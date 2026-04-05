from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from chart_generator import generate_chart
from sql_validator import validate_sql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("nl2sql")

app = FastAPI(title="NL2SQL Clinic Chatbot", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["GET", "POST"], allow_headers=["*"],
)

DB_PATH   = "clinic.db"
_cache: dict[str, dict] = {}
_rates: dict[str, list[float]] = {}
SELECT_RE = re.compile(r'\bSELECT\b', re.IGNORECASE)


# ── Rate limiter ──────────────────────────────────────────────────────────────
def _rate_ok(ip: str, limit: int = 20, window: float = 60.0) -> bool:
    now  = time.time()
    hits = [t for t in _rates.get(ip, []) if now - t < window]
    _rates[ip] = hits
    if len(hits) >= limit:
        return False
    _rates[ip].append(now)
    return True


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

class ChatResponse(BaseModel):
    message:    str
    sql_query:  str | None             = None
    columns:    list[str] | None       = None
    rows:       list[list[Any]] | None = None
    row_count:  int | None             = None
    chart:      dict | None            = None
    chart_type: str | None             = None
    cached:     bool                   = False
    error_type: str | None             = None

class HealthResponse(BaseModel):
    status:             str
    database:           str
    llm_provider:       str
    agent_memory_items: int


# ── DB helpers ────────────────────────────────────────────────────────────────
def _db_ok() -> bool:
    try:
        c = sqlite3.connect(DB_PATH); c.execute("SELECT 1"); c.close(); return True
    except Exception:
        return False

def _run_sql(sql: str) -> tuple[list[str], list[list[Any]]]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        cur  = conn.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, [list(r) for r in rows]
    finally:
        conn.close()

def _get_schema() -> str:
    if not os.path.exists(DB_PATH):
        return ""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name IN ('patients','doctors','appointments','treatments','invoices')"
    ).fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows if r[0])

def _mem_count() -> int:
    try:
        from vanna_setup import get_agent
        mems = get_agent().agent_memory.get_all_memories()
        return len(mems) if mems else 0
    except Exception:
        return -1

def _llm_provider() -> str:
    return "groq/llama-3.3-70b-versatile"


# ── Component tree walkers ────────────────────────────────────────────────────
def _deep_find_sql(obj, depth: int = 0) -> str | None:
    if depth > 8: return None
    if isinstance(obj, str):
        return obj.strip() if SELECT_RE.search(obj) else None
    if isinstance(obj, dict):
        if "sql" in obj and isinstance(obj["sql"], str) and SELECT_RE.search(obj["sql"]):
            return obj["sql"].strip()
        for v in obj.values():
            r = _deep_find_sql(v, depth + 1)
            if r: return r
        return None
    if isinstance(obj, (list, tuple)):
        for item in obj:
            r = _deep_find_sql(item, depth + 1)
            if r: return r
        return None
    attrs: dict = {}
    try: attrs = vars(obj)
    except TypeError: pass
    if hasattr(obj, "model_fields"):
        for f in obj.model_fields:
            try: attrs[f] = getattr(obj, f)
            except Exception: pass
    for key in ("sql", "rich_component"):
        if key in attrs:
            r = _deep_find_sql(attrs[key], depth + 1)
            if r: return r
    for k, v in attrs.items():
        if k in ("sql", "rich_component"): continue
        r = _deep_find_sql(v, depth + 1)
        if r: return r
    return None

def _deep_find_text(obj, depth: int = 0) -> str:
    if depth > 6: return ""
    if isinstance(obj, str) and len(obj) > 10 and not SELECT_RE.search(obj):
        return obj.strip()
    if isinstance(obj, dict):
        for k in ("text", "markdown", "content", "message"):
            if k in obj and isinstance(obj[k], str) and len(obj[k]) > 5:
                return obj[k].strip()
        for v in obj.values():
            r = _deep_find_text(v, depth + 1)
            if r: return r
    if isinstance(obj, (list, tuple)):
        for item in obj:
            r = _deep_find_text(item, depth + 1)
            if r: return r
    attrs: dict = {}
    try: attrs = vars(obj)
    except TypeError: pass
    for k in ("text", "markdown", "content", "message"):
        if k in attrs and isinstance(attrs[k], str) and len(attrs[k]) > 5:
            return attrs[k].strip()
    if "rich_component" in attrs:
        r = _deep_find_text(attrs["rich_component"], depth + 1)
        if r: return r
    return ""

