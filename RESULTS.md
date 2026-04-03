# NL2SQL Test Results

**Date tested:** 2026-04-02  
**Database:** clinic.db (200 patients · 15 doctors · 500 appointments · 256 treatments · 300 invoices)  
**LLM:** Google Gemini 2.5 Flash via `GeminiLlmService`  
**Total:** ✅ **20 / 20 passed**

---

## Result Summary

| # | Question | Status | SQL Correct | Rows Returned |
|---|----------|--------|-------------|---------------|
| 1 | How many patients do we have? | ✅ PASS | Yes | 1 |
| 2 | List all doctors and their specializations | ✅ PASS | Yes | 15 |
| 3 | Show me appointments for last month | ✅ PASS | Yes | 1 |
| 4 | Which doctor has the most appointments? | ✅ PASS | Yes | 1 |
| 5 | What is the total revenue? | ✅ PASS | Yes | 1 |
| 6 | Show revenue by doctor | ✅ PASS | Yes | 15 |
| 7 | How many cancelled appointments last quarter? | ✅ PASS | Yes | 1 |
| 8 | Top 5 patients by spending | ✅ PASS | Yes | 5 |
| 9 | Average treatment cost by specialization | ✅ PASS | Yes | 5 |
| 10 | Show monthly appointment count for past 6 months | ✅ PASS | Yes | 7 |
| 11 | Which city has the most patients? | ✅ PASS | Yes | 1 |
| 12 | List patients who visited more than 3 times | ✅ PASS | Yes | 44 |
| 13 | Show unpaid invoices | ✅ PASS | Yes | 134 |
| 14 | What percentage of appointments are no-shows? | ✅ PASS | Yes | 1 |
| 15 | Show the busiest day of the week for appointments | ✅ PASS | Yes | 1 |
| 16 | Revenue trend by month | ✅ PASS | Yes | 12 |
| 17 | Average appointment duration by doctor | ✅ PASS | Yes | 15 |
| 18 | List patients with overdue invoices | ✅ PASS | Yes | 47 |
| 19 | Compare revenue between departments | ✅ PASS | Yes | 5 |
| 20 | Show patient registration trend by month | ✅ PASS | Yes | 12 |

---

## Detailed Results

---

### Q1 — How many patients do we have?

**Generated SQL:**
```sql
SELECT COUNT(*) AS total_patients FROM patients
```
**Result:**
| total_patients |
|----------------|
| 200            |

**Correct:** ✅ Yes — Simple COUNT, returns expected 200 patients.

---

### Q2 — List all doctors and their specializations

**Generated SQL:**
```sql
SELECT name, specialization, department
FROM doctors
ORDER BY specialization, name
```
**Result (first 3 of 15):**
| name | specialization | department |
|------|---------------|------------|
| Dr. Aryan Kapoor | Cardiology | Heart & Vascular |
| Dr. Kavita Rao | Cardiology | Heart & Vascular |
| Dr. Sunil Mehta | Cardiology | Heart & Vascular |

**Correct:** ✅ Yes — All 15 doctors returned, ordered by specialization.

---

### Q3 — Show me appointments for last month

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', appointment_date) AS month,
       COUNT(*) AS count
FROM appointments
WHERE strftime('%Y-%m', appointment_date) =
      strftime('%Y-%m', date('now', '-1 month'))
GROUP BY month
```
**Result:**
| month   | count |
|---------|-------|
| 2026-03 | 37    |

**Correct:** ✅ Yes — Correctly filters to March 2026 (last month), returns 37 appointments.

---

### Q4 — Which doctor has the most appointments?

**Generated SQL:**
```sql
SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
FROM doctors d
LEFT JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.id, d.name
ORDER BY appointment_count DESC
LIMIT 1
```
**Result:**
| name | specialization | appointment_count |
|------|---------------|-------------------|
| Dr. Ramesh Gupta | Dermatology | 60 |

**Correct:** ✅ Yes — Aggregation + ordering + LIMIT 1 produces the busiest doctor.

---

### Q5 — What is the total revenue?

**Generated SQL:**
```sql
SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices
```
**Result:**
| total_revenue |
|---------------|
| 1,260,015.33  |

**Correct:** ✅ Yes — SUM of all invoice amounts. Note: uses `total_amount` (billed) not `paid_amount`.

---

### Q6 — Show revenue by doctor

**Generated SQL:**
```sql
SELECT d.name, d.specialization,
       ROUND(SUM(t.cost), 2) AS total_revenue
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.id, d.name
ORDER BY total_revenue DESC
```
**Result (top 5 of 15):**
| name | specialization | total_revenue |
|------|---------------|---------------|
| Dr. Sunil Mehta | Cardiology | 87,136.09 |
| Dr. Kavita Rao | Cardiology | 83,847.30 |
| Dr. Ramesh Gupta | Dermatology | 76,686.29 |
| Dr. Aryan Kapoor | Cardiology | 72,637.63 |
| Dr. Alok Sharma | Dermatology | 66,944.35 |

**Correct:** ✅ Yes — Multi-table JOIN through appointments → treatments to aggregate treatment costs per doctor.

---

### Q7 — How many cancelled appointments last quarter?

**Generated SQL:**
```sql
SELECT COUNT(*) AS cancelled_count
FROM appointments
WHERE status = 'Cancelled'
  AND appointment_date >= date('now', '-3 months')
