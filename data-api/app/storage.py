from pathlib import Path
import json

DATA_DIR = Path("data")
DATA_CI = DATA_DIR / "customer_info.json"
DATA_CI_VALIDATED = DATA_DIR / "customer_info_validated.json"


def load_menu(restaurant_id: str) -> list:
    MENU = DATA_DIR / "menus" / f"{restaurant_id}_menu.json"
    if MENU.exists():
        with MENU.open("r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return []
    return []

def save_menu(restaurant_id: str, menu_data: list):
    MENU = DATA_DIR / "menus" / f"{restaurant_id}_menu.json"
    MENU.parent.mkdir(parents=True, exist_ok=True)
    with MENU.open("w", encoding="utf-8") as f:
        json.dump(menu_data, f, indent=2)


def load_ci() -> dict:
    if DATA_CI.exists():
        with open(DATA_CI, "r") as f:
            content = f.read()
            if content.strip():
                return json.loads(content)
    return {}


def save_ci(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_CI, "w") as f:
        json.dump(data, f, indent=2)


def load_ci_validated() -> dict:
    if DATA_CI_VALIDATED.exists():
        with open(DATA_CI_VALIDATED, "r") as f:
            content = f.read()
            if content.strip():
                return json.loads(content)
    return {}


def save_ci_validated(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_CI_VALIDATED, "w") as f:
        json.dump(data, f, indent=2)