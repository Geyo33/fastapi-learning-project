# 🍜 Automated wAIter (Learning project)

A conversational AI restaurant ordering system built as a personal learning project. Users can browse a menu and place orders through a natural language chat interface powered by a local LLM backend and validate the order.

The repository is organised as a **monorepo of three independent projects**, each with its own virtual environment and dependencies.

---

## 🗂️ Repository Structure

```
/
├── frontend/          # Placeholder Gradio chat UI as frontend (port 7860)
├── client-api/        # LLM orchestration service (FastAPI + Uvicorn, port 8001)
├── data-api/          # Restaurant data & orders storage (FastAPI + SQLite + Uvicorn, port 8002)
└── README.md          # This file
```

---

## 🧩 Projects

### 1. `frontend/` – Gradio Interface
A browser-based chat UI where customers interact with the AI waiter. Displays the restaurant menu(in a separate tab) alongside a chat window and keeps a live view of the current order.

**Key tech:** Gradio · Pydantic · Pandas · Requests  
**Talks to:** `client-api` on `http://localhost:8001/api/v1`

---

### 2. `client-api/` – LLM Client Service
A FastAPI application that wraps a language-model client and orchestrates the ordering flow. Receives chat messages from the frontend, calls the LLM, parses the response, and coordinates with the data API to read/write orders.

**Key tech:** FastAPI · Uvicorn · Pydantic · async Python  
**Listens on:** `http://localhost:8001/api/v1`  
**Talks to:** `data-api` on `http://localhost:8002`

---

### 3. `data-api/` – Restaurant Data API
A FastAPI application that owns all persistent state: menus and orders stored in a SQLite database. Acts as a simple CRUD backend consumed by the LLM service.

**Key tech:** FastAPI · Uvicorn · SQLite · Pydantic  
**Listens on:** `http://localhost:8002/api/v1`

---

## 🚀 Getting Started

Each project has its own virtual environment. Open **three separate terminals** and follow the steps below.

### Configuration

`client_api/` requires an LLM API key or local endpoint.  
Refer to `client-api/README.md` for details on setting up the `.env` file.

- #### Tools Used
  - Primarily built and tested with Qwen3.5-9B (thinking mode disabled).

### Terminal 1 – Data API

```bash
cd data-api
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

### Terminal 2 – LLM Client API

```bash
cd client-api
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
# Copy .env.example to .env and add your LLM API key / endpoint
cp .env.example .env
uvicorn src.llm_service.main:app --reload --port 8001
```

### Terminal 3 – Frontend

```bash
cd frontend
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open your browser at the URL printed by Gradio (typically `http://localhost:7860`).

---

## 🔌 Service Map

```
Browser
  └─► Gradio (7860)
        └─► client-api (8001)  ←─ LLM provider (external)
              └─► data-api (8002)
                    └─► SQLite
```

---

## 🧪 Running Tests

Tests live inside `client-api/` and `data-api/`.

```bash
cd client-api
pytest -q
```

```bash
cd data-api
pytest -q
```

---

## ⚠️ Disclaimers

- **Learning project only** – no authentication, minimal error handling, wide-open CORS, trivial in-memory/SQLite stores.
- The LLM client expects a specific JSON response structure.
- You will need a valid API key or local model endpoint configured in `client-api/.env`.
