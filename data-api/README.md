# 🗄️ Automated wAIter – Data API

A **FastAPI** service that manages all persistent state for the Automated wAIter system: restaurant menus and customer orders stored in a SQLite database.

> **Learning project** – part of a three-project monorepo. Not intended for production use.

---

## 📋 Overview

| | |
|---|---|
| **Role** | Restaurant data & orders storage |
| **Framework** | FastAPI + Uvicorn |
| **Database** | SQLite (created automatically on first run) |
| **Default port** | 8002 |

---

## ✨ Features

- **Menu management** – retrieve menu items for a given restaurant
- **Order management** – create, update, validate, and query orders
- **Customer data** – store and manage customer information
- **Request timing** – middleware to track request processing time
- **CORS support** – enabled for frontend integration
- **Sample data** – included in `data/` for easy local testing

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+

### Installation

```bash
cd data-api
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Running the service

```bash
uvicorn main:app --reload --port 8002
```

The API will be available at `http://localhost:8002/api/v1`.  
Interactive docs (Swagger UI) are at `http://localhost:8002/docs`.

---

## 📁 Project Structure

```
data-api/
├── main.py                          # FastAPI app entry point
├── app/
│   ├── schemas.py                   # Pydantic models
│   ├── storage.py                   # JSON file operations for customer data and menus
│   ├── middleware/                  
│   ├── routes/                      # API route handlers
│   └── sql_requests/                # SQLite database operations
├── data/
│   ├── ai_waiter.db                 # SQLite database (auto-created)
│   ├── customer_info.json           # customer data
│   ├── customer_info_validated.json # validated customer data
│   └── menus/
│       └── MTW_menu.json            # Sample menu for restaurant "MTW"
├── tests/
│   ├── conftest.py                  # pytest fixtures
│   ├── unit/                        # Isolated tests for Sqlite operations
│   └── integration/                 # End-to-end tests
├── requirements.txt
└── README.md                        # This file
```

---

## 🔌 API Endpoints

### Restaurants

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/restaurants/{restaurant_id}/menu` | Get menu for a specific restaurant |

### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/orders/is_open/{order_id}` | Check if an order is open |
| `GET` | `/api/v1/orders/{order_id}` | Get details of a specific order |
| `POST` | `/api/v1/orders/create_order` | Create a new order or add items to an existing one |
| `POST` | `/api/v1/orders/update_order/{order_id}` | Update an existing order (e.g., change items, quantities) |
| `POST` | `/api/v1/orders/remove_from_order/{order_id}` | Remove items from an order |
| `POST` | `/api/v1/orders/remove_order/{order_id}` | Delete an order entirely |
| `PUT` | `/api/v1/orders/validate_order/{order_id}` | Validate an order |

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| FastAPI | Web framework |
| Uvicorn | ASGI server |
| Pydantic | Data validation and serialisation |
| SQLite (stdlib) | Lightweight data storage |
| pytest | Testing framework |

---

## 🧪 Running Tests

temporary SQLite database file for testing and JSON storage files for testing.

```bash
pytest -q
```

---

## 💡 Learning Goals

- Building REST APIs with **FastAPI**
- **SQLite** database integration
- **Pydantic** data modelling and validation
- **Middleware** implementation (request timing)
- **CORS** configuration
- Basic **CRUD** operations

---

## 🗺️ Related Projects

| Project | Description |
|---------|-------------|
| `frontend/` | Gradio chat UI – port 7860 |
| `client-api/` | LLM orchestration service – FastAPI, port 8001 |

See the root `README.md` for instructions on running all three services together.
