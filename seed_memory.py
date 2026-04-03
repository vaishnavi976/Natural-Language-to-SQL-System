"""
seed_memory.py
Pre-seeds Vanna 2.0 DemoAgentMemory with 15 high-quality Q&A SQL pairs.
Run after setup_database.py:  python seed_memory.py
"""

import asyncio
import uuid
from vanna_setup import get_agent

QA_PAIRS = [
    # ── Patient queries ───────────────────────────────────────────────────
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients",
    },
    {
        "question": "List all patients and their cities",
        "sql": (
            "SELECT first_name, last_name, city, gender "
            "FROM patients ORDER BY last_name, first_name"
        ),
    },
    {
        "question": "How many patients are from each city?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients GROUP BY city ORDER BY patient_count DESC"
        ),
    },
    {
        "question": "Which city has the most patients?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1"
        ),
    },
    {
        "question": "How many male and female patients do we have?",
        "sql": "SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender",
    },
    # ── Doctor queries ────────────────────────────────────────────────────
    {
        "question": "List all doctors and their specializations",
        "sql": (
            "SELECT name, specialization, department "
            "FROM doctors ORDER BY specialization, name"
        ),
    },
    {
        "question": "Which doctor has the most appointments?",
        "sql": (
            "SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count "
            "FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1"
        ),
    },
    {
        "question": "Show appointment count per doctor",
        "sql": (
            "SELECT d.name, d.specialization, COUNT(a.id) AS total_appointments "
            "FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id, d.name ORDER BY total_appointments DESC"
        ),
    },
    # ── Appointment queries ───────────────────────────────────────────────
    {
        "question": "How many appointments are there by status?",
        "sql": (
            "SELECT status, COUNT(*) AS count "
            "FROM appointments GROUP BY status ORDER BY count DESC"
        ),
    },
    {
        "question": "Show appointments for last month",
        "sql": (
            "SELECT a.id, p.first_name, p.last_name, d.name AS doctor_name, "
            "a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "WHERE strftime('%Y-%m', a.appointment_date) = "
            "strftime('%Y-%m', date('now', '-1 month')) "
            "ORDER BY a.appointment_date"
        ),
    },
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": (
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS appointment_count "
            "FROM appointments WHERE appointment_date >= date('now', '-6 months') "
            "GROUP BY month ORDER BY month"
        ),
    },
    # ── Financial queries ─────────────────────────────────────────────────
    {
        "question": "What is the total revenue from paid invoices?",
        "sql": (
            "SELECT ROUND(SUM(paid_amount), 2) AS total_revenue "
            "FROM invoices WHERE status = 'Paid'"
        ),
    },
    {
        "question": "Show revenue by doctor",
        "sql": (
            "SELECT d.name, d.specialization, ROUND(SUM(t.cost), 2) AS total_revenue "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "JOIN treatments t ON t.appointment_id = a.id "
            "GROUP BY d.id, d.name ORDER BY total_revenue DESC"
        ),
    },
    {
        "question": "Show unpaid invoices",
        "sql": (
            "SELECT p.first_name, p.last_name, i.invoice_date, "
            "i.total_amount, i.paid_amount, "
            "ROUND(i.total_amount - i.paid_amount, 2) AS outstanding, i.status "
            "FROM invoices i JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.status, outstanding DESC"
        ),
    },
    {
        "question": "Top 5 patients by total spending",
        "sql": (
            "SELECT p.first_name, p.last_name, p.city, "
            "ROUND(SUM(i.total_amount), 2) AS total_spent "
            "FROM patients p JOIN invoices i ON i.patient_id = p.id "
            "GROUP BY p.id, p.first_name, p.last_name "
            "ORDER BY total_spent DESC LIMIT 5"
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

    # ToolContext requires: user, conversation_id, request_id, agent_memory
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
        print(f"  [{i:>2}/{len(QA_PAIRS)}] {pair['question'][:65]}")

    print(f"\nDone! {len(QA_PAIRS)} pairs seeded successfully.")
    print("The agent will use these as examples when generating SQL.")


if __name__ == "__main__":
    asyncio.run(seed())