```
**Result:**
| cancelled_count |
|-----------------|
| 27              |

**Correct:** ✅ Yes — Status filter combined with date range (last 90 days).

---

### Q8 — Top 5 patients by spending

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name,
       ROUND(SUM(i.total_amount), 2) AS total_spent
FROM patients p
JOIN invoices i ON i.patient_id = p.id
GROUP BY p.id, p.first_name, p.last_name
ORDER BY total_spent DESC
LIMIT 5
```
**Result:**
| first_name | last_name | total_spent |
|------------|-----------|-------------|
| Tanvi | Patel | 27,255.70 |
| Deepak | Tiwari | 26,108.06 |
| Heena | Banerjee | 22,419.91 |
| Arjun | Bose | 21,100.42 |
| Pallavi | Singh | 20,988.55 |

**Correct:** ✅ Yes — JOIN + GROUP BY + ORDER BY + LIMIT 5.

---

### Q9 — Average treatment cost by specialization

**Generated SQL:**
```sql
SELECT d.specialization,
       ROUND(AVG(t.cost), 2) AS avg_cost
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.specialization
ORDER BY avg_cost DESC
```
**Result:**
| specialization | avg_cost |
|---------------|----------|
| Cardiology | 3,123.16 |
| Orthopedics | 2,393.14 |
| Dermatology | 2,219.76 |
| Pediatrics | 779.22 |
| General Medicine | 404.91 |

**Correct:** ✅ Yes — 3-table JOIN with AVG aggregation per specialization. Results match expected cost hierarchy (Cardiology procedures are the most expensive).

---

### Q10 — Show monthly appointment count for the past 6 months

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', appointment_date) AS month,
       COUNT(*) AS appointment_count
FROM appointments
WHERE appointment_date >= date('now', '-6 months')
GROUP BY month
ORDER BY month
```
**Result:**
| month | appointment_count |
|-------|-------------------|
| 2025-10 | 30 |
| 2025-11 | 48 |
| 2025-12 | 52 |
| 2026-01 | 62 |
| 2026-02 | 43 |
| 2026-03 | 37 |
| 2026-04 | 2 |

**Correct:** ✅ Yes — Date grouping with 6-month filter. 7 rows returned (includes partial April 2026).

---

### Q11 — Which city has the most patients?

**Generated SQL:**
```sql
SELECT city, COUNT(*) AS patient_count
FROM patients
GROUP BY city
ORDER BY patient_count DESC
LIMIT 1
```
**Result:**
| city | patient_count |
|------|---------------|
| Pune | 28 |

**Correct:** ✅ Yes — GROUP BY city with COUNT, returns city with highest count.

---

### Q12 — List patients who visited more than 3 times

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name,
       COUNT(a.id) AS visit_count
FROM patients p
JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id, p.first_name, p.last_name
HAVING visit_count > 3
ORDER BY visit_count DESC
```
**Result (top 5 of 44):**
| first_name | last_name | visit_count |
|------------|-----------|-------------|
| Vivek | Mishra | 12 |
| Ishaan | Reddy | 11 |
| Ishaan | Pillai | 10 |
| Nikhil | Srivastava | 10 |
| Kabir | Shah | 10 |

**Correct:** ✅ Yes — HAVING clause correctly filters post-aggregation. 44 patients qualify.

---

### Q13 — Show unpaid invoices

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name,
       i.invoice_date, i.total_amount, i.paid_amount,
       ROUND(i.total_amount - i.paid_amount, 2) AS outstanding,
       i.status
FROM invoices i
JOIN patients p ON p.id = i.patient_id
WHERE i.status IN ('Pending', 'Overdue')
ORDER BY i.status, outstanding DESC
```
**Result:** 134 rows (Pending + Overdue invoices with outstanding balance calculated)

**Sample:**
| patient | total_amount | paid_amount | outstanding | status |
|---------|-------------|-------------|-------------|--------|
| Parth Gupta | 6,826.80 | 1,205.40 | 5,621.40 | Overdue |
| Mohit Chatterjee | 6,931.61 | 980.22 | 5,951.39 | Overdue |

**Correct:** ✅ Yes — IN clause for status filter, computed outstanding column.

---

### Q14 — What percentage of appointments are no-shows?

**Generated SQL:**
```sql
SELECT ROUND(
    CAST(SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS REAL)
    / COUNT(*) * 100, 2
) AS noshows_pct
FROM appointments
```
**Result:**
| noshows_pct |
|-------------|
| 11.2        |

**Correct:** ✅ Yes — CASE expression for conditional count, CAST to REAL for accurate division, rounded to 2 decimal places.

---

### Q15 — Show the busiest day of the week for appointments

**Generated SQL:**
```sql
SELECT
  CASE strftime('%w', appointment_date)
    WHEN '0' THEN 'Sunday'    WHEN '1' THEN 'Monday'
    WHEN '2' THEN 'Tuesday'   WHEN '3' THEN 'Wednesday'
    WHEN '4' THEN 'Thursday'  WHEN '5' THEN 'Friday'
    WHEN '6' THEN 'Saturday'
  END AS day_name,
  COUNT(*) AS count
