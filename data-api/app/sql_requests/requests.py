import sqlite3
import json
from datetime import datetime
from pathlib import Path

from .parser import parse_customer_order
from ..storage import save_menu, load_menu


DATA_DIR = Path("./data")
DATA_DB = DATA_DIR / "ai_waiter.db"

def get_connection():
    DATA_DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATA_DB)

def menu_to_json(db_path, table_name):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table_name} WHERE id = 1")
        columns = [description[0] for description in cur.description]
        results = []
        for row in cur.fetchall():
            result = dict(zip(columns, row))
            results.append(result)
        result["spiciness"] = json.loads(result["spiciness"])
        result["dish_base"] = json.loads(result["dish_base"])
        result["dish_meat"] = json.loads(result["dish_meat"])
        save_menu("MTW", results)
    except Exception as e:
        print(f"Error processing menu JSON: {e}")
    finally:
        if conn:
            conn.close()

def init_db():
    try:
        conn = get_connection()
        cur = conn.cursor()

        restaurant_id = "MTW"
        table_menu_name = f"{restaurant_id}_menu"

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_menu_name} (
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
        menu_to_insert = load_menu(restaurant_id)
        for item in menu_to_insert:
            cur.execute(f"""
                INSERT OR IGNORE INTO {table_menu_name} (id, category, dish_name, description, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item["id"], item["category"], item["dish_name"], item["description"], item["price"],
                json.dumps(item["spiciness"]), json.dumps(item["dish_base"]), json.dumps(item["dish_meat"])))

        cur.execute(f"""
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

        cur.execute(f"""
            CREATE TABLE order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                menu_item_id INTEGER NOT NULL,   -- Links to your menu table
                qty INTEGER NOT NULL DEFAULT 1,
                price REAL NOT NULL,
                spiciness TEXT,
                dish_base TEXT, 
                dish_meat TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (menu_item_id) REFERENCES MTW_menu(id)
            )
        """)

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

        conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        conn.close()


def order_exist(user_id: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()

        cur.execute("""
            SELECT user_id 
            FROM orders 
            WHERE status = ? AND user_id = ?
        """, ('open', user_id))
        id_fetched = cur.fetchone()
        return bool(id_fetched)
    except Exception as e:
        print(f"Error checking if order exists: {e}")
        return False
    finally:
        if conn:
            conn.close()
    
def order_complete(user_id: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()

        cur.execute("""
            SELECT raw_text 
            FROM orders 
            WHERE status = ? AND user_id = ?
        """, ('open', user_id))

        is_complete = cur.fetchone() != "incomplete_order"
        return is_complete
    except Exception as e:
        print(f"Error checking if order is complete: {e}")
        return False
    finally:
        if conn:
            conn.close()

    
def get_order_db(user_id: str) -> dict:
    def fetch_table(table_name: str, status: str, user_id: str) -> list[dict]:
        query = f"""
            SELECT user_id, total, raw_text
            FROM {table_name}
            WHERE status = ? AND user_id = ?
        """
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()
        try:
            if table_name == 'orders':
                query = """
                    SELECT *
                    FROM orders
                    WHERE status = ? AND user_id = ?
                """
                cur.execute(query, (status, user_id))
            else:
                query = """
                    SELECT menu_item_id, qty, price, spiciness, dish_base, dish_meat
                    FROM order_items
                    WHERE order_id = ?
                """
                cur.execute(query, (user_id,))
            
            columns = [description[0] if description[0] != "menu_item_id" else "item_id" for description in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            return results
        finally:
            conn.close()

    # Fetch both tables
    order_info = fetch_table('orders', 'open', user_id)
    order_items = fetch_table('order_items', 'open', order_info[0]["order_id"])
    
    customer_order = parse_customer_order({
            'order': order_info[0],
            'order_items': order_items
        }
    )
    return customer_order
    
    
def get_menu_db():
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()
        cur.execute("SELECT * FROM MTW_menu")
        columns = [description[0] for description in cur.description]
        results = []
        for row in cur.fetchall():
            result = dict(zip(columns, row))
            results.append(result)
        result["spiciness"] = json.loads(result["spiciness"])
        result["dish_base"] = json.loads(result["dish_base"])
        result["dish_meat"] = json.loads(result["dish_meat"])
        json_output = json.dumps(results, indent=4)
        return json_output
    except Exception as e:
        print(f"Error retrieving menu from database: {e}")
        return json.dumps([], indent=4)
    finally:
        if conn:
            conn.close()


def create_order_db(user_id, customer_order, status):
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()
        
        # Insert main order
        cur.execute("""
            INSERT INTO orders (user_id, total, raw_text, status) 
            VALUES (?, ?, ?, ?)
        """, (user_id, customer_order['total'], customer_order['raw_text'], status))
        
        order_id = cur.lastrowid
        
        # Insert items
        for item in customer_order['items']:
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, item['item_id'], item['qty'], item['price'],
                  item['spiciness'], item['dish_base'], item['dish_meat']))
        
        conn.commit()
    except Exception as e:
        print(f"Error creating order: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def add_item_db(user_id, customer_order, status):
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()

        cur.execute("""
            UPDATE orders 
            SET total = ?, raw_text = ?, status = ?, updated_at = ?
            WHERE user_id = ?
        """, (customer_order['total'], customer_order['raw_text'], status, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))

        cur.execute("SELECT order_id FROM orders WHERE user_id = ?", (user_id,))
        order_id = cur.fetchone()[0]

        # Insert items
        for item in customer_order['items']:
            cur.execute("""
                INSERT INTO order_items (
                    order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id, menu_item_id, spiciness, dish_base, dish_meat)
                DO UPDATE SET
                    qty = excluded.qty,
                    price = excluded.price
            """, (order_id, item['item_id'], item['qty'], item['price'],
                  item['spiciness'], item['dish_base'], item['dish_meat']))
        
        conn.commit()
    except Exception as e:
        print(f"Error adding item to order: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def update_order_db(user_id, customer_order, status):
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE orders 
            SET total = ?, raw_text = ?, status = ?, updated_at = ?
            WHERE user_id = ?
        """, (customer_order['total'], customer_order['raw_text'], status, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        cur.execute("SELECT order_id FROM orders WHERE user_id = ?", (user_id,))
        order_id = cur.fetchone()[0]
        
        for item in customer_order['items']:
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id, menu_item_id, spiciness, dish_base, dish_meat) 
                DO UPDATE SET
                    qty = excluded.qty,
                    price = excluded.price,
                    spiciness = excluded.spiciness,
                    dish_base = excluded.dish_base,
                    dish_meat = excluded.dish_meat
            """, (order_id, item['item_id'], item['qty'], item['price'],
                  item['spiciness'], item['dish_base'], item['dish_meat']))
        
        conn.commit()
    except Exception as e:
        print(f"Error updating order: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def delete_items_db(user_id, customer_order, items_to_remove, status):
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()

        cur.execute("SELECT order_id FROM orders WHERE status = ? AND user_id = ?", ('open', user_id))
        order_id = cur.fetchone()[0]

        for item in items_to_remove:
            cur.execute("""
                DELETE FROM order_items 
                WHERE order_id = ? AND menu_item_id = ? AND spiciness = ? AND dish_base = ? AND dish_meat = ?
            """, (order_id, item["item_id"], item["spiciness"], item["dish_base"], item["dish_meat"]))

        cur.execute("""
            UPDATE orders 
            SET total = ?, raw_text = ?, status = ?, updated_at = ?
            WHERE user_id = ?
        """, (customer_order['total'], customer_order['raw_text'], status, 
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
    except Exception as e:
        print(f"Error deleting items from order: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def delete_order_db(user_id):
    conn = None
    try:
        conn = sqlite3.connect(DATA_DB)
        cur = conn.cursor()

        cur.execute("SELECT order_id FROM orders WHERE status = ? AND user_id = ?", ('open', user_id))
        order_id = cur.fetchone()[0]

        cur.execute("""
            DELETE FROM order_items WHERE order_id = ?
        """, (order_id,))
        cur.execute("""
            DELETE FROM orders WHERE user_id = ?
        """, (user_id,))

        conn.commit()
    except Exception as e:
        print(f"Error deleting order: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()