def _extract_dataframe(component) -> tuple[list, list] | None:
    try:
        rc = getattr(component, "rich_component", None) or component
        for attr in ("data", "dataframe", "df", "value"):
            df = getattr(rc, attr, None)
            if df is not None and hasattr(df, "columns"):
                return list(df.columns), df.values.tolist()
    except Exception:
        pass
    return None


# ── SQL auto-fixer ─────────────────────────────────────────────────────────────
_SQL_FIXES = [
    (re.compile(r'\bDAYNAME\s*\(([^)]+)\)', re.IGNORECASE),
     lambda m: (
         f"CASE strftime('%w',{m.group(1)}) "
         "WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' "
         "WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' "
         "WHEN '6' THEN 'Saturday' END"
     )),
    (re.compile(r'\bMONTH\s*\(([^)]+)\)', re.IGNORECASE),
     lambda m: f"CAST(strftime('%m',{m.group(1)}) AS INTEGER)"),
    (re.compile(r'\bYEAR\s*\(([^)]+)\)', re.IGNORECASE),
     lambda m: f"CAST(strftime('%Y',{m.group(1)}) AS INTEGER)"),
    (re.compile(r'\bNOW\s*\(\s*\)', re.IGNORECASE),
     lambda m: "datetime('now')"),
    (re.compile(r'\bCURRENT_DATE\b', re.IGNORECASE),
     lambda m: "date('now')"),
    (re.compile(r'\bAND\s+(?:\w+\.)?paid_date\s+IS\s+NULL\b', re.IGNORECASE),
     lambda m: ""),
    (re.compile(r'\bAND\s+(?:\w+\.)?due_date\s*[<>=][^,\n)]+', re.IGNORECASE),
     lambda m: ""),
    (re.compile(r'\bWHERE\s+(?:\w+\.)?paid_date\s+IS\s+NULL\b', re.IGNORECASE),
     lambda m: "WHERE 1=1"),
    (re.compile(r'\bi\.due_date\s*<\s*\S+', re.IGNORECASE),
     lambda m: "i.status = 'Overdue'"),
]

def _fix_sql(sql: str) -> str:
    """Convert MySQL/PostgreSQL syntax to SQLite equivalents."""
    fixed = sql
    for pattern, replacement in _SQL_FIXES:
        fixed = pattern.sub(replacement, fixed)
    fixed = re.sub(
        r'\b([a-z])\.(patient_id|invoice_id|appointment_id|treatment_id)\b(?!\s*=)',
        lambda m: f"{m.group(1)}.id",
        fixed, flags=re.IGNORECASE,
    )
    if fixed != sql:
        log.info("SQL auto-fixed: %s", fixed[:150])
    return fixed


# ── Direct Groq call — no tool-calling ────────────────────────────────────────
# Used when the Vanna agent throws "Failed to call a function".
# The same LLM (llama-3.3-70b-versatile) still decides the SQL.
# No tool-calling = no streaming crash. AI is still the decision-maker.
_DIRECT_SYSTEM = """\
You are a SQLite expert. Output ONE raw SQLite SELECT query — nothing else.
No markdown, no backticks, no explanation. Just the SQL.

STRICT RULES:
- Only SQLite syntax. Never MySQL/PostgreSQL.
- Only these tables: patients, doctors, appointments, treatments, invoices
- Primary keys are always "id" — never patient_id, invoice_id as self-ref.
- invoices has NO columns: due_date, paid_date → use status='Overdue' instead
- patients has NO column: patient_name → use first_name, last_name
- appointments has NO column: DAY_OF_WEEK → use strftime('%w', appointment_date)
- treatments has NO column: specialization → JOIN doctors to get specialization
- Date functions: strftime('%Y-%m', col), date('now'), date('now','-N months')

SCHEMA:
{schema}

EXAMPLES:
Q: How many patients do we have?
A: SELECT COUNT(*) AS total_patients FROM patients

Q: Which doctor has the most appointments?
A: SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1

Q: What is the total revenue?
A: SELECT ROUND(SUM(total_amount),2) AS total_revenue FROM invoices

Q: Show revenue by doctor
A: SELECT d.name, d.specialization, ROUND(SUM(t.cost),2) AS total_revenue FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.id, d.name ORDER BY total_revenue DESC

Q: How many cancelled appointments last quarter?
A: SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status='Cancelled' AND appointment_date >= date('now','-3 months')

Q: Top 5 patients by spending
A: SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spent FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id ORDER BY total_spent DESC LIMIT 5

Q: Average treatment cost by specialization
A: SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.specialization ORDER BY avg_cost DESC

Q: Show monthly appointment count for the past 6 months
A: SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now','-6 months') GROUP BY month ORDER BY month

Q: Which city has the most patients?
A: SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1

Q: List patients who visited more than 3 times
A: SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC

Q: Show unpaid invoices
A: SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount, ROUND(i.total_amount - i.paid_amount,2) AS outstanding, i.status FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY outstanding DESC

Q: What percentage of appointments are no-shows?
A: SELECT ROUND(CAST(SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 2) AS noshows_pct FROM appointments

Q: Show the busiest day of the week for appointments
A: SELECT CASE strftime('%w',appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday' END AS day_name, COUNT(*) AS cnt FROM appointments GROUP BY strftime('%w',appointment_date) ORDER BY cnt DESC LIMIT 1

Q: Revenue trend by month
A: SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(paid_amount),2) AS revenue FROM invoices WHERE status='Paid' GROUP BY month ORDER BY month

Q: Average appointment duration by doctor
A: SELECT d.name, d.specialization, ROUND(AVG(t.duration_minutes),1) AS avg_duration_min FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.id, d.name ORDER BY avg_duration_min DESC

Q: List patients with overdue invoices
A: SELECT DISTINCT p.first_name, p.last_name, p.city FROM patients p JOIN invoices i ON i.patient_id = p.id WHERE i.status='Overdue' ORDER BY p.last_name

Q: Compare revenue between departments
A: SELECT d.department, ROUND(SUM(t.cost),2) AS revenue, COUNT(t.id) AS treatments FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.department ORDER BY revenue DESC

Q: Show patient registration trend by month
A: SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month

Q: List all doctors and their specializations
A: SELECT name, specialization, department FROM doctors ORDER BY specialization, name

Q: Show me appointments for last month
A: SELECT p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', date('now','-1 month')) ORDER BY a.appointment_date
"""

