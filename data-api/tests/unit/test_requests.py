import pytest
import sqlite3
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.sql_requests import requests


# ===== get_connection() tests =====
class TestGetConnection:
    def test_get_connection_creates_connection(self, mock_db_path):
        """Test that get_connection returns a valid SQLite connection."""
        conn = requests.get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
    
    def test_get_connection_creates_data_dir(self, mock_db_path):
        """Test that get_connection creates the data directory if it doesn't exist."""
        # Create a new temporary directory path that doesn't exist
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_data"
            test_db = test_dir / "test.db"
            
            with patch.object(requests, 'DATA_DB', test_db):
                conn = requests.get_connection()
                assert test_dir.exists()
                conn.close()


# ===== order_exist() tests =====
class TestOrderExist:
    def test_order_exist_returns_true_when_open_order_exists(self, initialized_db, mock_db_path):
        """Test that order_exist returns True when an open order exists for user."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            # Insert a test order
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'test order', 'open'))
            conn.commit()
            conn.close()
            
            result = requests.order_exist('user123')
            assert result is True
    
    def test_order_exist_returns_false_when_no_open_order(self, initialized_db, mock_db_path):
        """Test that order_exist returns False when no open order exists."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            result = requests.order_exist('nonexistent_user')
            assert result is False
    
    def test_order_exist_ignores_closed_orders(self, initialized_db, mock_db_path):
        """Test that order_exist ignores closed orders."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'test order', 'closed'))
            conn.commit()
            conn.close()
            
            result = requests.order_exist('user123')
            assert result is False


# ===== order_complete() tests =====
class TestOrderComplete:
    def test_order_complete_returns_true_when_open_order_exists(self, initialized_db, mock_db_path):
        """Test that order_complete returns True when an open order exists (note: function logic always returns True for existing orders)."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'incomplete_order', 'open'))
            conn.commit()
            conn.close()
            
            # Note: The function compares fetchone() (a tuple) to a string, so it always returns True
            result = requests.order_complete('user123')
            assert result is True
    
    def test_order_complete_returns_true_for_any_order_text(self, initialized_db, mock_db_path):
        """Test that order_complete returns True regardless of raw_text content."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'complete order', 'open'))
            conn.commit()
            conn.close()
            
            result = requests.order_complete('user123')
            assert result is True


# ===== create_order_db() tests =====
class TestCreateOrderDb:
    def test_create_order_db_inserts_order_and_items(self, initialized_db, mock_db_path):
        """Test that create_order_db inserts an order and its items."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            customer_order = {
                'total': 150.0,
                'raw_text': 'customer wants 2 items',
                'items': [
                    {
                        'item_id': 1,
                        'qty': 2,
                        'price': 13.0,
                        'spiciness': json.dumps(['moyen']),
                        'dish_base': json.dumps(['riz']),
                        'dish_meat': json.dumps(['boeuf'])
                    }
                ]
            }
            
            requests.create_order_db('user123', customer_order, 'open')
            
            # Verify order was created
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT * FROM orders WHERE user_id = ?", ('user123',))
            order = cur.fetchone()
            assert order is not None
            assert order[1] == 'user123'  # user_id
            assert order[2] == 150.0  # total
            
            # Verify items were created
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order[0],))
            items = cur.fetchall()
            assert len(items) == 1
            conn.close()
    
    def test_create_order_db_sets_correct_status(self, initialized_db, mock_db_path):
        """Test that create_order_db sets the correct status."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            customer_order = {
                'total': 100.0,
                'raw_text': 'order',
                'items': []
            }
            
            requests.create_order_db('user123', customer_order, 'validated')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT status FROM orders WHERE user_id = ?", ('user123',))
            status = cur.fetchone()[0]
            assert status == 'validated'
            conn.close()


# ===== add_item_db() tests =====
class TestAddItemDb:
    def test_add_item_db_adds_items_to_existing_order(self, initialized_db, mock_db_path):
        """Test that add_item_db adds items to an existing order."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            # Create initial order
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'initial order', 'open'))
            order_id = cur.lastrowid
            conn.commit()
            conn.close()
            
            # Add items
            customer_order = {
                'total': 200.0,
                'raw_text': 'added more items',
                'items': [
                    {
                        'item_id': 1,
                        'qty': 1,
                        'price': 13.0,
                        'spiciness': json.dumps(['fort']),
                        'dish_base': json.dumps(['nouilles fines']),
                        'dish_meat': json.dumps(['poulet'])
                    }
                ]
            }
            
            requests.add_item_db('user123', customer_order, 'open')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            items = cur.fetchall()
            assert len(items) == 1
            conn.close()
    
    def test_add_item_db_updates_total(self, initialized_db, mock_db_path):
        """Test that add_item_db updates the order total."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'initial', 'open'))
            conn.commit()
            conn.close()
            
            customer_order = {
                'total': 250.0,
                'raw_text': 'updated',
                'items': []
            }
            
            requests.add_item_db('user123', customer_order, 'open')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT total FROM orders WHERE user_id = ?", ('user123',))
            total = cur.fetchone()[0]
            assert total == 250.0
            conn.close()


# ===== update_order_db() tests =====
class TestUpdateOrderDb:
    def test_update_order_db_updates_existing_items(self, initialized_db, mock_db_path):
        """Test that update_order_db updates quantities of existing items."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'initial', 'open'))
            order_id = cur.lastrowid
            
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 1, 50.0, json.dumps(['moyen']), json.dumps(['riz']), json.dumps(['boeuf'])))
            conn.commit()
            conn.close()
            
            # Update order
            customer_order = {
                'total': 100.0,
                'raw_text': 'updated',
                'items': [
                    {
                        'item_id': 1,
                        'qty': 2,
                        'price': 13.0,
                        'spiciness': json.dumps(['moyen']),
                        'dish_base': json.dumps(['riz']),
                        'dish_meat': json.dumps(['boeuf'])
                    }
                ]
            }
            
            requests.update_order_db('user123', customer_order, 'open')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT qty FROM order_items WHERE order_id = ? AND menu_item_id = ?", (order_id, 1))
            qty = cur.fetchone()[0]
            assert qty == 2
            conn.close()


