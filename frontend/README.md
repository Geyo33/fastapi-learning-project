# 🍜 Automated wAIter – Frontend

A **Gradio-based** chat interface for the Automated wAIter system. Users can browse the restaurant menu and place orders through a natural language conversation powered by the LLM backend, validate an order or cancel it.

> **Learning project** – part of a three-project monorepo. Not intended for production use.

---

## 📋 Overview

| | |
|---|---|
| **Role** | Browser UI |
| **Framework** | Gradio |
| **Depends on** | `client-api` running on `http://localhost:8001/api/v1` |
| **Default port** | 7860 |

---

## ✨ Features

- **Chat-based ordering** – natural language interface for placing food orders
- **Menu browsing** – view menu items organised by category
- **Live order view** – order total and item list update as you chat
- **Order management** – add, update, or remove items mid-conversation
- **Order validation** – confirm and send orders to the kitchen
- **Session management** – persistent user context and order history

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- `client-api` service running (see its README)
- `data-api` service running (see its README)

### Installation

```bash
cd frontend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Running the app

```bash
python app.py
```

Open your browser at the URL printed by Gradio (typically `http://localhost:7860`).

---

## 📁 Project Structure

```
frontend/
├── app.py              # Gradio UI, API calls, event handlers, data formatting
├── schemas.py          # Pydantic models for data validation
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🔌 API Integration

All communication goes to `client-api` at `http://localhost:8001/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/get-menu/{restaurant_id}` | Fetch restaurant menu |
| `GET` | `/order-exists/{user_id}` | Check if user has an open order |
| `GET` | `/get-order/{user_id}` | Retrieve current order |
| `POST` | `/chat` | Send message to LLM for order suggestions |
| `POST` | `/create-order` | Create a new order |
| `POST` | `/update-order/{user_id}` | Update existing order |
| `POST` | `/remove-from-order/{user_id}` | Remove items from order |
| `POST` | `/remove-order/{user_id}` | Delete an order |
| `POST` | `/validate-order` | Validate and finalise order |

---

## 🗂️ Data Models (`schemas.py`)

| Model | Description |
|-------|-------------|
| `UserContext` | User ID, order history, language preference |
| `MenuItem` | Menu items with prices and descriptions |
| `OrderItem` | Individual order line (quantity, price, customisations) |
| `OrderSuggestion` | Collection of order items with total |
| `OrderRequest` | Payload for order operations |
| `CustomerOrder` | Complete order with status |
| `ChatRequest` | Payload for chat interactions |

---

## 📦 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Gradio | 6.5.1 | Web UI framework |
| Pydantic | 2.12.5 | Data validation |
| Pandas | 3.0.0 | Data manipulation & display |
| Requests | 2.32.5 | HTTP client |

---

## 💡 Learning Goals

- Building web interfaces with **Gradio**
- Making **HTTP requests** to a REST backend
- **Data validation** with Pydantic
- **State management** in interactive web apps
- **Error handling** for API calls
- Using **Pandas DataFrames** for UI display

---

## 🗺️ Related Projects

| Project | Description |
|---------|-------------|
| `client-api/` | LLM orchestration service – FastAPI, port 8001 |
| `data-api/` | Restaurant data & orders storage – FastAPI + SQLite, port 8002 |

See the root `README.md` for instructions on running all three services together.
