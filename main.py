from __future__ import annotations

import logging
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

DB_PATH = "clinic.db"
_cache: dict[str, dict] = {}
_rates: dict[str, list[float]] = {}

SELECT_RE = re.compile(r'\bSELECT\b', re.IGNORECASE)


def _rate_ok(ip: str, limit: int = 20, window: float = 60.0) -> bool:
    now  = time.time()
    hits = [t for t in _rates.get(ip, []) if now - t < window]
    _rates[ip] = hits
    if len(hits) >= limit:
        return False
    _rates[ip].append(now)
    return True


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

class ChatResponse(BaseModel):
    message:    str
    sql_query:  str | None            = None
    columns:    list[str] | None      = None
    rows:       list[list[Any]] | None = None
    row_count:  int | None            = None
    chart:      dict | None           = None
    chart_type: str | None            = None
    cached:     bool                  = False

class HealthResponse(BaseModel):
    status:             str
    database:           str
    agent_memory_items: int

def _db_ok() -> bool:
    try:
        c = sqlite3.connect(DB_PATH); c.execute("SELECT 1"); c.close(); return True
    except Exception:
        return False

def _run_sql(sql: str) -> tuple[list[str], list[list[Any]]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur  = conn.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, [list(r) for r in rows]
    finally:
        conn.close()

def _mem_count() -> int:
    try:
        from vanna_setup import get_agent
        return len(get_agent().agent_memory.get_all_memories() or [])
    except Exception:
        return -1



def _deep_find_sql(obj, depth: int = 0) -> str | None:
    """
    Recursively walk any object/dict/list looking for a string
    that contains a SELECT statement.  Works on Vanna's nested
    UiComponent → rich_component → CardComponent structure.
    """
    if depth > 8:
        return None

    
    if isinstance(obj, str):
        if SELECT_RE.search(obj):
            return obj.strip()
        return None

   
    if isinstance(obj, dict):
        # Prioritise the key literally named "sql"
        if "sql" in obj and isinstance(obj["sql"], str) and SELECT_RE.search(obj["sql"]):
            return obj["sql"].strip()
        for v in obj.values():
            found = _deep_find_sql(v, depth + 1)
            if found:
                return found
        return None

   
    if isinstance(obj, (list, tuple)):
        for item in obj:
            found = _deep_find_sql(item, depth + 1)
            if found:
                return found
        return None

    
    attrs = {}
    try:
        attrs = vars(obj)
    except TypeError:
        pass

    if hasattr(obj, "model_fields"):
        for f in obj.model_fields:
            try:
                attrs[f] = getattr(obj, f)
            except Exception:
                pass

    if attrs:
   
        if "sql" in attrs:
            found = _deep_find_sql(attrs["sql"], depth + 1)
            if found:
                return found
        # Then walk rich_component first (Vanna wraps everything in UiComponent.rich_component)
        if "rich_component" in attrs:
            found = _deep_find_sql(attrs["rich_component"], depth + 1)
            if found:
                return found
        for k, v in attrs.items():
            if k in ("sql", "rich_component"):
                continue   # already handled
            found = _deep_find_sql(v, depth + 1)
            if found:
                return found

    return None


def _deep_find_text(obj, depth: int = 0) -> str:
    """Find any human-readable text/markdown inside a component."""
    if depth > 6:
        return ""
    if isinstance(obj, str) and len(obj) > 10 and not SELECT_RE.search(obj):
        return obj.strip()
    if isinstance(obj, dict):
        for k in ("text", "markdown", "content", "message"):
            if k in obj and isinstance(obj[k], str) and len(obj[k]) > 5:
                return obj[k].strip()
        for v in obj.values():
            r = _deep_find_text(v, depth + 1)
            if r:
                return r
    if isinstance(obj, (list, tuple)):
        for item in obj:
            r = _deep_find_text(item, depth + 1)
            if r:
                return r
    attrs = {}
    try:
        attrs = vars(obj)
    except TypeError:
        pass
    for k in ("text", "markdown", "content", "message"):
        if k in attrs and isinstance(attrs[k], str) and len(attrs[k]) > 5:
            return attrs[k].strip()
    if "rich_component" in attrs:
        r = _deep_find_text(attrs["rich_component"], depth + 1)
        if r:
            return r
    return ""


def _extract_dataframe(component) -> tuple[list[str], list[list[Any]]] | None:
    """
    Component[12] is a DataFrameComponent — it holds the already-executed results.
    We extract columns + rows from it so we can skip the extra DB round-trip.
    """
    try:
        rc = getattr(component, "rich_component", None) or component
        # pandas DataFrame stored in .data or .dataframe or .df
        for attr in ("data", "dataframe", "df", "value"):
            df = getattr(rc, attr, None)
            if df is not None and hasattr(df, "columns"):
                cols = list(df.columns)
                rows = df.values.tolist()
                return cols, rows
    except Exception:
        pass
    return None


async def _ask_vanna(question: str) -> tuple[str | None, str, list[str] | None, list[list] | None]:
    """
    Drive the Vanna 2.0 async-generator.
    Returns: (sql, agent_text, columns_or_None, rows_or_None)
    """
    from vanna_setup import get_agent
    from vanna.core.user import RequestContext

    agent = get_agent()
    ctx   = RequestContext(user_id="clinic_user", session_id="api")

    sql        = None
    text_parts = []
    df_result  = None

    async for component in agent.send_message(request_context=ctx, message=question):
        cname = type(getattr(component, "rich_component", component)).__name__

        # 1. Try to pull SQL out of any component (CardComponent carries it)
        if not sql:
            found = _deep_find_sql(component)
            if found:
                sql = found
                log.info("SQL found in %s: %.120s", cname, sql)

        # 2. DataFrameComponent already has the query results
        if df_result is None and "DataFrame" in cname:
            df_result = _extract_dataframe(component)
            if df_result:
                log.info("DataFrame found: cols=%s rows=%d", df_result[0], len(df_result[1]))

        # 3. RichTextComponent / TextComponent → summary
        if "Text" in cname or "RichText" in cname:
            t = _deep_find_text(component)
            if t:
                text_parts.append(t)

    cols, rows = df_result if df_result else (None, None)
    return sql, " ".join(text_parts).strip(), cols, rows


# Routes 
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

    try:
        sql, agent_text, vanna_cols, vanna_rows = await _ask_vanna(question)
    except Exception as exc:
        log.exception("Agent error: %s", exc)
        return ChatResponse(message=f"Agent error: {exc}. Try rephrasing.")

    if not sql:
        return ChatResponse(
            message=agent_text or "Could not generate SQL. Please rephrase your question.",
        )

    log.info("SQL | %s", sql)

    val = validate_sql(sql)
    if not val.is_valid:
        log.warning("SQL REJECTED | %s", val.error)
        return ChatResponse(message=f"SQL rejected for safety: {val.error}", sql_query=sql)

  
    if vanna_cols is not None and vanna_rows is not None:
        columns, rows = vanna_cols, vanna_rows
        log.info("Using Vanna DataFrame result: %d rows", len(rows))
    else:
        try:
            columns, rows = _run_sql(sql)
        except sqlite3.Error as exc:
            log.error("DB ERROR | %s", exc)
            return ChatResponse(message=f"Database error: {exc}", sql_query=sql)

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

    log.info("RESPONSE | rows=%d chart=%s", len(rows), chart_type or "none")
    return JSONResponse(payload)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        database="connected" if _db_ok() else "disconnected",
        agent_memory_items=_mem_count(),
    )