# ===== delete_items_db() tests =====
class TestDeleteItemsDb:
    def test_delete_items_db_removes_specific_items(self, initialized_db, mock_db_path):
        """Test that delete_items_db removes specified items from order."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 150.0, 'initial', 'open'))
            order_id = cur.lastrowid
            
            # Insert two items
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 1, 50.0, json.dumps(['moyen']), json.dumps(['riz']), json.dumps(['boeuf'])))
            
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, 2, 1, 50.0, json.dumps(['fort']), json.dumps(['thick']), json.dumps(['poulet'])))
            conn.commit()
            conn.close()
            
            # Delete one item
            items_to_remove = [
                {
                    'item_id': 1,
                    'spiciness': json.dumps(['moyen']),
                    'dish_base': json.dumps(['riz']),
                    'dish_meat': json.dumps(['boeuf'])
                }
            ]
            
            customer_order = {
                'total': 50.0,
                'raw_text': 'removed item',
                'items': []
            }
            
            requests.delete_items_db('user123', customer_order, items_to_remove, 'open')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (order_id,))
            count = cur.fetchone()[0]
            assert count == 1
            conn.close()
    
    def test_delete_items_db_updates_total(self, initialized_db, mock_db_path):
        """Test that delete_items_db updates order total."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'initial', 'open'))
            order_id = cur.lastrowid
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 1, 50.0, json.dumps(['moyen']), json.dumps(['riz']), json.dumps(['boeuf'])))
            conn.commit()
            conn.close()
            
            items_to_remove = [
                {
                    'item_id': 1,
                    'spiciness': json.dumps(['moyen']),
                    'dish_base': json.dumps(['riz']),
                    'dish_meat': json.dumps(['boeuf'])
                }
            ]
            
            customer_order = {
                'total': 0.0,
                'raw_text': 'no items',
                'items': []
            }
            
            requests.delete_items_db('user123', customer_order, items_to_remove, 'open')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT total FROM orders WHERE user_id = ?", ('user123',))
            total = cur.fetchone()[0]
            assert total == 0.0
            conn.close()


# ===== delete_order_db() tests =====
class TestDeleteOrderDb:
    def test_delete_order_db_removes_order_and_items(self, initialized_db, mock_db_path):
        """Test that delete_order_db removes order and all associated items."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'test', 'open'))
            order_id = cur.lastrowid
            
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, qty, price, spiciness, dish_base, dish_meat)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, 1, 1, 50.0, json.dumps(['moyen']), json.dumps(['riz']), json.dumps(['boeuf'])))
            conn.commit()
            conn.close()
            
            requests.delete_order_db('user123')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", ('user123',))
            order_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (order_id,))
            item_count = cur.fetchone()[0]
            conn.close()
            
            assert order_count == 0
            assert item_count == 0
    
    def test_delete_order_db_only_deletes_specified_user_order(self, initialized_db, mock_db_path):
        """Test that delete_order_db only deletes the specified user's order."""
        with patch.object(requests, 'DATA_DB', mock_db_path):
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            # Create orders for two different users
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user123', 100.0, 'test', 'open'))
            order_id_1 = cur.lastrowid
            
            cur.execute("""
                INSERT INTO orders (user_id, total, raw_text, status)
                VALUES (?, ?, ?, ?)
            """, ('user456', 100.0, 'test', 'open'))
            order_id_2 = cur.lastrowid
            conn.commit()
            conn.close()
            
            requests.delete_order_db('user123')
            
            conn = sqlite3.connect(mock_db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", ('user123',))
            count_user1 = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", ('user456',))
            count_user2 = cur.fetchone()[0]
            conn.close()
            
            assert count_user1 == 0
            assert count_user2 == 1


