# NL2SQL Clinic Chatbot

A production-ready **Natural Language to SQL** system built with **Vanna AI 2.0**, **FastAPI**, **Google Gemini 2.5 Flash**, and **SQLite**.

Users ask questions in plain English and receive SQL results, human-readable summaries, and Plotly charts — all powered by an AI agent.

---

## Architecture

```
User Question (English)
        │
        ▼
FastAPI Backend  (main.py)
        │  ← input validation, rate limiting, caching
        ▼
Vanna 2.0 Agent  (vanna_setup.py)
  ├── GeminiLlmService    (gemini-2.5-flash)
  ├── DemoAgentMemory     (15 seeded Q&A pairs)
  ├── RunSqlTool          (executes validated SQL)
  ├── VisualizeDataTool   (chart hints)
  └── SqliteRunner        (clinic.db)
        │
        ▼
SQL Validator  (sql_validator.py)
  SELECT-only · blocks DML/DDL · blocks system tables
        │
        ▼
SQLite Execution  (clinic.db)
        │
        ▼
Plotly Chart Generator  (chart_generator.py)
        │
        ▼
JSON Response: message + sql + rows + chart
```

### Database Schema

| Table        | Rows  | Description                              |
|--------------|-------|------------------------------------------|
| patients     | 200   | Patient demographics                     |
| doctors      | 15    | Doctors with specialization              |
| appointments | 500   | Clinic visits with status                |
| treatments   | ~350  | Procedures linked to completed visits    |
| invoices     | 300   | Billing records                          |

### LLM Provider

**Option A — Google Gemini** (`gemini-2.5-flash`)
- Free tier via [Google AI Studio](https://aistudio.google.com/apikey)
- Import: `from vanna.integrations.google import GeminiLlmService`

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- A free Google Gemini API key from [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 2. Clone and set up environment

```bash
git clone <your-repo-url>
cd nl2sql_project

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API key

```bash
cp .env.example .env
# Edit .env and set your GOOGLE_API_KEY
```

```dotenv
GOOGLE_API_KEY=AIza...your-key-here
```

### 5. Create the database

```bash
python setup_database.py
```

Expected output:
```
==================================================
  clinic.db created successfully!
==================================================
  patients       : 200
  doctors        : 15
  appointments   : 500
  treatments     : 347
  invoices       : 300
==================================================
```

### 6. Seed agent memory

```bash
python seed_memory.py
```

### 7. Start the API server

```bash
uvicorn main:app --port 8000 --reload
```

The API is live at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### One-liner (from the assignment spec)

```bash
pip install -r requirements.txt && python setup_database.py \
  && python seed_memory.py && uvicorn main:app --port 8000
```

---

## API Reference

### `POST /chat`

Ask a natural language question about clinic data.

**Request**
```json
{ "question": "Show me the top 5 patients by total spending" }
```

**Response**
```json
{
  "message":    "Found 5 results for: \"Show me the top 5 patients by total spending\".",
  "sql_query":  "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spent ...",
  "columns":    ["first_name", "last_name", "total_spent"],
  "rows":       [["Arjun", "Sharma", 14200.50], ...],
  "row_count":  5,
  "chart":      { "data": [...], "layout": {...} },
  "chart_type": "bar",
  "cached":     false
}
```

**Error response** (invalid/unsafe SQL)
```json
{
  "message": "The generated SQL was rejected for safety reasons: Only SELECT queries are allowed.",
  "sql_query": "DROP TABLE patients"
}
```

### `GET /health`

```json
{
  "status":             "ok",
  "database":           "connected",
  "agent_memory_items": 15
}
```

---

## Sample Questions

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Which doctor has the most appointments?"}'

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Show revenue by specialization"}'
```

---

## Security

- **SELECT-only**: All non-SELECT statements are rejected before execution.
- **Keyword blocklist**: `DROP`, `INSERT`, `DELETE`, `UPDATE`, `EXEC`, `xp_`, `sp_`, `PRAGMA`, etc.
- **System table guard**: Access to `sqlite_master` and `information_schema` is blocked.
- **Rate limiting**: 20 requests per 60 seconds per IP.
- **Query caching**: Identical questions are served from cache (no LLM cost).
- **Input validation**: Questions must be 2–500 characters.

---

## Project Structure

```
nl2sql_project/
├── setup_database.py    # Creates clinic.db + inserts dummy data
├── seed_memory.py       # Seeds DemoAgentMemory with 15 Q&A pairs
├── vanna_setup.py       # Vanna 2.0 Agent initialisation
├── sql_validator.py     # SQL safety checks
├── chart_generator.py   # Plotly chart generation
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── README.md            # This file
└── RESULTS.md           # Test results for 20 benchmark questions
```

---

## Notes on Vanna 2.0

This project uses **Vanna 2.0** exclusively:

| Feature | Vanna 0.x (old) | Vanna 2.0 (used here) |
|---------|-----------------|----------------------|
| Training | `vn.train(ddl=...)` | `DemoAgentMemory.save_correct_tool_use()` |
| Vector store | ChromaDB required | Not needed |
| Execution | Manual runner | Built-in `SqliteRunner` |
| Architecture | Single class | Agent + ToolRegistry |
| LLM config | Constructor param | `GeminiLlmService` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `GOOGLE_API_KEY is not set` | Add your key to `.env` |
| `clinic.db not found` | Run `python setup_database.py` first |
| `ModuleNotFoundError: vanna` | Run `pip install -r requirements.txt` |
| 429 Too Many Requests | Wait 60 seconds (rate limit) |
| Empty response from agent | Rephrase question more specifically |
