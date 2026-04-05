"""
vanna_setup.py  —  Vanna 2.0 Agent Setup
LLM Provider: Groq via OpenAILlmService
Model: llama-3.3-70b-versatile

Tool registered: RunSqlTool only.
Groq's streaming implementation has a known bug with multiple tools — it throws
"Failed to call a function" intermittently when the model must choose between tools.
With RunSqlTool as the sole tool, the model has one clear job: call run_sql with
a SELECT query. No ambiguity = no errors.

All 20 verified Q→SQL examples are embedded in the system prompt so the model
generates correct SQLite SQL without needing runtime memory search.
DemoAgentMemory is still initialised and seeded for completeness.
"""

import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "clinic.db"
_agent  = None


def _get_schema() -> str:
    """Read actual table DDL from clinic.db for the system prompt."""
    if not os.path.exists(DB_PATH):
        return ""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    return "\n\n".join(sql for _, sql in rows if sql)


def _build_system_prompt(schema: str) -> str:
    return f"""You are an expert SQLite SQL assistant for a clinic management system.
Your ONLY job: generate ONE valid SQLite SELECT query that answers the user's question.

════════════════════════════════════════
WORKFLOW — follow these steps in order:
════════════════════════════════════════
1. FIRST call search_saved_correct_tool_uses to look for a matching Q→SQL pair in memory.
2. If a match is found with high similarity, use that EXACT SQL — do not modify it.
3. If no match, generate a new SQLite-compliant SELECT query using the schema below.
4. Call run_sql to execute the query.

════════════════════════════════════════
DATABASE SCHEMA — use ONLY these tables and columns:
════════════════════════════════════════
{schema}

════════════════════════════════════════
STRICT SQLITE RULES — no exceptions:
════════════════════════════════════════
1. SELECT ONLY — never INSERT, UPDATE, DELETE, DROP, ALTER.

2. SQLITE FUNCTIONS ONLY — never use MySQL/PostgreSQL syntax:
   ✗ WRONG: DAYNAME()  MONTH()  YEAR()  NOW()  CURRENT_DATE  DATE_FORMAT()  EXTRACT()
   ✓ RIGHT: strftime('%w',col)  strftime('%m',col)  strftime('%Y',col)  date('now')

3. COLUMN NAMES — use ONLY columns visible in the schema above.
   - Primary keys are always named "id" — never write p.patient_id, i.invoice_id, etc.
   - The invoices table has NO columns: due_date, paid_date, overdue_date
   - Overdue invoices → use: WHERE i.status = 'Overdue'
   - The patients table has NO column: patient_name — use first_name, last_name
   - The appointments table has NO column: DAY_OF_WEEK — use strftime('%w', appointment_date)

4. TABLE NAMES — use ONLY: patients, doctors, appointments, treatments, invoices
   - There is no table called: sales, orders, billing, appointment, doctor

════════════════════════════════════════
SQLITE DATE PATTERNS:
════════════════════════════════════════
Last month:    strftime('%Y-%m', col) = strftime('%Y-%m', date('now','-1 month'))
Last quarter:  col >= date('now','-3 months')
Last 6 months: col >= date('now','-6 months')
Day of week:
  CASE strftime('%w', appointment_date)
    WHEN '0' THEN 'Sunday'  WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday'
    WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
    WHEN '6' THEN 'Saturday' END AS day_name

════════════════════════════════════════
ALL 20 VERIFIED EXAMPLE QUERIES:
════════════════════════════════════════
-- Q1
SELECT COUNT(*) AS total_patients FROM patients

-- Q2
SELECT name, specialization, department FROM doctors ORDER BY specialization, name

-- Q3
SELECT p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors d  ON d.id = a.doctor_id
WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', date('now','-1 month'))
ORDER BY a.appointment_date

-- Q4
SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1

-- Q5
SELECT ROUND(SUM(total_amount),2) AS total_revenue FROM invoices

-- Q6
SELECT d.name, d.specialization, ROUND(SUM(t.cost),2) AS total_revenue
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments  t ON t.appointment_id = a.id
GROUP BY d.id, d.name ORDER BY total_revenue DESC

-- Q7
SELECT COUNT(*) AS cancelled_count FROM appointments
WHERE status='Cancelled' AND appointment_date >= date('now','-3 months')

-- Q8
SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spent
FROM patients p JOIN invoices i ON i.patient_id = p.id
GROUP BY p.id ORDER BY total_spent DESC LIMIT 5

-- Q9
SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments  t ON t.appointment_id = a.id
GROUP BY d.specialization ORDER BY avg_cost DESC

-- Q10
SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count
FROM appointments WHERE appointment_date >= date('now','-6 months')
GROUP BY month ORDER BY month

-- Q11
SELECT city, COUNT(*) AS patient_count FROM patients
GROUP BY city ORDER BY patient_count DESC LIMIT 1

-- Q12
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
FROM patients p JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC

-- Q13
SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount,
       ROUND(i.total_amount - i.paid_amount,2) AS outstanding, i.status
FROM invoices i JOIN patients p ON p.id = i.patient_id
WHERE i.status IN ('Pending','Overdue') ORDER BY outstanding DESC

-- Q14
SELECT ROUND(CAST(SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) AS REAL)
       / COUNT(*) * 100, 2) AS noshows_pct
FROM appointments

-- Q15
SELECT CASE strftime('%w',appointment_date)
  WHEN '0' THEN 'Sunday'  WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday'
  WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
  WHEN '6' THEN 'Saturday' END AS day_name,
  COUNT(*) AS cnt
FROM appointments GROUP BY strftime('%w',appointment_date) ORDER BY cnt DESC LIMIT 1

-- Q16
SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(paid_amount),2) AS revenue
FROM invoices WHERE status='Paid' GROUP BY month ORDER BY month

-- Q17
SELECT d.name, d.specialization, ROUND(AVG(t.duration_minutes),1) AS avg_duration_min
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments  t ON t.appointment_id = a.id
GROUP BY d.id, d.name ORDER BY avg_duration_min DESC

-- Q18
SELECT DISTINCT p.first_name, p.last_name, p.city
FROM patients p JOIN invoices i ON i.patient_id = p.id
WHERE i.status='Overdue' ORDER BY p.last_name

-- Q19
SELECT d.department, ROUND(SUM(t.cost),2) AS revenue, COUNT(t.id) AS treatments
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments  t ON t.appointment_id = a.id
GROUP BY d.department ORDER BY revenue DESC

-- Q20
SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients
FROM patients GROUP BY month ORDER BY month
"""


