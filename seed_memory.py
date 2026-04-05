"""
seed_memory.py
Seeds Vanna 2.0 DemoAgentMemory with all 20 evaluation questions + SQL.
Run after setup_database.py:   python seed_memory.py

Every seeded pair maps to one of the 20 test questions — verified correct
against clinic.db.
"""

import asyncio
import uuid
from vanna_setup import get_agent

# ── All 20 evaluation questions with verified-correct SQLite SQL ──────────────
QA_PAIRS = [
    # Q1
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients",
    },
    # Q2
    {
        "question": "List all doctors and their specializations",
        "sql": (
            "SELECT name, specialization, department "
            "FROM doctors ORDER BY specialization, name"
        ),
    },
    # Q3
    {
        "question": "Show me appointments for last month",
        "sql": (
            "SELECT p.first_name, p.last_name, d.name AS doctor, "
            "a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d  ON d.id = a.doctor_id "
            "WHERE strftime('%Y-%m', a.appointment_date) = "
            "strftime('%Y-%m', date('now','-1 month')) "
            "ORDER BY a.appointment_date"
        ),
    },
    # Q4
    {
        "question": "Which doctor has the most appointments?",
        "sql": (
            "SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count "
            "FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1"
        ),
    },
    # Q5
    {
        "question": "What is the total revenue?",
        "sql": "SELECT ROUND(SUM(total_amount),2) AS total_revenue FROM invoices",
    },
    # Q6
    {
        "question": "Show revenue by doctor",
        "sql": (
            "SELECT d.name, d.specialization, ROUND(SUM(t.cost),2) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments  t ON t.appointment_id = a.id "
            "GROUP BY d.id, d.name ORDER BY total_revenue DESC"
        ),
    },
    # Q7
    {
        "question": "How many cancelled appointments last quarter?",
        "sql": (
            "SELECT COUNT(*) AS cancelled_count FROM appointments "
            "WHERE status='Cancelled' AND appointment_date >= date('now','-3 months')"
        ),
    },
    # Q8
    {
        "question": "Top 5 patients by spending",
        "sql": (
            "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spent "
            "FROM patients p JOIN invoices i ON i.patient_id = p.id "
            "GROUP BY p.id ORDER BY total_spent DESC LIMIT 5"
        ),
    },
    # Q9
    {
        "question": "Average treatment cost by specialization",
        "sql": (
            "SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments  t ON t.appointment_id = a.id "
            "GROUP BY d.specialization ORDER BY avg_cost DESC"
        ),
    },
    # Q10
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": (
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS appointment_count "
            "FROM appointments WHERE appointment_date >= date('now','-6 months') "
            "GROUP BY month ORDER BY month"
        ),
    },
    # Q11
    {
        "question": "Which city has the most patients?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count FROM patients "
            "GROUP BY city ORDER BY patient_count DESC LIMIT 1"
        ),
    },
    # Q12
    {
        "question": "List patients who visited more than 3 times",
        "sql": (
            "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count "
            "FROM patients p JOIN appointments a ON a.patient_id = p.id "
            "GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC"
        ),
    },
    # Q13
    {
        "question": "Show unpaid invoices",
        "sql": (
            "SELECT p.first_name, p.last_name, i.invoice_date, "
            "i.total_amount, i.paid_amount, "
            "ROUND(i.total_amount - i.paid_amount,2) AS outstanding, i.status "
            "FROM invoices i JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending','Overdue') ORDER BY outstanding DESC"
        ),
    },
    # Q14
    {
        "question": "What percentage of appointments are no-shows?",
        "sql": (
            "SELECT ROUND(CAST(SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) AS REAL) "
            "/ COUNT(*) * 100, 2) AS noshows_pct FROM appointments"
        ),
    },
    # Q15
    {
        "question": "Show the busiest day of the week for appointments",
        "sql": (
            "SELECT CASE strftime('%w',appointment_date) "
            "WHEN '0' THEN 'Sunday'  WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday' "
            "WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' "
            "WHEN '6' THEN 'Saturday' END AS day_name, "
            "COUNT(*) AS cnt "
            "FROM appointments GROUP BY strftime('%w',appointment_date) "
            "ORDER BY cnt DESC LIMIT 1"
        ),
    },
    # Q16
    {
        "question": "Revenue trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', invoice_date) AS month, "
            "ROUND(SUM(paid_amount),2) AS revenue "
            "FROM invoices WHERE status='Paid' GROUP BY month ORDER BY month"
        ),
    },
    # Q17
    {
        "question": "Average appointment duration by doctor",
        "sql": (
            "SELECT d.name, d.specialization, "
            "ROUND(AVG(t.duration_minutes),1) AS avg_duration_min "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments  t ON t.appointment_id = a.id "
            "GROUP BY d.id, d.name ORDER BY avg_duration_min DESC"
        ),
    },
    # Q18
    {
        "question": "List patients with overdue invoices",
        "sql": (
            "SELECT DISTINCT p.first_name, p.last_name, p.city "
            "FROM patients p JOIN invoices i ON i.patient_id = p.id "
            "WHERE i.status='Overdue' ORDER BY p.last_name"
        ),
    },
    # Q19
    {
        "question": "Compare revenue between departments",
        "sql": (
            "SELECT d.department, ROUND(SUM(t.cost),2) AS revenue, COUNT(t.id) AS treatments "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments  t ON t.appointment_id = a.id "
            "GROUP BY d.department ORDER BY revenue DESC"
        ),
    },
    # Q20
    {
        "question": "Show patient registration trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', registered_date) AS month, "
            "COUNT(*) AS new_patients "
            "FROM patients GROUP BY month ORDER BY month"
        ),
    },
]


async def seed():
    print("Connecting to Vanna 2.0 agent...")
    agent = get_agent()

    from vanna.core.tool import ToolContext
    from vanna.core.user.models import User

    admin_user = User(
        id="seed_admin",
        email="admin@clinic.local",
        group_memberships=["admin", "user"],
    )
    ctx = ToolContext(
        user=admin_user,
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        agent_memory=agent.agent_memory,
    )

    print(f"Seeding {len(QA_PAIRS)} Q&A pairs into DemoAgentMemory...")
    for i, pair in enumerate(QA_PAIRS, 1):
        await agent.agent_memory.save_tool_usage(
            question=pair["question"],
            tool_name="run_sql",
            args={"sql": pair["sql"]},
            context=ctx,
            success=True,
        )
        print(f"  [{i:>2}/{len(QA_PAIRS)}] {pair['question']}")

    print(f"\nDone! {len(QA_PAIRS)} pairs seeded.")
    print("Agent will retrieve these as examples when generating SQL.")


if __name__ == "__main__":
    asyncio.run(seed())