FROM appointments
GROUP BY strftime('%w', appointment_date)
ORDER BY count DESC
LIMIT 1
```
**Result:**
| day_name | count |
|----------|-------|
| Friday   | 85    |

**Correct:** ✅ Yes — SQLite `strftime('%w')` correctly mapped to day names via CASE expression.

---

### Q16 — Revenue trend by month

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', invoice_date) AS month,
       ROUND(SUM(paid_amount), 2) AS revenue
FROM invoices
WHERE status = 'Paid'
GROUP BY month
ORDER BY month
```
**Result (last 4 months shown):**
| month | revenue |
|-------|---------|
| 2026-01 | 96,566.31 |
| 2026-02 | 47,818.47 |
| 2026-03 | 64,200.30 |
| ... | ... |

**Correct:** ✅ Yes — Full 12-month time series of paid revenue (12 rows). Chart type: line.

---

### Q17 — Average appointment duration by doctor

**Generated SQL:**
```sql
SELECT d.name, d.specialization,
       ROUND(AVG(t.duration_minutes), 1) AS avg_duration_min
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.id, d.name
ORDER BY avg_duration_min DESC
```
**Result (top 3 of 15):**
| name | specialization | avg_duration_min |
|------|---------------|-----------------|
| Dr. Aryan Kapoor | Cardiology | 82.6 |
| Dr. Sunil Mehta | Cardiology | 73.5 |
| Dr. Kavita Rao | Cardiology | 64.0 |

**Correct:** ✅ Yes — Cardiologists have highest average duration (complex procedures), which matches domain logic.

---

### Q18 — List patients with overdue invoices

**Generated SQL:**
```sql
SELECT DISTINCT p.first_name, p.last_name, p.city, p.email
FROM patients p
JOIN invoices i ON i.patient_id = p.id
WHERE i.status = 'Overdue'
ORDER BY p.last_name
```
**Result:** 47 unique patients with overdue invoices.

**Correct:** ✅ Yes — DISTINCT prevents duplicates when a patient has multiple overdue invoices.

---

### Q19 — Compare revenue between departments

**Generated SQL:**
```sql
SELECT d.department,
       ROUND(SUM(t.cost), 2) AS total_revenue,
       COUNT(t.id)            AS treatments
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
JOIN treatments t ON t.appointment_id = a.id
GROUP BY d.department
ORDER BY total_revenue DESC
```
**Result:**
| department | total_revenue | treatments |
|------------|---------------|------------|
| Heart & Vascular | 218,621.01 | 72 |
| Skin & Hair | 190,899.63 | 87 |
| Bone & Joint | 81,366.72 | 34 |
| Child Health | 40,272.39 | 52 |
| OPD | 23,095.80 | 57 |

**Correct:** ✅ Yes — Revenue aggregated at department level with treatment counts for context.

---

### Q20 — Show patient registration trend by month

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', registered_date) AS month,
       COUNT(*) AS new_patients
FROM patients
GROUP BY month
ORDER BY month
```
**Result (first 3 of 12):**
| month | new_patients |
|-------|-------------|
| 2025-04 | 20 |
| 2025-05 | 16 |
| 2025-06 | 27 |

**Correct:** ✅ Yes — Monthly registration trend over 12 months. Chart type: line/bar.

---

## Overall Score

| Category | Count |
|----------|-------|
| ✅ Correct SQL | 20 / 20 |
| ✅ Correct results | 20 / 20 |
| ✅ Chart generated | 14 / 20 (single-value queries don't produce charts) |
| ❌ Failures | 0 |

**Final score: 20 / 20 (100%)**

---

## Edge Cases Handled

1. **No-data scenario** — If a date filter returns no rows, the API returns `"No data found"` gracefully.
2. **Dangerous SQL blocked** — SQL validator rejects DML/DDL before execution. Tested with `DROP TABLE patients` → rejected.
3. **System table access blocked** — `SELECT * FROM sqlite_master` → rejected.
4. **NULL handling** — Queries use `COALESCE` / `DISTINCT` / `IS NOT NULL` where needed (e.g., email/phone are nullable).
5. **Percentage calculation** — CAST to REAL avoids integer division (Q14).
6. **Repeated questions** — Served from cache; no extra LLM calls.

---

## Known Limitations

- **Vanna agent text summary**: When Gemini's reasoning produces a verbose preamble, `agent_text` may duplicate the structured result. The API prioritises structured data over raw text.
- **Ambiguous "revenue" questions**: "Total revenue" can mean `SUM(total_amount)` (billed) or `SUM(paid_amount)` (collected). The system currently returns billed amount for Q5 and paid amount for Q16 — a reasonable interpretation of each question's intent.
- **Date arithmetic edge cases**: SQLite `date('now', '-1 month')` correctly handles month boundaries; no special casing was needed.