async def _direct_sql(question: str) -> str | None:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    schema = _get_schema()

    def _call() -> str | None:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": _DIRECT_SYSTEM.format(schema=schema)},
                {"role": "user",   "content": question},
            ],
            max_tokens=512,
            temperature=0,
            # No `tools` key → no tool-calling → no "Failed to call a function"
        )
        raw = resp.choices[0].message.content or ""
        # Strip markdown fences if the model adds them despite instructions
        raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        return raw if SELECT_RE.search(raw) else None

    try:
        sql = await asyncio.get_event_loop().run_in_executor(None, _call)
        if sql:
            log.info("DIRECT SQL: %.150s", sql)
        return sql
    except Exception as exc:
        log.error("Direct Groq call failed: %s", exc)
        return None


# ── Rate-limit error ──────────────────────────────────────────────────────────
class RateLimitError(Exception):
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit — retry after {retry_after}s")


# ── Vanna agent call ──────────────────────────────────────────────────────────
async def _ask_vanna(question: str) -> tuple[str | None, str, list | None, list | None]:
    from vanna_setup import get_agent
    from vanna.core.user import RequestContext

    agent = get_agent()

    for attempt in range(2):
        ctx = RequestContext(user_id="clinic_user", session_id=f"api-{attempt}")
        sql, text_parts, df_result = None, [], None

        try:
            async for component in agent.send_message(
                request_context=ctx, message=question
            ):
                cname = type(getattr(component, "rich_component", component)).__name__

                if not sql:
                    found = _deep_find_sql(component)
                    if found:
                        sql = found
                        log.info("AGENT SQL: %.150s", sql)

                if df_result is None and "DataFrame" in cname:
                    df_result = _extract_dataframe(component)

                if "Text" in cname or "RichText" in cname:
                    t = _deep_find_text(component)
                    if t:
                        text_parts.append(t)

            cols, rows = df_result if df_result else (None, None)
            return sql, " ".join(text_parts).strip(), cols, rows

        except Exception as exc:
            err = str(exc)
            is_rate = (
                "429" in err or "RESOURCE_EXHAUSTED" in err
                or "rate limit" in err.lower() or "too many requests" in err.lower()
            )
            if is_rate:
                wait = 45
                m = re.search(r'retry in (\d+)', err, re.IGNORECASE)
                if m:
                    wait = int(m.group(1)) + 3
                if attempt == 0:
                    log.warning("Rate limit — waiting %ds then retrying...", wait)
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(wait) from exc
            raise

    return None, "", None, None