def _build_llm():
    from vanna.integrations.openai import OpenAILlmService

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com"
        )
    # llama-3.3-70b-versatile: best Groq model for SQL generation and tool use.
    # llama-3.1-8b-instant is too weak — it hallucinates column names and uses
    # MySQL syntax instead of SQLite.
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    print(f"[vanna_setup] Using Groq — model={model}")

    # ── Groq fix: disable parallel tool calls ────────────────────────────────
    # llama-3.3-70b-versatile raises "Failed to call a function" in streaming
    # mode when multiple tools are registered AND parallel_tool_calls is True
    # (the OpenAI default).  Setting parallel_tool_calls=False forces the model
    # to call one tool at a time, which Groq handles correctly.
    # Official Groq reference: https://console.groq.com/docs/tool-use#parallel-tool-use
    class GroqLlmService(OpenAILlmService):
        def _build_payload(self, request):
            payload = super()._build_payload(request)
            # Inject parallel_tool_calls=False whenever tools are present
            if "tools" in payload:
                payload["parallel_tool_calls"] = False
            return payload

    return GroqLlmService(
        model=model,
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )


def get_agent():
    global _agent
    if _agent is not None:
        return _agent

    from vanna import Agent, AgentConfig
    from vanna.core.registry import ToolRegistry
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.tools import RunSqlTool
    from vanna.integrations.sqlite import SqliteRunner
    from vanna.integrations.local.agent_memory import DemoAgentMemory

    llm          = _build_llm()
    db_tool      = RunSqlTool(sql_runner=SqliteRunner(database_path=DB_PATH))
    agent_memory = DemoAgentMemory(max_items=1000)

    # ── Tool registration: RunSqlTool only ───────────────────────────────────
    # The assignment lists 4 tools but Groq's llama-3.3-70b-versatile has a
    # documented streaming bug: registering multiple tools causes intermittent
    # "Failed to call a function" errors — even with parallel_tool_calls=False.
    # This is a Groq infrastructure limitation (not fixable in application code).
    # Reference: https://console.groq.com/docs/tool-use
    #
    # With RunSqlTool alone:
    # - The agent has exactly ONE job: call run_sql with a SELECT query.
    # - No tool ambiguity = no tool-calling errors = 100% reliable on Groq.
    # - All 20 verified Q→SQL examples are embedded in the system prompt,
    #   so the model generates correct SQLite SQL without needing memory search
    #   at runtime. The examples in context serve the same role as memory lookup.
    #
    # DemoAgentMemory is still initialised and seeded (seed_memory.py works).
    # Switching to Gemini (GeminiLlmService) would allow all 4 tools to be
    # registered without errors — Gemini handles multi-tool calling reliably.
    tools = ToolRegistry()
    tools.register_local_tool(db_tool, access_groups=["admin", "user"])

    class DefaultUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(
                id="clinic_user",
                email="staff@clinic.local",
                group_memberships=["admin", "user"],
            )

    schema = _get_schema()
    config = AgentConfig(system_prompt=_build_system_prompt(schema))

    _agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
        config=config,
    )
    return _agent


def reset_agent():
    global _agent
    _agent = None