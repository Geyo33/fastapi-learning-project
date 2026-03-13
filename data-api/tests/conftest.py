import pytest
import sqlite3
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app
from app.sql_requests import requests
from app.schemas import (
    UserContext,
    OrderSuggestion,
    OrderItem,
)


# ---------------------------------------------------------------------------
# database fixtures (used by unit and integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    """Create a temporary SQLite database file for testing and clean it up.

    Tests that need to talk to the database can use this path and patch
    ``requests.DATA_DB`` so the real database isn't touched.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        temp_path = Path(f.name)
    yield temp_path
    # teardown: remove file if it still exists
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_db_path(temp_db):
    """Patch ``requests.DATA_DB`` so all database calls go to the temporary file."""
    with patch.object(requests, "DATA_DB", temp_db):
        yield temp_db


@pytest.fixture
def initialized_db(temp_db):
    """Create the minimal schema (orders, order_items, MTW_menu) in the temp DB.

    This mirrors the logic from the original unit test file; other tests
    can depend on ``mock_db_path`` as well if they need the path.
    """
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()

    # orders table
    cur.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            total REAL NOT NULL,
            raw_text TEXT,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'validated', 'closed')),
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # order_items table
    cur.execute("""
        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            price REAL NOT NULL,
            spiciness TEXT,
            dish_base TEXT,
            dish_meat TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (menu_item_id) REFERENCES MTW_menu(id)
        )
    """)

    # unique index on order_items
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_order_item_unique 
        ON order_items (
            order_id,
            menu_item_id,
            spiciness,
            dish_base,
            dish_meat
        )
    """)

    # menu table (used by some helpers)
    cur.execute("""
        CREATE TABLE MTW_menu (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            dish_name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            spiciness TEXT,
            dish_base TEXT,
            dish_meat TEXT
        )
    """)

    conn.commit()
    conn.close()
    return temp_db


# ---------------------------------------------------------------------------
# data-directory fixtures (used by integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_data_dir():
    """Temporary directory that stands in for the ``data/`` folder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        yield temp_path


@pytest.fixture
def mock_data_paths(temp_data_dir, temp_db):
    """Patch both storage paths and the DATABASE path to point into temp objects.

    ``temp_data_dir`` is used for JSON files; ``temp_db`` gives a clean DB file.
    When the fixture is entered we also create the schema by calling
    ``init_db`` under the patched path so that endpoints have tables ready.
    """
    # patch storage.DATA_DIR and the module-level paths in sql_requests
    with patch("app.storage.DATA_DIR", temp_data_dir), \
         patch("app.sql_requests.requests.DATA_DIR", temp_data_dir), \
         patch("app.sql_requests.requests.DATA_DB", temp_db):
        # ensure tables exist before tests run
        from app.sql_requests.requests import init_db
        init_db()
        yield temp_data_dir


# ---------------------------------------------------------------------------
# client fixture (integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def client(mock_data_paths):
    """FastAPI test client that depends on the patched paths fixture.

    The dependency ensures the database and data directories are
    redirected before the application starts up in the TestClient.
    """
    return TestClient(app)


from app.storage import load_ci, save_ci, load_ci_validated, save_ci_validated

@pytest.fixture
def revert_order_status(mock_db_path):
    """Return a helper allowing tests to set an order's status back to open.

    The fixture connects directly to the temporary database patched by
    ``mock_db_path`` and executes an UPDATE statement.  It also updates the
    customer-info JSON files so that the delete endpoint can run without
    KeyError.  Accepts an optional ``user_context`` value (pydantic model or
    dict) to re‑populate the CI record; if omitted a minimal entry is added.
    """
    def _revert(user_id: str, user_context=None):
        # database
        conn = sqlite3.connect(mock_db_path)
        cur = conn.cursor()
        cur.execute("""UPDATE orders SET status = 'open' WHERE user_id = ?""", (user_id,))
        conn.commit()
        conn.close()

        # ensure open customers_info contains the user
        ci = load_ci()
        if user_context is not None:
            # model_dump if it's a pydantic object
            try:
                ci[user_id] = user_context.model_dump()
            except Exception:
                ci[user_id] = user_context
        else:
            ci[user_id] = {"user_id": user_id}
        save_ci(ci)

        # remove from validated list if present
        civ = load_ci_validated()
        civ.pop(user_id, None)
        save_ci_validated(civ)

    return _revert


# ---------------------------------------------------------------------------
# example data fixtures (shared by all tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_user_context():
    return UserContext(
        user_id="test_user_123",
        user_history=[{"role": "user", "content": "user message"}, {"role": "assistant", "content": "bot message"}],
        language="en",
    )


@pytest.fixture
def sample_order_suggestion():
    return OrderSuggestion(
        items=[
            OrderItem(
                item_id=1,
                qty=2,
                price=26,
                spiciness=json.dumps(["moyen"]),
                dish_base=json.dumps(["riz"]),
                dish_meat=json.dumps(["boeuf"]),
            ),
            OrderItem(
                item_id=2,
                qty=1,
                price=13,
                spiciness=json.dumps(["fort"]),
                dish_base=json.dumps(["nouilles fines"]),
                dish_meat=json.dumps(["poulet"]),
            ),
        ],
        total=39,
        raw_text="Deux wok saté et un wok thaï",
    )


@pytest.fixture
def sample_menu_data(temp_data_dir):
    menu_data = [
        {
        "id": 1, 
        "category": "plat", 
        "dish_name": "Wok saté", 
        "description": "Plat sauce saté à base de viande/fruits de mer(au choix) sauté au wok avec riz ou nouilles(au choix)",
        "price": 13,
        "spiciness": ["non épicé","léger","moyen","fort","indéfini"],
        "dish_base": ["riz","nouilles larges","nouilles fines","indéfini"],
        "dish_meat": ["boeuf","porc","poulet","crevette","seiche","indéfini"]
        },
        {
            "id": 2, 
            "category": "plat", 
            "dish_name": "Wok thaï", 
            "description": "Plat sauce thaï à base de viande/fruits de mer(au choix) sauté au wok avec riz ou nouilles(au choix)",
            "price": 13,
            "spiciness": ["non épicé","léger","moyen","fort","indéfini"],
            "dish_base": ["riz","nouilles larges","nouilles fines","indéfini"],
            "dish_meat": ["boeuf","porc","poulet","crevette","seiche","indéfini"]
        },
    ]

    menu_file = temp_data_dir / "menus" / "MTW_menu.json"
    menu_file.parent.mkdir(parents=True, exist_ok=True)
    with open(menu_file, "w") as f:
        json.dump(menu_data, f)

    return menu_data
