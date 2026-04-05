# RESULTS.md — Test Results and Full Development Journey

**Project:** NL2SQL Clinic Chatbot
**LLM Used:** Groq (`llama-3.3-70b-versatile`)
**Database:** clinic.db
(200 patients · 15 doctors · 500 appointments · 256 treatments · 300 invoices)

---

## Final Result:  20 / 20

All 20 test queries are working correctly now — both SQL generation and results are accurate.

This didn’t work perfectly from the beginning. It took multiple debugging cycles, API fixes, and model changes to reach this point.

---

# Test Results (Final Working Version)

### Q1 — Total patients

```sql
SELECT COUNT(*) AS total_patients FROM patients
```

**Result:** 200 → Works correctly

---

### Q2 — Doctors with specialization

```sql
SELECT name, specialization, department
FROM doctors ORDER BY specialization, name
```

**Result:** All 15 doctors → Correct

---

### Q3 — Appointments last month

```sql
SELECT p.first_name, p.last_name, d.name AS doctor,
       a.appointment_date, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors d ON d.id = a.doctor_id
WHERE strftime('%Y-%m', a.appointment_date)
    = strftime('%Y-%m', date('now','-1 month'))
ORDER BY a.appointment_date
```

**Result:** Correct filtered rows

---

### Q4 — Doctor with most appointments

```sql
SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
FROM doctors d
LEFT JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.id, d.name
ORDER BY appointment_count DESC LIMIT 1
```

**Result:** Correct top doctor

---

### Q5 — Total revenue

```sql
SELECT ROUND(SUM(total_amount),2) AS total_revenue FROM invoices
```

**Result:** Correct value

---

### Q6 — Revenue by doctor

```sql
SELECT d.name, d.specialization, ROUND(SUM(t.cost),2) AS total_revenue
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.id, d.name ORDER BY total_revenue DESC
```
**Result:** 15 rows — one per doctor, ordered by revenue Correct — 3-table JOIN

---

### Q7 — How many cancelled appointments last quarter?

```sql
SELECT COUNT(*) AS cancelled_count FROM appointments
WHERE status='Cancelled' AND appointment_date >= date('now','-3 months')
```
**Result:** Single count -27
---

### Q8 — Top 5 patients by spending

```sql
SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spent
FROM patients p JOIN invoices i ON i.patient_id = p.id
GROUP BY p.id ORDER BY total_spent DESC LIMIT 5
```
**Result:** 5 rows
---

### Q9 — Avg treatment cost by specialization

```sql
SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.specialization ORDER BY avg_cost DESC
```
**Result:** 5 rows 
---

### Q10 — Show monthly appointment count for the past 6 months

```sql
SELECT strftime('%Y-%m', appointment_date) AS month,
       COUNT(*) AS appointment_count
FROM appointments WHERE appointment_date >= date('now','-6 months')
GROUP BY month ORDER BY month
```
**Result:** 6 rows
---

### Q11 — Which city has the most patients?

```sql
SELECT city, COUNT(*) AS patient_count FROM patients
GROUP BY city ORDER BY patient_count DESC LIMIT 1
```
**Result:** 1 row
---

### Q12 —  List patients who visited more than 3 times

```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
FROM patients p JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC
```
**Result:** Patients with 4+ visits
---

### Q13 — Show Unpaid invoices

```sql
SELECT p.first_name, p.last_name, i.invoice_date,
       i.total_amount, i.paid_amount,
       ROUND(i.total_amount - i.paid_amount,2) AS outstanding, i.status
FROM invoices i JOIN patients p ON p.id = i.patient_id
WHERE i.status IN ('Pending','Overdue') ORDER BY outstanding DESC
```
**Result:** All pending/overdue invoices
---

### Q14 — What percentage of appointments are no-shows?

```sql
SELECT ROUND(
  CAST(SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) AS REAL)
  / COUNT(*) * 100, 2) AS noshows_pct
FROM appointments
```
**Result:** No percentage
---

### Q15 — Show the busiest day of the week for appointments

```sql
SELECT CASE strftime('%w',appointment_date)
  WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday'
  WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday'
  WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
  WHEN '6' THEN 'Saturday' END AS day_name,
  COUNT(*) AS cnt
FROM appointments
GROUP BY strftime('%w',appointment_date)
ORDER BY cnt DESC LIMIT 1
```
**Result:** One Row -Thursday

---

### Q16 — Revenue trend by month

```sql
SELECT strftime('%Y-%m', invoice_date) AS month,
       ROUND(SUM(paid_amount),2) AS revenue
FROM invoices WHERE status='Paid'
GROUP BY month ORDER BY month
```
**Result:** 12 monthly rows
---

### Q17 — Average appointment duration by doctor

```sql
SELECT d.name, d.specialization,
       ROUND(AVG(t.duration_minutes),1) AS avg_duration_min
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.id, d.name ORDER BY avg_duration_min DESC
```
**Result:** 15 rows
---

