# 🧠 Automated wAIter – Client API

A **FastAPI** service that wraps a language-model client and orchestrates the restaurant ordering flow. It receives chat messages from the frontend, calls the LLM, parses the response, and coordinates with the data API to read and write orders.

> **Learning project** – part of a three-project monorepo. Not intended for production use.

---

## 📋 Overview

| | |
|---|---|
| **Role** | LLM orchestration service |
| **Framework** | FastAPI + Uvicorn |
| **Depends on** | `data-api` running on `http://localhost:8002/api/v1` |
| **Default port** | 8001 |

---

## ✨ Features

- **Chat endpoint** – receives user messages, calls the LLM, returns order suggestions
- **Order validation** – delegates order logic to the data API
- **CRUD pass-through** – forwards order and customer operations downstream
- **Health check** – simple liveness endpoint
- **Configurable** – Pydantic settings with `.env` support

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A valid LLM API key or local model endpoint
- `data-api` service running (see its README)

### Installation

```bash
cd client-api
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copy the example env file and fill in your LLM credentials:

```bash
cp .env.example .env
```

LLM models used must be specified in settings. Settings can be reviewed and tweaked in `config.py`.

### Running the service

```bash
uvicorn src.llm_service.main:app --reload
```

The API will be available at `http://localhost:8001/api/v1` (the `PORT` setting is honoured).

---

## 📁 Project Structure

```
client-api/
├── src/llm_service/
│   ├── main.py                        # App factory – wires clients, orchestrators, CORS
│   ├── config.py                      # Pydantic settings
|   ├── custom_exceptions.py           # Custom exception classes
│   ├── api/
│   │   └── routes.py                  # HTTP endpoints (chat, orders, CRUD, health)
│   ├── llm/                           # LLM client, prompts, parsers, helpers
│   │   └── infrastructure/
│   │       └── orders_client.py       # Stubbed orders storage / HTTP client
│   ├── models/                        # Domain objects and Pydantic schemas
│   └── services/                      # Orchestrator & OrderOrchestrator
├── tests/
│   ├── conftest.py                    # pytest fixtures (FastAPI TestClient)
│   ├── unit/                          # Isolated tests for LLM client & order-draft logic
│   └── integration/                   # End-to-end tests against /api/v1/*
├── requirements.txt
├── pytest.ini
└── README.md                          # This file
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Liveness check |
| `POST` | `/api/v1/chat` | Send a message |
| `POST` | `/api/v1/orders/create_order` | Create or extend an order |
| `PUT` | `/api/v1/orders/validate_order/{order_id}` | Validate an order |
| `GET` | `/api/v1/orders/{order_id}` | Get order details |
| `GET` | `/api/v1/orders/is_open/{order_id}` | Check if an order is open |

See `api/routes.py` for the full list.

---

## 🧪 Running Tests

Unit tests mock the LLM client and use an in-memory orders store — no external services required.

```bash
pytest -q
```

---

## 💡 Learning Goals

- Building async REST APIs with **FastAPI**
- Wrapping and consuming an **LLM client**
- **Pydantic** models and settings management
- Writing **unit and integration tests** with pytest
- Structuring a Python service with clear separation of concerns

---

## ⚠️ Notes

- The LLM client expects the provider to return a specific JSON structure.
- No authentication, minimal error handling, wide-open CORS — learning purposes only.

---

## 🗺️ Related Projects

| Project | Description |
|---------|-------------|
| `frontend/` | Gradio chat UI – port 7860 |
| `data-api/` | Restaurant data & orders storage – FastAPI + SQLite, port 8002 |

See the root `README.md` for instructions on running all three services together.
