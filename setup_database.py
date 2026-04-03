"""
setup_database.py
Creates the clinic SQLite database (clinic.db) with schema + realistic dummy data.
Run: python setup_database.py
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "clinic.db"
random.seed(42)

# ── Reference data ────────────────────────────────────────────────────────────
FIRST_NAMES_M = [
    "Aarav","Arjun","Rohan","Vikram","Rahul","Amit","Sanjay","Nikhil",
    "Deepak","Suresh","Ravi","Ajay","Arun","Kiran","Mohit","Rajesh",
    "Vivek","Ankit","Harsh","Pranav","Dev","Ishaan","Kabir","Lakshya",
    "Manish","Naveen","Omkar","Parth","Sahil","Tarun",
]
FIRST_NAMES_F = [
    "Priya","Ananya","Sneha","Divya","Pooja","Nisha","Kavya","Meera",
    "Shreya","Riya","Neha","Ankita","Swati","Tanvi","Sonal","Isha",
    "Pallavi","Jyoti","Rekha","Sunita","Aisha","Bhavna","Charu",
    "Deepa","Esha","Fatima","Gauri","Heena","Ira","Jasmine",
]
LAST_NAMES = [
    "Sharma","Patel","Singh","Kumar","Gupta","Verma","Mehta","Shah",
    "Joshi","Nair","Reddy","Chopra","Banerjee","Iyer","Pillai",
    "Desai","Rao","Chatterjee","Bose","Saxena","Mishra","Tiwari",
    "Pandey","Srivastava","Dubey","Yadav","Malhotra","Bhatia","Kapoor","Aggarwal",
]
CITIES = [
    "Mumbai","Delhi","Bangalore","Hyderabad","Chennai",
    "Pune","Kolkata","Ahmedabad","Jaipur","Lucknow",
]
DOCTOR_NAMES = [
    ("Dr. Alok Sharma",    "Dermatology",      "Skin & Hair"),
    ("Dr. Preethi Nair",   "Dermatology",      "Skin & Hair"),
    ("Dr. Ramesh Gupta",   "Dermatology",      "Skin & Hair"),
    ("Dr. Sunil Mehta",    "Cardiology",       "Heart & Vascular"),
    ("Dr. Kavita Rao",     "Cardiology",       "Heart & Vascular"),
    ("Dr. Aryan Kapoor",   "Cardiology",       "Heart & Vascular"),
    ("Dr. Vijay Malhotra", "Orthopedics",      "Bone & Joint"),
    ("Dr. Sunita Verma",   "Orthopedics",      "Bone & Joint"),
    ("Dr. Rakesh Joshi",   "Orthopedics",      "Bone & Joint"),
    ("Dr. Meena Pillai",   "General Medicine", "OPD"),
    ("Dr. Ashok Patel",    "General Medicine", "OPD"),
    ("Dr. Geeta Iyer",     "General Medicine", "OPD"),
    ("Dr. Harish Reddy",   "Pediatrics",       "Child Health"),
    ("Dr. Lalitha Singh",  "Pediatrics",       "Child Health"),
    ("Dr. Nitin Chopra",   "Pediatrics",       "Child Health"),
]
TREATMENT_MAP = {
    "Dermatology":      [("Acne Treatment",800,30),("Skin Biopsy",2500,60),("Laser Therapy",3500,90),("Chemical Peel",1800,45),("Mole Removal",2000,40)],
    "Cardiology":       [("ECG",600,20),("Echocardiography",3000,60),("Stress Test",2500,90),("Holter Monitoring",4000,30),("Angiography",5000,120)],
    "Orthopedics":      [("Physiotherapy",800,60),("X-Ray Consultation",700,30),("MRI Review",4500,45),("Joint Injection",2000,30),("Fracture Management",3500,90)],
    "General Medicine": [("General Consultation",400,20),("Blood Test Review",300,15),("BP Management",350,20),("Diabetes Consultation",450,25),("Vaccination",600,15)],
    "Pediatrics":       [("Child Checkup",500,30),("Vaccination (Child)",700,20),("Growth Assessment",400,25),("Fever Treatment",350,20),("Allergy Test",1500,45)],
}

NOW          = datetime.now()
ONE_YEAR_AGO = NOW - timedelta(days=365)

def rdt(start, end):
    """Random datetime between start and end."""
    delta = int((end - start).total_seconds())
    return (start + timedelta(seconds=random.randint(0, delta)))

def rand_phone():
    if random.random() < 0.15:
        return None
    return f"+91-{random.randint(70000,99999)}{random.randint(10000,99999)}"

def rand_email(first, last):
    if random.random() < 0.10:
        return None
    domains = ["gmail.com","yahoo.com","hotmail.com","outlook.com"]
    return f"{first.lower()}.{last.lower()}{random.randint(1,99)}@{random.choice(domains)}"

SCHEMA = """
CREATE TABLE patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    date_of_birth   DATE,
    gender          TEXT,
    city            TEXT,
    registered_date DATE
);
CREATE TABLE doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    specialization  TEXT,
    department      TEXT,
    phone           TEXT
);
CREATE TABLE appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER REFERENCES patients(id),
    doctor_id        INTEGER REFERENCES doctors(id),
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT
);
CREATE TABLE treatments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id     INTEGER REFERENCES appointments(id),
    treatment_name     TEXT,
    cost               REAL,
    duration_minutes   INTEGER
);
CREATE TABLE invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER REFERENCES patients(id),
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT
);
"""

def build():
    import os
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.executescript(SCHEMA)
    conn.commit()

    # Doctors
    for name, spec, dept in DOCTOR_NAMES:
        phone = rand_phone() or f"+91-9{random.randint(100000000,999999999)}"
        cur.execute("INSERT INTO doctors(name,specialization,department,phone) VALUES(?,?,?,?)",
                    (name, spec, dept, phone))
    conn.commit()
    doc_rows  = cur.execute("SELECT id,specialization FROM doctors").fetchall()
    doc_ids   = [r[0] for r in doc_rows]
    doc_spec  = {r[0]: r[1] for r in doc_rows}

    # Patients
    for _ in range(200):
        gender = random.choice(["M","F"])
        first  = random.choice(FIRST_NAMES_M if gender=="M" else FIRST_NAMES_F)
        last   = random.choice(LAST_NAMES)
        dob    = rdt(datetime(1950,1,1), datetime(2010,12,31)).strftime("%Y-%m-%d")
        city   = random.choice(CITIES)
        reg    = rdt(ONE_YEAR_AGO, NOW).strftime("%Y-%m-%d")
        cur.execute(
            "INSERT INTO patients(first_name,last_name,email,phone,date_of_birth,gender,city,registered_date) VALUES(?,?,?,?,?,?,?,?)",
            (first, last, rand_email(first,last), rand_phone(), dob, gender, city, reg))
    conn.commit()
    pat_ids    = [r[0] for r in cur.execute("SELECT id FROM patients").fetchall()]
    power_pats = random.sample(pat_ids, 30)

    # Appointments
    for i in range(500):
        pid    = random.choice(power_pats) if i % 10 < 3 else random.choice(pat_ids)
        did    = random.choice(doc_ids)
        # Weight doctors unequally
        if random.random() < 0.3:
            did = random.choice(doc_ids[:5])
        appt_dt = rdt(ONE_YEAR_AGO, NOW).strftime("%Y-%m-%d %H:%M:%S")
        status  = random.choices(["Scheduled","Completed","Cancelled","No-Show"], weights=[15,55,20,10])[0]
        notes   = random.choice(["Follow-up required","Patient came on time","Referral given","Lab tests ordered",None,None]) if random.random()>0.4 else None
        cur.execute("INSERT INTO appointments(patient_id,doctor_id,appointment_date,status,notes) VALUES(?,?,?,?,?)",
                    (pid, did, appt_dt, status, notes))
    conn.commit()

    # Treatments (only for Completed)
    completed = cur.execute("SELECT id,doctor_id FROM appointments WHERE status='Completed'").fetchall()
    sample    = random.sample(completed, min(350, len(completed)))
    for appt_id, doc_id in sample:
        spec  = doc_spec.get(doc_id, "General Medicine")
        opts  = TREATMENT_MAP.get(spec, TREATMENT_MAP["General Medicine"])
        name, base_cost, base_dur = random.choice(opts)
        cost = round(base_cost * random.uniform(0.8, 1.3), 2)
        dur  = max(10, base_dur + random.randint(-5,15))
        cur.execute("INSERT INTO treatments(appointment_id,treatment_name,cost,duration_minutes) VALUES(?,?,?,?)",
                    (appt_id, name, cost, dur))
    conn.commit()

    # Invoices
    for _ in range(300):
        pid    = random.choice(pat_ids)
        idate  = rdt(ONE_YEAR_AGO, NOW).strftime("%Y-%m-%d")
        total  = round(random.uniform(300, 8000), 2)
        status = random.choices(["Paid","Pending","Overdue"], weights=[60,25,15])[0]
        paid   = total if status=="Paid" else round(total*random.uniform(0,0.5),2) if status=="Pending" else round(total*random.uniform(0,0.3),2)
        cur.execute("INSERT INTO invoices(patient_id,invoice_date,total_amount,paid_amount,status) VALUES(?,?,?,?,?)",
                    (pid, idate, total, paid, status))
    conn.commit()
    conn.close()

def summary():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    tbls = ["patients","doctors","appointments","treatments","invoices"]
    print("="*50)
    print("  clinic.db created successfully!")
    print("="*50)
    for t in tbls:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<15}: {n}")
    print("="*50)
    conn.close()

if __name__ == "__main__":
    build()
    summary()