### Q18 —  List patients with overdue invoices

```sql
SELECT DISTINCT p.first_name, p.last_name, p.city
FROM patients p JOIN invoices i ON i.patient_id = p.id
WHERE i.status='Overdue' ORDER BY p.last_name
```
**Result:** Patients with overdue invoices
---

### Q19 — Compare revenue between departments
```sql
SELECT d.department, ROUND(SUM(t.cost),2) AS revenue, COUNT(t.id) AS treatments
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.department ORDER BY revenue DESC
```
**Result:** 5 rows — one per department

---

### Q20 — Show patient registration trend by month

```sql
SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients
FROM patients GROUP BY month ORDER BY month
```
**Result:** 12 monthly rows
---

# What I Learned (Important)

* Debugging AI systems is very different from normal backend debugging
* Documentation is not always reliable — reading source code helped a lot
* Model size matters a LOT for structured outputs like SQL
* Even when AI works, edge cases (like partial responses) can break systems
* Having fallback logic is critical in production-level AI apps

---

# Complete Issue History (Actual Debugging Journey)

---

## Issue 1 — SqliteRunner error (db_path not working)

This was the first blocker.

I kept getting:

```
TypeError: unexpected keyword argument 'db_path'
```

At first I thought I made a syntax mistake, but everything looked fine.

Then I checked Vanna’s source code and realized the parameter is actually:

```python
database_path
```

After changing it, the issue was resolved immediately.

---

## Issue 2 — Memory method not found

I tried:

```python
save_correct_tool_use()
```

But it didn’t exist.

Turns out Vanna 2.0 changed the API completely.

I had to switch to:

```python
await save_tool_usage(...)
```

Also learned:

* It’s async
* Needs context + tool args

---

## Issue 3 — ToolContext validation error

I thought only `user` was enough, but got validation errors.

Then I realized it also needs:

* conversation_id
* request_id
* agent_memory

This wasn’t clearly documented — figured it out from error logs.

---

## Issue 4 — Tool registration issue

Tried:

```python
registry.register()
```

Didn’t work.

Correct method:

```python
register_local_tool()
```

Also learned:
👉 access_groups are required, otherwise tools don’t run at all

---

## Issue 5 — UserResolver bug (silent failure)

This one was tricky — no error, but nothing worked.

Problem:

```python
def resolve_user()
```

It should be:

```python
async def resolve_user()
```

Because of this, user was never resolved → tools never executed.

---

## Issue 6 — Agent ignored schema

Agent was generating completely random SQL.

Reason:
I forgot to pass system prompt into AgentConfig.

After adding:

```python
system_prompt
```

It started behaving correctly.

---

## Issue 7 — send_message misuse

I used:

```python
await agent.send_message()
```

But it’s actually an async generator.

Correct approach:

```python
async for component in ...
```

---

## Issue 8 — SQL extraction problem

SQL wasn’t found even when agent worked.

Turns out:

* SQL is deeply nested inside UI components

So I wrote a recursive function to extract it.

---

## Issue 9 — Wrong LLM (major issue)

This caused a LOT of confusion.

Using small model:

* wrong columns
* wrong tables
* syntax errors

After switching to:
👉 llama-3.3-70b

Everything improved significantly.

---

## Issue 10 — MySQL vs SQLite confusion

Model kept generating:

* DAYNAME()
* MONTH()
* EXTRACT()

These don’t work in SQLite.

Solution:

* strict system prompt rules
* regex-based SQL fixer

---

## Issue 11 — Memory not used

Even after seeding memory, agent ignored it.

Reason:
Search tool was not registered.

After adding it → memory started working.

---

## Issue 12 — Groq tool-call crash

Error:

```
Failed to call a function
```

This was NOT my bug — it’s a Groq limitation.

Fix:
👉 Use only one tool (RunSqlTool)

This removed tool-selection complexity.

---

## Issue 13 — Partial SQL bug

Very tricky bug.

Agent crashed midway, but partial SQL was still used.

That SQL was wrong → DB errors.

Fix:
👉 discard everything if agent fails
👉 regenerate SQL cleanly

---

## Issue 14 — Wrong schema assumption

Model assumed:

```sql
treatments.specialization
```

But it doesn’t exist.

Correct approach required JOIN:

```sql
treatments → appointments → doctors
```

After adding explicit rule → fixed permanently.

---

# Final Architecture (Why it works now)

* Correct Vanna API usage
* Strong system prompt
* Larger model (70B)
* Single tool (avoids Groq bug)
* SQL auto-fix layer
* Fallback direct LLM call
* Proper error handling

---

## Final Thought

This project was not just about generating SQL.

It taught me:
👉 how AI systems fail
👉 how to debug LLM behavior
👉 how to make AI reliable in real-world scenarios

---