# ── Route: POST /chat ─────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    ip = request.client.host if request.client else "unknown"
    if not _rate_ok(ip):
        raise HTTPException(429, "Rate limit exceeded. Please wait.")

    question  = body.question.strip()
    cache_key = question.lower()
    log.info("QUESTION | ip=%s | %r", ip, question)

    if cache_key in _cache:
        log.info("CACHE HIT")
        return JSONResponse({**_cache[cache_key], "cached": True})

    # ── Primary: Vanna 2.0 agent ──────────────────────────────────────────────
    sql        = None
    agent_text = ""
    vanna_cols = None
    vanna_rows = None
    via        = "agent"

    try:
        sql, agent_text, vanna_cols, vanna_rows = await _ask_vanna(question)
        log.info("Agent completed | sql_found=%s", bool(sql))

    except RateLimitError as exc:
        log.warning("Rate limit exhausted. retry_after=%ds", exc.retry_after)
        return ChatResponse(
            message=(
                f"⚠️ Groq API rate limit reached. "
                f"Please wait {exc.retry_after} seconds and try again."
            ),
            error_type="rate_limit",
        )

    except Exception as exc:
        log.warning("Agent exception (discarding partial SQL, using direct call): %s", exc)
        sql        = None   # ← critical: throw away any partial SQL
        agent_text = ""
        vanna_cols = None
        vanna_rows = None
        via        = "direct"
    if via == "direct" or not sql:
        if via != "direct":
            via = "direct"
        log.info("Using direct Groq call for: %r", question)
        sql = await _direct_sql(question)

    if not sql:
        return ChatResponse(
            message="Could not generate SQL for this question. Please try rephrasing.",
        )

    # ── SQLite compatibility fixes ────────────────────────────────────────────
    sql = _fix_sql(sql)
    log.info("SQL [via=%s] | %s", via, sql)

    # ── Security validation ───────────────────────────────────────────────────
    val = validate_sql(sql)
    if not val.is_valid:
        log.warning("SQL REJECTED | %s", val.error)
        return ChatResponse(message=f"SQL rejected: {val.error}", sql_query=sql)

    # ── Execute ───────────────────────────────────────────────────────────────
    if vanna_cols is not None and vanna_rows is not None:
        columns, rows = vanna_cols, vanna_rows
        log.info("Using Vanna DataFrame: %d rows", len(rows))
    else:
        try:
            columns, rows = _run_sql(sql)
        except sqlite3.Error as db_exc:
            log.error("DB ERROR [via=%s] | %s | sql=%.200s", via, db_exc, sql)
            if via == "agent":
                log.info("Agent SQL failed DB execution — trying direct Groq call")
                via       = "direct"
                retry_sql = await _direct_sql(question)

                if retry_sql:
                    retry_sql = _fix_sql(retry_sql)
                    val2 = validate_sql(retry_sql)
                    if val2.is_valid:
                        try:
                            columns, rows = _run_sql(retry_sql)
                            sql = retry_sql
                            log.info("Direct call recovery succeeded: %d rows", len(rows))
                        except sqlite3.Error as exc2:
                            log.error("Direct call recovery also failed: %s", exc2)
                            return ChatResponse(
                                message=f"Database error: {exc2}",
                                sql_query=retry_sql,
                                error_type="db_error",
                            )
                    else:
                        return ChatResponse(
                            message=f"SQL rejected: {val2.error}",
                            sql_query=retry_sql,
                        )
                else:
                    return ChatResponse(
                        message=f"Database error: {db_exc}",
                        sql_query=sql, error_type="db_error",
                    )
            else:
                return ChatResponse(
                    message=f"Database error: {db_exc}",
                    sql_query=sql, error_type="db_error",
                )

    if not rows:
        return ChatResponse(
            message="Query returned no results.",
            sql_query=sql, columns=columns, rows=[], row_count=0,
        )

    chart, chart_type = generate_chart(columns, rows, question)

    message = (
        agent_text
        or (f"Result: {rows[0][0]}" if len(rows) == 1 and len(columns) == 1
            else f"Found {len(rows)} result{'s' if len(rows) != 1 else ''} for: \"{question}\".")
    )

    payload = {
        "message":    message,
        "sql_query":  sql,
        "columns":    columns,
        "rows":       rows,
        "row_count":  len(rows),
        "chart":      chart,
        "chart_type": chart_type,
        "cached":     False,
    }

    if len(_cache) >= 100:
        del _cache[next(iter(_cache))]
    _cache[cache_key] = payload

    log.info("RESPONSE [via=%s] | rows=%d chart=%s", via, len(rows), chart_type or "none")
    return JSONResponse(payload)


# ── Route: GET /health ────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        database="connected" if _db_ok() else "disconnected",
        llm_provider=_llm_provider(),
        agent_memory_items=_mem_count(),
    )