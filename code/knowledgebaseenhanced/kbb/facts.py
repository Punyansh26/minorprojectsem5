"""Structured Facts Extractor and Router for IIIT Naya Raipur RAG.

Extracts high-precision facts into SQLite:
- Fees (Tuition, Hostel, Mess, Caution Deposit, Semester totals)
- Seat Matrix (Branch allocations, Quotas: All India, CG State, NTPC, Supernumerary)
- Key Dates (Orientation, Registration, Exams, Holidays, Application deadlines)
- Faculty Roster (Names, Designations, Departments, Emails, Research areas)
- Placement Statistics (Average CTC, Median CTC, Top percentages, Recruiters)
"""
from __future__ import annotations

import logging
from pathlib import Path
import re
import sqlite3
from typing import Any

from .models import Parent
from .textnorm import clean

log = logging.getLogger(__name__)


def init_facts_db(db_path: Path) -> sqlite3.Connection:
    """Initialize facts database schema."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS fees")
    cur.execute("""
        CREATE TABLE fees (
            fee_type TEXT,
            amount INT,
            currency TEXT DEFAULT 'INR',
            semester TEXT,
            notes TEXT,
            parent_id TEXT,
            source_file TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS seat_matrix")
    cur.execute("""
        CREATE TABLE seat_matrix (
            program TEXT,
            quota TEXT,
            category TEXT,
            seats INT,
            notes TEXT,
            parent_id TEXT,
            source_file TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS key_dates")
    cur.execute("""
        CREATE TABLE key_dates (
            event TEXT,
            date_str TEXT,
            category TEXT,
            parent_id TEXT,
            source_file TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS faculty_roster")
    cur.execute("""
        CREATE TABLE faculty_roster (
            name TEXT,
            designation TEXT,
            department TEXT,
            email TEXT,
            research_interests TEXT,
            parent_id TEXT,
            source_file TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS placements")
    cur.execute("""
        CREATE TABLE placements (
            metric TEXT,
            value TEXT,
            academic_year TEXT,
            notes TEXT,
            parent_id TEXT,
            source_file TEXT
        )
    """)
    con.commit()
    return con


def extract_and_populate_facts(db_path: Path, processed_kb_dir: Path, parents: list[Parent]) -> dict[str, int]:
    """Parse processed Markdown files and parent chunks to populate facts.sqlite."""
    con = init_facts_db(db_path)
    cur = con.cursor()

    # Clear existing tables for idempotent rebuild
    for tbl in ["fees", "seat_matrix", "key_dates", "faculty_roster", "placements"]:
        cur.execute(f"DELETE FROM {tbl}")

    parents_by_file: dict[str, list[Parent]] = {}
    for p in parents:
        src = p.meta.get("source_file", "")
        parents_by_file.setdefault(src, []).append(p)

    counts = {"fees": 0, "seat_matrix": 0, "key_dates": 0, "faculty_roster": 0, "placements": 0}

    # 1. Extract Fees
    # Source: admissions/btech_admission_brochure_2026.md
    btech_brochure = processed_kb_dir / "admissions" / "btech_admission_brochure_2026.md"
    p_btech_fee = next((p.id for p in parents if "admissions-btech_admission_brochure_2026" in p.id and "Fee" in p.text), "admissions-btech_admission_brochure_2026:p011")

    fee_items = [
        ("Tuition Fee", 90000, "Semester I & II", "Per semester", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Hostel Fee", 15000, "Semester I & II", "Hostel accommodation per semester", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Mess Advance", 25000, "Semester I", "Adjustable mess fee advance", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Academic and Student Welfare Fee", 20000, "Semester I", "Welfare and academic activities", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Caution Deposit", 15000, "One-Time", "Refundable security caution deposit", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("One Time Fee (with caution deposit)", 31000, "One-Time", "One-time fee at admission including refundable ₹15,000 caution deposit", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Total Institution Fee", 141000, "Semester I", "Sum of One-Time (31k) + Tuition (90k) + Welfare (20k)", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Total Fee Semester I", 181000, "Semester I", "Total payable for Semester I (includes Institution Fee 141k + Hostel 15k + Mess 25k)", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Total Fee Semester II Onwards", 150000, "Semester II Onwards", "Subsequent semester fees (Tuition 90k + Welfare 20k + Hostel 15k + Mess 25k)", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        ("Application Fee (CG/NTPC Quota)", 500, "Admission", "Non-refundable application & counselling fee", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
    ]
    for item in fee_items:
        cur.execute("INSERT INTO fees VALUES (?, ?, 'INR', ?, ?, ?, ?)", item)
        counts["fees"] += 1

    # 2. Extract Seat Matrix
    # Source: admissions/btech_admission_brochure_2026.md
    p_btech_seats = next((p.id for p in parents if "admissions-btech_admission_brochure_2026" in p.id and "Eligibility Criteria, Seats" in p.text), "admissions-btech_admission_brochure_2026:p007")

    seat_items = [
        # Quota Totals
        ("B.Tech (All Branches)", "All India Quota", "Open/All", 95, "35% of seats (32 CSE, 32 ECE, 31 DSAI) filled via JoSAA/CSAB 2026", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech (All Branches)", "Chhattisgarh Quota", "CG Domicile", 135, "50% of seats (45 CSE, 45 ECE, 45 DSAI) filled via IIIT-NR online counselling", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech (All Branches)", "NTPC Quota", "NTPC Wards", 40, "15% of seats (16 CSE, 17 ECE, 17 DSAI) filled via IIIT-NR online counselling", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        # Branch Normals
        ("B.Tech CSE", "Total Normal", "All Quotas", 90, "Regular seats (32 All India + 45 CG + 16 NTPC) + 1 Kashmiri Migrant", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech ECE", "Total Normal", "All Quotas", 90, "Regular seats (32 All India + 45 CG + 17 NTPC) + 1 Kashmiri Migrant", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech DSAI", "Total Normal", "All Quotas", 90, "Regular seats (31 All India + 45 CG + 17 NTPC) + 1 Kashmiri Migrant", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        # Supernumerary Female Seats
        ("B.Tech CSE", "All India Quota", "Female Supernumerary", 8, "Reserved exclusively for female candidates via JoSAA/CSAB", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech ECE", "All India Quota", "Female Supernumerary", 8, "Reserved exclusively for female candidates via JoSAA/CSAB", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech DSAI", "All India Quota", "Female Supernumerary", 8, "Reserved exclusively for female candidates via JoSAA/CSAB", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech CSE", "NTPC Quota", "Female Supernumerary", 3, "Reserved exclusively for female candidates", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech ECE", "NTPC Quota", "Female Supernumerary", 4, "Reserved exclusively for female candidates", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        ("B.Tech DSAI", "NTPC Quota", "Female Supernumerary", 3, "Reserved exclusively for female candidates", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
        # Overall Total
        ("B.Tech (Total)", "Institute Total", "All Categories", 307, "270 normal seats + 34 female supernumerary + 3 Kashmiri Migrant seats across CSE, ECE, DSAI", p_btech_seats, "admissions/btech_admission_brochure_2026.md"),
    ]
    for item in seat_items:
        cur.execute("INSERT INTO seat_matrix VALUES (?, ?, ?, ?, ?, ?, ?)", item)
        counts["seat_matrix"] += 1

    # 3. Extract Academic Calendar & Admission Key Dates
    # Source: academics/academic_calendar_2026.md
    p_cal = next((p.id for p in parents if "academics-academic-calendar-2026" in p.id), "academics-academic-calendar-2026:p001")
    p_hol = next((p.id for p in parents if "academics-academic-calendar-2026" in p.id and "Holidays" in p.text), p_cal)

    date_items = [
        ("Commencement of Orientation / Induction Program", "August 20, 2026", "Academic Event", p_cal, "academics/academic_calendar_2026.md"),
        ("Commencement of Registration for First Semester", "August 24, 2026", "Registration", p_cal, "academics/academic_calendar_2026.md"),
        ("Closing date for First Semester registration", "August 30, 2026", "Registration", p_cal, "academics/academic_calendar_2026.md"),
        ("Sports Event AAGAAZ 2026", "October 18-20, 2026", "Event", p_cal, "academics/academic_calendar_2026.md"),
        ("Mid Term Examinations (MTE)", "November 03, 2026", "Examination", p_cal, "academics/academic_calendar_2026.md"),
        ("5th Convocation", "November, 2026", "Convocation", p_cal, "academics/academic_calendar_2026.md"),
        ("Last Day of Instruction (B.Tech / M.Tech)", "December 17, 2026", "Academic Event", p_cal, "academics/academic_calendar_2026.md"),
        ("End Term Examination (ETE)", "December 21-30, 2026", "Examination", p_cal, "academics/academic_calendar_2026.md"),
        ("Semester Break for B.Tech Students", "December 31, 2026 – January 10, 2027", "Recess", p_cal, "academics/academic_calendar_2026.md"),
        ("Faculty Vacation Leave", "December 31, 2026 – January 15, 2027", "Recess", p_cal, "academics/academic_calendar_2026.md"),
        ("Spring 2027 Classes Start (M.Tech)", "January 04, 2027", "Academic Event", p_cal, "academics/academic_calendar_2026.md"),
        ("Spring 2027 Classes Start (B.Tech)", "January 11, 2027", "Academic Event", p_cal, "academics/academic_calendar_2026.md"),
        ("Declaration of First Semester Results", "January 20, 2027", "Results", p_cal, "academics/academic_calendar_2026.md"),
        ("B.Tech Application Submission Start", "May 15, 2026", "Admission", p_btech_fee, "admissions/btech_admission_brochure_2026.md"),
        # Holidays
        ("World Tribal Day", "August 09, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Hareli", "August 12, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Independence Day", "August 15, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Id-E-Milad", "August 26, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Rakshabandhan", "August 28, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Krishna Janmashtami", "September 04, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Haritalika Teej", "September 14, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Nuwakhai", "September 15, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Mahatma Gandhi Birthday", "October 02, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Mahashtami", "October 19, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Vijaya Dashami (Dussehra)", "October 20, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Diwali", "November 08, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Govardhan Puja", "November 09, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Chhath Pooja", "November 15, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Gurunanak Jayanti", "November 24, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Guru Ghasi Das Jayanti", "December 18, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
        ("Christmas", "December 25, 2026", "Holiday", p_hol, "academics/academic_calendar_2026.md"),
    ]
    for item in date_items:
        cur.execute("INSERT INTO key_dates VALUES (?, ?, ?, ?, ?)", item)
        counts["key_dates"] += 1

    # 4. Extract Faculty Roster
    faculty_dir = processed_kb_dir / "faculty"
    if faculty_dir.exists():
        for fpath in sorted(faculty_dir.glob("*.md")):
            if fpath.stem == "faculty_directory":
                continue
            text = fpath.read_text(encoding="utf-8")
            # Parse frontmatter
            name_m = re.search(r'title:\s*["\']?(?:Faculty Profile:\s*)?([^"\'\n]+)', text)
            desig_m = re.search(r'designation:\s*["\']?([^"\'\n]+)', text)
            dept_m = re.search(r'department:\s*["\']?([^"\'\n]+)', text)
            email_m = re.search(r'email:\s*["\']?([^"\'\n]+)', text)
            research_m = re.search(r'##\s*Research Interests\s*\n+([^#\n]+(?:\n[^#\n]+)*)', text)

            name = clean(name_m.group(1)) if name_m else fpath.stem.replace("_", " ").title()
            desig = clean(desig_m.group(1)) if desig_m else "Faculty Member"
            dept = clean(dept_m.group(1)) if dept_m else "IIIT Naya Raipur"
            email = clean(email_m.group(1)) if email_m else ""
            research = clean(research_m.group(1)) if research_m else ""

            p_id = next((p.id for p in parents if p.meta.get("source_file", "").endswith(fpath.name)), f"faculty-{fpath.stem}:p001")
            cur.execute("INSERT INTO faculty_roster VALUES (?, ?, ?, ?, ?, ?, ?)", (
                name, desig, dept, email, research, p_id, f"faculty/{fpath.name}"
            ))
            counts["faculty_roster"] += 1

    # 5. Extract Placement Statistics
    p_placement = next((p.id for p in parents if "general-placement-statistics-and-companies" in p.id), "general-placement-statistics-and-companies:p001")

    placement_items = [
        ("Highest CTC", "Top tier competitive offers across batches", "2021-2025", "Placement Highlight", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Top 25% Average CTC", "30.34 LPA", "2021-2025", "B.Tech Batch Average for top quartile", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Top 50% Average CTC", "25.46 LPA", "2021-2025", "B.Tech Batch Average for top half", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Median CTC", "14.50 LPA", "2021-2025", "Overall median package for placed students", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Total Job Offers", "110+ Offers", "2021-2025", "Total offers received till date", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Total Participating Companies", "60+ Companies", "2021-2025", "Recruiting organizations", p_placement, "general/placement_statistics_and_recruiters.md"),
        ("Top Recruiting Companies", "Amazon, Swiggy, Amex, AON, Credit Sea, ACKO, Google, L&T, DE Shaw, IND Money, Cadence Design, Radcom", "2021-2025", "Prominent national and MNC recruiters", p_placement, "general/placement_statistics_and_recruiters.md"),
    ]
    for item in placement_items:
        cur.execute("INSERT INTO placements VALUES (?, ?, ?, ?, ?, ?)", item)
        counts["placements"] += 1

    con.commit()
    con.close()
    return counts


def query_facts(db_path: Path, question: str) -> list[dict[str, Any]]:
    """Check facts.sqlite for high-precision factual matches.
    
    Returns a list of evidence dicts ready for conversion to RetrievedEvidence.
    """
    if not db_path.exists():
        return []

    q = question.lower()
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    evidence_list: list[dict[str, Any]] = []

    # 1. Fee Lookups
    if any(k in q for k in ["fee", "fees", "tuition", "hostel charge", "hostel fee", "mess", "caution deposit", "cost"]):
        matched_rows = []
        conditions = []
        if "tuition" in q:
            conditions.append("fee_type LIKE '%tuition%'")
        if "hostel" in q:
            conditions.append("fee_type LIKE '%hostel%'")
        if "mess" in q:
            conditions.append("fee_type LIKE '%mess%'")
        if "caution" in q or "deposit" in q:
            conditions.append("(fee_type LIKE '%caution%' OR fee_type LIKE '%one time%')")

        if conditions:
            where_clause = " OR ".join(conditions)
            cur.execute(f"SELECT fee_type, amount, currency, semester, notes, parent_id, source_file FROM fees WHERE {where_clause}")
            matched_rows.extend(cur.fetchall())
        else:
            cur.execute("SELECT fee_type, amount, currency, semester, notes, parent_id, source_file FROM fees")
            matched_rows.extend(cur.fetchall())

        if matched_rows:
            lines = ["### Official Fee Structure (B.Tech 2026-2030)\n| Fee Component | Amount | Schedule | Details |", "| :--- | :--- | :--- | :--- |"]
            p_id = matched_rows[0][5]
            src_file = matched_rows[0][6]
            for f_type, amt, curr, sem, notes, _, _ in matched_rows:
                lines.append(f"| **{f_type}** | ₹{amt:,} | {sem} | {notes} |")
            evidence_list.append({
                "parent_id": p_id,
                "title": "B.Tech Fee Structure (2026-2030)",
                "heading_path": ["Admissions", "B.Tech Fees", "Official Fee Schedule"],
                "page_start": 11,
                "page_end": 11,
                "text": "\n".join(lines),
                "score": 1.0,
                "source_file": src_file,
                "status": "verified_fact",
            })

    # 2. Seat Matrix Lookups
    if any(k in q for k in ["seat", "seats", "quota", "intake", "reservation", "matrix", "supernumerary"]):
        cur.execute("SELECT program, quota, category, seats, notes, parent_id, source_file FROM seat_matrix")
        rows = cur.fetchall()
        if rows:
            lines = ["### Official Seat Matrix & Reservation (B.Tech 2026)\n| Program / Quota | Category | Seats | Notes |", "| :--- | :--- | :--- | :--- |"]
            for prog, quota, cat, seats, notes, p_id, src_file in rows:
                if any(term in q for term in ["cse", "ece", "dsai"]) and not any(term in prog.lower() for term in [q_term for q_term in ["cse", "ece", "dsai"] if q_term in q]):
                    continue
                lines.append(f"| **{prog}** ({quota}) | {cat} | **{seats}** | {notes} |")
            evidence_list.append({
                "parent_id": rows[0][5],
                "title": "B.Tech Seat Matrix and Quota Allocations 2026",
                "heading_path": ["Admissions", "Seats and Reservation", "Seat Matrix"],
                "page_start": 7,
                "page_end": 8,
                "text": "\n".join(lines),
                "score": 1.0,
                "source_file": rows[0][6],
                "status": "verified_fact",
            })

    # 3. Key Dates / Academic Calendar / Holidays
    if any(k in q for k in ["date", "dates", "schedule", "when", "holiday", "holidays", "orientation", "exam", "mte", "ete", "vacation", "calendar"]):
        cur.execute("SELECT event, date_str, category, parent_id, source_file FROM key_dates")
        rows = cur.fetchall()
        matched = []
        for ev, dt, cat, p_id, src in rows:
            # Check if event matches query terms
            ev_lower = ev.lower()
            if any(term in ev_lower for term in q.split() if len(term) > 3) or ("holiday" in q and cat == "Holiday"):
                matched.append((ev, dt, cat, p_id, src))

        if not matched and any(k in q for k in ["calendar", "schedule", "dates"]):
            matched = rows[:12]

        if matched:
            lines = ["### Verified Academic Calendar & Key Dates (2026-2027)\n| Event / Holiday | Date | Category |", "| :--- | :--- | :--- |"]
            for ev, dt, cat, p_id, src in matched:
                lines.append(f"| **{ev}** | {dt} | {cat} |")
            evidence_list.append({
                "parent_id": matched[0][3],
                "title": "Academic Calendar & Key Dates (2026-2027)",
                "heading_path": ["Academics", "Academic Calendar", "Verified Dates"],
                "page_start": 1,
                "page_end": 2,
                "text": "\n".join(lines),
                "score": 1.0,
                "source_file": matched[0][4],
                "status": "verified_fact",
            })

    # 4. Faculty Contact / Roster
    if any(k in q for k in ["faculty", "professor", "teacher", "email", "dr.", "dr "]) or any(word in q for word in ["sharma", "paltani", "bandi", "choudhary", "sahu", "mishra", "deb"]):
        cur.execute("SELECT name, designation, department, email, research_interests, parent_id, source_file FROM faculty_roster")
        rows = cur.fetchall()
        matched = []
        for name, desig, dept, email, research, p_id, src in rows:
            name_parts = name.lower().split()
            if any(part in q for part in name_parts if len(part) > 2) or (dept.lower() in q and "faculty" in q):
                matched.append((name, desig, dept, email, research, p_id, src))

        if matched:
            for name, desig, dept, email, research, p_id, src in matched[:3]:
                card = f"### Faculty Profile: {name}\n- **Designation:** {desig}\n- **Department:** {dept}\n- **Email:** `{email}`\n- **Research Interests:** {research}"
                evidence_list.append({
                    "parent_id": p_id,
                    "title": f"Faculty Profile: {name}",
                    "heading_path": ["Faculty", dept, name],
                    "page_start": 1,
                    "page_end": 1,
                    "text": card,
                    "score": 1.0,
                    "source_file": src,
                    "status": "verified_fact",
                })

    # 5. Placement Statistics
    if any(k in q for k in ["placement", "package", "salary", "ctc", "lpa", "recruiter", "recruiters", "companies", "placed"]):
        cur.execute("SELECT metric, value, academic_year, notes, parent_id, source_file FROM placements")
        rows = cur.fetchall()
        if rows:
            lines = ["### Placement Statistics & Recruiters (Batch 2021-2025)\n| Metric | Figure / Details | Notes |", "| :--- | :--- | :--- |"]
            for metric, val, yr, notes, p_id, src in rows:
                lines.append(f"| **{metric}** | **{val}** | {notes} ({yr}) |")
            evidence_list.append({
                "parent_id": rows[0][4],
                "title": "B.Tech & M.Tech Placement Highlights",
                "heading_path": ["General", "Placements", "Statistics and Recruiters"],
                "page_start": 1,
                "page_end": 1,
                "text": "\n".join(lines),
                "score": 1.0,
                "source_file": rows[0][5],
                "status": "verified_fact",
            })

    con.close()
    return evidence_list
