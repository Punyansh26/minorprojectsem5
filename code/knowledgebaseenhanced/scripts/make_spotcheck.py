#!/usr/bin/env python3
"""Generate ``eval/spotcheck.json``: the questions that decide whether the new KB is good enough.

Two origins:

``legacy``  every reviewed case from the institute-assistant evaluation (117, three languages),
            enriched with the source file and page of its expected evidence block.  These guard
            against regressions: the old release finds the required terms for all 93 answerable
            cases (``eval/baseline_old.json``).
``new``     hand-written cases for content the old release never covered (faculty, library,
            placements, calendar, hostel, curriculum, FAQ).  Every expected value below was
            copied from the source document named in ``source`` – none is derived from a model.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT.parent / "Institute-voice-agent" / "institute-assistant"


def legacy_cases() -> list[dict]:
    cases = json.loads((LEGACY / "docs" / "kb_evaluation_cases.json").read_text(encoding="utf-8"))
    active = json.loads((LEGACY / "kb_state" / "active.json").read_text())["release"]
    parents = json.loads((LEGACY / "kb_state" / "releases" / active / "parents.json").read_text(encoding="utf-8"))
    out = []
    for c in cases:
        sources = []
        for block in c.get("expected_blocks", []):
            p = parents.get(block)
            if p:
                name = p["source_file"]
                looks_like_file = bool(__import__("re").search(r"\.[A-Za-z]{2,5}$", name))
                sources.append({"file": Path(name).name if looks_like_file else name, "page": p.get("page_number", -1)})
        expect = {"answerable": "answerable", "no_cutoff": "no_result", "insufficient": "answer_review"}[c["expected"]]
        out.append({"id": "legacy_" + c["id"], "origin": "legacy", "language": c["language"], "topic": c["topic"],
                    "question": c["question"], "expect": expect, "required_terms": c.get("required_terms", []),
                    "expected_sources": sources, "cutoff_filters": c.get("cutoff_filters")})
    return out


def case(id, topic, language, question, terms, file, page=None, source="", expect="answerable", any_terms=None):
    row = {"id": "new_" + id, "origin": "new", "language": language, "topic": topic, "question": question,
           "expect": expect, "required_terms": terms,
           "expected_sources": [{"file": file, **({"page": page} if page else {})}] if file else [], "source": source}
    if any_terms:
        row["required_any"] = any_terms
    return row


def new_cases() -> list[dict]:
    brochure = "B TECH_2026.pdf"
    cal = "ACF2026.pdf"
    return [
        # --- admissions brochure (seats, eligibility, fees, hostel) ---
        case("seats_per_branch", "admissions", "english", "How many seats are there in each B.Tech branch at IIIT Naya Raipur?",
             ["90 seats"], brochure, 7, "brochure p7: 'There are 90 seats available in each CSE, ECE, and DSAI'"),
        case("all_india_seats", "admissions", "english", "How many seats are filled through JoSAA/CSAB in the All India quota?",
             ["95 seats"], brochure, 7, "brochure p7"),
        case("cg_quota_seats", "admissions", "hinglish", "Chhattisgarh quota mein kitni seats hain B.Tech ke liye?",
             ["135"], brochure, 8, "brochure p8: 'Chhattisgarh Quota: 50% of seats amount to 135 seats'"),
        # The brochure's NTPC figures contradict each other (40 seats, but 16+17+17 = 50 per branch); the reviewed
        # text marks them "not verified".  The system must not state a number - a human reads the answer.
        case("ntpc_quota_seats", "admissions", "english", "How many seats does the NTPC quota have for B.Tech?",
             [], None, None, "brochure p7: NTPC total conflicts with its branch breakdown", expect="answer_review"),
        case("cg_marks", "admissions", "english", "What minimum 12th marks are needed for the Chhattisgarh quota?",
             ["50%", "45%"], brochure, 8, "brochure p8 (note: institute FAQ says Physics and Mathematics only)"),
        case("cg_dob", "admissions", "english", "What is the date of birth limit for Chhattisgarh quota candidates?",
             ["October 01, 2000"], brochure, 8, "brochure p8 item 3"),
        case("application_fee", "fees", "english", "What is the B.Tech application fee for CG and NTPC quota?",
             ["500"], brochure, 10, "brochure p10: 'non-refundable application fee of Rs. 500/-'"),
        case("caution_deposit", "fees", "english", "How much is the refundable caution deposit for B.Tech 2026?",
             ["15000"], brochure, 11, "brochure p11: 'One Time Fee including refundable caution deposit (₹ 15000.00)'"),
        case("mess_advance", "fees", "hinglish", "B.Tech 2026 mein mess advance kitna hai?",
             ["25"], brochure, 11, "brochure p11: Mess Advance ₹ 25, 000.00", any_terms=["25,000", "25000", "25, 000"]),
        case("welfare_fee", "fees", "english", "What is the Academic and Student Welfare Fee?",
             ["20"], brochure, 11, "brochure p11: ₹ 20000.00", any_terms=["20,000", "20000"]),
        case("hostel_count", "campus", "english", "How many hostels does IIIT Naya Raipur have?",
             ["four hostels for boys", "three for girls"], brochure, 3, "brochure p3: 'four hostels for boys and three for girls'"),
        case("auditorium", "campus", "english", "What is the seating capacity of the auditorium?",
             ["800"], brochure, 5, "brochure p5: '800-seat capacity'"),
        case("campus_area", "campus", "english", "How large is the IIIT-NR campus?",
             ["50 acres"], brochure, 2, "brochure p2"),
        case("admission_contact", "admissions", "english", "What email can I write to for B.Tech admission queries?",
             ["btech.admissions@iiitnr.ac.in"], brochure, 12, "brochure p12"),
        # --- academic calendar ---
        case("orientation_date", "calendar", "english", "When does the orientation program start in 2026?",
             ["August 20, 2026"], cal, 1, "ACF2026 p1"),
        case("mte_date", "calendar", "hinglish", "Mid term exams kab hain 2026 mein?",
             ["November 03"], cal, 1, "ACF2026 p1"),
        case("ete_dates", "calendar", "english", "When is the End Term Examination?",
             ["December 21-30, 2026"], cal, 1, "ACF2026 p1"),
        case("diwali_holiday", "calendar", "english", "On which date is the Diwali holiday?",
             ["NOVEMBER 08, 2026"], cal, 2, "ACF2026 p2"),
        case("results_date", "calendar", "english", "When will first semester results be declared?",
             ["January 20, 2027"], cal, 1, "ACF2026 p1"),
        # --- faculty ---
        case("faculty_santosh", "faculty", "english", "What is Dr. Santosh Kumar's designation and department?",
             ["ASSOCIATE PROFESSOR", "CSE"], "Santosh Kumar _ IIIT", None, "faculty directory + profile"),
        case("faculty_dean", "faculty", "english", "Who is the Dean of Academics at IIIT-NR?",
             ["Srinivasa"], None, None, "faculty directory: Srinivasa K G, Professor (DSAI) and Dean (Academics)"),
        case("faculty_abhishek", "faculty", "english", "Which department is Abhishek Sharma in and where did he do his PhD?",
             ["ECE", "IIT Guwahati"], None, None, "faculty directory"),
        case("faculty_email", "faculty", "english", "What is the email address of Dr. Vinay Kumar?",
             ["vinay@iiitnr.edu.in"], None, None, "faculty directory"),
        case("faculty_hindi", "faculty", "hindi", "डीएसएआई विभाग में कौन से प्राध्यापक हैं?",
             ["DSAI"], None, None, "faculty directory", expect="answer_review"),
        # --- library / placements / general ---
        case("library_books", "general", "english", "How many books are in the IIIT-NR library?",
             ["7316"], "Library At A Glance _ IIIT NAYA RAIPUR.html", None, "library page: BOOKS 7316"),
        case("library_ejournals", "general", "english", "How many e-journals and e-books does Knimbus provide?",
             ["18000", "85000"], "Library At A Glance _ IIIT NAYA RAIPUR.html", None, "library page"),
        case("median_ctc", "placements", "english", "What is the median CTC in B.Tech placements 2021-2025?",
             ["14.50"], None, None, "Placement-Highlight.jpg: 'Median CTC 14.50 LPA'"),
        case("top25_ctc", "placements", "english", "What is the average CTC for the top 25 percent of the batch?",
             ["30.34"], None, None, "Placement-Highlight.jpg"),
        case("placed_students", "placements", "english", "How many students of the 2021-25 B.Tech batch were placed?",
             ["111"], None, None, "Placement-Stat-1.jpg: placed till date total 111"),
        case("companies_recruited", "placements", "english", "Which companies recruited from IIIT Naya Raipur?",
             ["Amazon"], None, None, "Companies.jpg"),
        case("established", "general", "english", "When did the first academic session of the institute start?",
             ["2015"], "FAQs _ IIIT NAYA RAIPUR.html", None, "FAQ: 'first academic session commenced from Aug 2015'"),
        case("phd_start", "general", "english", "When does Ph.D. admission usually take place?",
             ["June"], "FAQs _ IIIT NAYA RAIPUR.html", None, "FAQ: June for Autumn, December for Spring"),
        case("programs_offered", "general", "english", "What programs does the institute offer?",
             ["B.Tech", "M.Tech", "Ph.D"], None, None, "FAQ / brochure p6"),
        case("curriculum_credits", "academics", "english", "What is the total credit requirement of the B.Tech CSE curriculum from 2025?",
             ["160"], None, None, "btech_cse_curriculum_2025: 'Total Credit : 160'"),
        case("sem1_credits", "academics", "english", "How many credits are there in semester 1 of B.Tech CSE?",
             ["21"], None, None, "btech_cse_curriculum_2025: 'Semester 1 Total Credit : 21'"),
        case("fractal", "academics", "english", "What is the basic motto of the academic curriculum at IIIT-NR?",
             ["Skill First"], None, None, "Training and Placement page"),
        # --- questions the corpus cannot answer: the engine must not invent ---
        case("out_of_scope_1", "unknown", "english", "What is the hostel mess menu for Sunday dinner?", [], None, None,
             "not in corpus", expect="answer_review"),
        case("out_of_scope_2", "unknown", "english", "What is the fee for an MBBS course at IIIT-NR?", [], None, None,
             "institute offers no MBBS", expect="answer_review"),
        case("out_of_scope_3", "unknown", "hinglish", "Aaj ka mausam kaisa hai Raipur mein?", [], None, None,
             "weather is not in the corpus", expect="answer_review"),
    ]


def main() -> None:
    cases = legacy_cases() + new_cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    out = ROOT / "eval" / "spotcheck.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases ({sum(c['origin'] == 'legacy' for c in cases)} legacy, "
          f"{sum(c['origin'] == 'new' for c in cases)} new) -> {out}")


if __name__ == "__main__":
    main()
