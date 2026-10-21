"""Publish source coverage and actionable offline questions separately from answer evidence."""
from pathlib import Path

from assistant.kb.common import now, read_json

# These are questions to confirm, not statements that a policy exists or a benefit applies.
QUESTIONS = {
    "Scholarships — scholarship nodal officer / student welfare": [
        ("P0", "Which institute-funded merit, means, emergency, alumni or donor scholarships are actually available in 2026–27?", "Scheme circulars, benefit amounts, eligibility, selection and funding limits"),
        ("P0", "Which central and state scholarship schemes currently accept IIIT-NR students, and what institution identifiers must applicants select?", "Current portal listing, AISHE/institution codes, programme and domicile restrictions"),
        ("P0", "Who is the institute scholarship nodal officer, and what is the internal verification deadline for each 2026–27 scheme?", "Official role contact, office location, internal deadlines and signed procedure"),
        ("P0", "For Chhattisgarh post-matric scholarships, which IIIT-NR fees are reimbursable and what amount is payable for each category/course/hosteller status?", "Current fee mapping and sanction schedule; the fetched registration notice does not state award amounts"),
        ("P1", "Which documents and grade/attendance conditions are needed for fresh applications and renewals?", "Scheme-specific checklist, renewal circular and treatment of backlogs/repeat years"),
        ("P1", "Can a student combine state scholarships, central scholarships, institute aid, fee reimbursement, stipends or loan subsidies?", "A scheme-by-scheme combination/exclusion policy; do not generalize across schemes"),
        ("P1", "What aid is available for other-state domicile students, students with disabilities, and students facing sudden financial hardship?", "Applicable scheme circulars and institute approval process"),
        ("P1", "What is the verified process for scholarship rejection, correction, appeals, delayed verification and delayed payment?", "Portal procedure, responsible office, escalation channel and any published service timeline"),
        ("P1", "What current scholarships or assistantships apply to regular M.Tech, CMIT M.Tech and Ph.D students?", "Programme-specific award, renewal, service/bond and outside-employment rules"),
        ("P2", "Is financial support available for research, conferences, internships or international visits?", "Current circular, caps, eligible expenses and approval/reimbursement process")
    ],
    "Loans and payment support — accounts office / authorised bank desk": [
        ("P0", "Is IIIT-NR currently included in the PM-Vidyalaxmi eligible QHEI list, and for which programmes and admission routes?", "Current official list entry and written confirmation; general guidelines alone do not prove inclusion"),
        ("P0", "Which IIIT-NR programmes currently qualify for PM-USP CSIS interest support?", "Accreditation/course eligibility and relevant bank/government confirmation"),
        ("P0", "Does the institute permit fee instalments, deferral or provisional registration while a scholarship/loan is pending?", "Signed policy, eligible circumstances, due dates, charges and approving authority"),
        ("P1", "Which banks have a current institute arrangement, and what are their verified education-loan contacts?", "Current MoU/list and official bank branch contacts, not personal recommendations"),
        ("P1", "What are the current bank-specific rates, benchmark/spread, margin, collateral and co-borrower conditions?", "Dated product sheets/MITC and institution-specific category where applicable"),
        ("P1", "Which expenses can loans cover, including hostel, mess, laptop, deposits and annual fee increases?", "Bank product terms and institute cost certificate"),
        ("P1", "How does a student obtain a bonafide certificate, admission letter, fee estimate and bank disbursement instructions?", "Office procedure, forms, official account verification and authorised signatory"),
        ("P1", "What rules apply to fee refunds, caution-deposit refunds and bank disbursements after withdrawal?", "Current refund circular with deductions, timelines and required clearances"),
        ("P2", "Is there any emergency bridge assistance while a sanctioned scholarship or loan is awaiting disbursement?", "Written policy and application process, or confirmation that none exists")
    ],
    "Spot rounds and cutoffs — admissions office": [
        ("P0", "Provide the official CG and NTPC opening/closing ranks for each available year 2022–2026, round, branch, seat category and seat pool.", "Published cutoff tables with CRL/category/PwD rank definitions and corrigenda"),
        ("P0", "Provide the institute spot-round notices, revised vacancy snapshots and final published cutoff/outcome tables for 2026.", "Dated notices and final results; institute website requests timed out during this audit"),
        ("P0", "What are the spot-round eligibility, registration, fee-payment, reporting and withdrawal rules, and did any later notice amend them?", "Latest signed notice and amendment chain"),
        ("P0", "How are reservation categories, vacant reserved seats, seat conversion and rank lists handled in each institute spot round?", "Round-specific rules; regular-round reservations must not be assumed"),
        ("P1", "Can an already allotted/admitted candidate join a spot round, and what happens to the previous seat or fees?", "Official participation and seat-retention/cancellation instructions"),
        ("P1", "What are the tie-break, waiting-list, upgradation and subsequent vacancy procedures?", "Published rules and separate dates for each action"),
        ("P1", "Provide the missing IIIT-NR CSAB opening/closing rank data with special-round and rank-basis definitions.", "Official CSAB exports; do not substitute JoSAA or institute spot data"),
        ("P0", "Which NTPC seat total and branch breakdown in the 2026 brochure is correct?", "Corrigendum: page 7 states 40 seats but its printed branch numbers total 50"),
        ("P0", "What JEE rank-card year is required in the 2026 reporting checklist?", "Corrected checklist: the brochure page 10 contains a 2024 rank-card entry"),
        ("P1", "If no official cutoff table exists for a quota/round, can admissions provide a signed aggregate table without applicant personal details?", "Certified aggregate data with complete dimensions and rank definitions")
    ],
    "Academic policies — academic office": [
        ("P0", "Have the first-semester 2026 calendar or spring 2027 dates been revised since the 18 August 2026 circular?", "Latest revision and notice identifying superseded dates"),
        ("P1", "What are the current attendance, detention, medical-leave and attendance-relaxation rules?", "Programme/cohort-specific academic regulations"),
        ("P1", "What are the rules and deadlines for course add/drop, electives, backlogs, supplementary exams and grade improvement?", "Current rules, forms and fee circulars"),
        ("P1", "What are the branch-change, minor/honours, credit-transfer and semester-withdrawal policies?", "Approved academic ordinance and cohort applicability"),
        ("P1", "How do students obtain transcripts, certificates, grade corrections and re-evaluation?", "Forms, fees, office contacts and published processing timelines"),
        ("P2", "Where are the current programme curricula, elective lists, faculty advising schedules and lab access rules?", "Versioned curriculum and current departmental notices")
    ],
    "Hostel, mess and student services — hostel office / student welfare": [
        ("P0", "What are the current hostel allotment, room-change, visitor, leave and late-entry rules?", "Current hostel handbook and approval procedures"),
        ("P1", "How are mess advances adjusted, and when do mess rebates or refunds apply?", "Current mess accounting/rebate policy and forms"),
        ("P1", "What are the verified hostel/caretaker/security emergency and after-hours contact channels?", "Official role-based directory with validity date"),
        ("P1", "How should students report maintenance, water, electricity, internet or laundry problems?", "Complaint channels, responsible offices and escalation procedure"),
        ("P1", "What medical, ambulance, counselling and accessibility support is actually available?", "Current services, hours, eligibility and official emergency contacts"),
        ("P2", "What are the library, lab, sports-facility and campus transport hours and charges?", "Current operational schedules and fee notices"),
        ("P2", "How do students request ID cards, lost-card replacements, Wi-Fi access and ERP account recovery?", "Approved IT/student-office procedures")
    ],
    "Placements and institute contacts — placement office / administration": [
        ("P1", "Provide the latest completed batch's branch-wise placement figures, salary definitions and denominators.", "Signed/public placement report separating eligible, participating and placed students"),
        ("P1", "What are the current placement participation, internship/PPO, multiple-offer and disciplinary rules?", "Latest placement policy and cohort/programme scope"),
        ("P1", "Provide the current role-based office directory, office hours and grievance escalation channels.", "Dated official directory; distinguish office roles from personal contacts"),
        ("P2", "Which older circulars, FAQ statements and handbooks have been superseded?", "Supersession list and replacement documents")
    ]
}


def write_reports(state: Path) -> dict:
    """Regenerate public-source reports without incorporating private student conversations."""
    project = Path(__file__).resolve().parents[2]
    docs = project / "docs"
    docs.mkdir(exist_ok=True)
    sources = read_json(state / "sources.json", {"sources": []})["sources"]
    blocks = read_json(state / "blocks.json", [])
    report = read_json(state / "extraction_report.json", {})
    active = read_json(state / "active.json") or read_json(state / "latest_build.json", {})
    root = state / "releases" / active.get("release", "missing")
    manifest = read_json(root / "release.json", {})
    evaluation = read_json(root / "validation.json", {})
    inventory = ["# Knowledge-base source inventory", "", f"Audit generated: {now()}", "",
                 "Fetched dates record downloads, not proof that an undated policy is current. Local copies are identified separately. Failed downloads preserve earlier copies when available.", "",
                 "| Source | Retrieval | Review status | Period |", "|---|---|---|---|"]
    for s in sources:
        title = s.get("title", s["id"]).replace("|", "\\|")
        link = f"[{title}]({s['url'].replace(' ', '%20')})" if s.get("url") else title
        inventory.append(f"| {link} | {s.get('fetch_status','unknown')} | {s.get('verification_status','needs_review')} | {s.get('period','Not established')} |")
    (docs / "KB_SOURCE_INVENTORY.md").write_text("\n".join(inventory) + "\n")
    pending = ["# Extraction review queue", "", "These blocks are excluded from factual answers until reviewed against their source. An image crop is evidence for review, not an automatically understood chart.", ""]
    for b in blocks:
        if b["verification_status"] != "needs_review":
            continue
        pending.append(f"- `{b['id']}` — {b['title']}, page {b['page_number']}, {b['kind']}: {b.get('review_reason','Verify source scope and content')}" + (f" ([crop](../kb_state/{b['asset']}))" if b.get("asset") else ""))
    (docs / "KB_EXTRACTION_REVIEW.md").write_text("\n".join(pending) + "\n")
    failures = sum(s.get("fetch_status") == "failed" for s in sources)
    offline = ["# Offline information to collect for Demo 2", "", f"Prepared: {now()}", "",
        "This is a collection checklist, not institute policy. A question here means the audited corpus does not establish a reliable current answer; it does not prove the information is absent everywhere online.", "",
        "Sources checked: the supplied institute brochure, reporting instructions, FAQs, academic calendar, NIRF submissions and annual report; official institute endpoints; JoSAA public rank tables for 2022–2026; Chhattisgarh scholarship notices; and government-hosted PM-Vidyalaxmi guidelines. See [source inventory](../Institute-voice-agent/institute-assistant/docs/KB_SOURCE_INVENTORY.md) for individual URLs and failed requests.", "",
        "Confirmed distinctions: JoSAA All India rank rows are available; CG/NTPC, CSAB and institute spot cutoffs remain unverified. The CG registration notice gives conditions and processing dates, not a complete award schedule. PM-Vidyalaxmi rules do not establish IIIT-NR's current institutional eligibility. The supplied 2026 brochure contains conflicting NTPC seat figures and a rank-card-year inconsistency.", "",
        "P0 = needed for reliable admissions/financial guidance; P1 = frequently useful; P2 = broader campus coverage. Suggested offices below are collection routes, not verified contacts.", ""]
    count = 0
    for group, items in QUESTIONS.items():
        offline += [f"## {group}", "", "| ID | Priority | Question | Evidence to obtain |", "|---|---|---|---|"]
        for priority, question, evidence in items:
            count += 1
            offline.append(f"| Q{count:02d} | {priority} | {question} | {evidence} |")
        offline.append("")
    offline += ["## Record each response", "", "Copy this template for each question answered. Keep unknown fields blank; attach the circular/table rather than relying on recollection.", "", "```text", "Question ID:", "Answer:", "Programme / branch / quota / category / seat pool:", "Academic year / round / effective dates:", "Amount / unit / rank basis (if applicable):", "Exceptions / exclusions / renewal conditions:", "Official source or attached document and page:", "Office / role providing the information:", "Verified by:", "Verification date:", "Supersedes which earlier notice:", "Permission to use in the public helpdesk:", "```", "", "Offline responses remain outside the answerable database until their supporting evidence is reviewed and imported. For unreadable charts/tables, obtain the original spreadsheet or a clear export with captions, units and row/column labels."]
    target = project.parent.parent / "demo2/OFFLINE_INFORMATION_NEEDED.md"
    target.write_text("\n".join(offline) + "\n")
    summary = ["# Knowledge-base rebuild validation", "", f"Generated: {now()}", "", f"Release: `{manifest.get('release','not built')}`", "",
        f"- Vector chunks: {manifest.get('chunks',0)}; structured cutoff records: {manifest.get('cutoff_records',0)}.",
        f"- Source entries: {len(sources)}; failed fetches: {failures}. Failed sources are not marked fresh.",
        f"- Extraction blocks awaiting review: {sum(b['verification_status']=='needs_review' for b in blocks)}.",
        f"- Evaluation cases: {evaluation.get('cases',0)}; answerable cases: {evaluation.get('answerable_cases',0)}.",
        f"- Supporting-evidence recall@6: {evaluation.get('recall_at_6','not run')}; previous corpus recall@6: {evaluation.get('baseline_recall_at_6','not run')}.",
        f"- Exact cutoff tests: {evaluation.get('exact_rank_passed',0)}/{evaluation.get('exact_rank_cases',0)}.",
        f"- Warm retrieval median/p95: {evaluation.get('median_seconds','?')} / {evaluation.get('p95_seconds','?')} seconds (excludes LLM and speech).", "",
        "The benchmark tests retrieval and exact numeric lookup. It does not prove the factual accuracy of every generated answer. The expanded corpus and new extractor/model both contribute to changes from the baseline; this is not an isolated embedding-model comparison.", "",
        "## Remaining limitations", "", "- The institute website timed out during acquisition; current institute scholarships, spot notices, CG/NTPC cutoffs and several service policies need offline confirmation or a later successful refresh.", "- Unsupported/unreadable sources and unreviewed visual interpretations are excluded. There is no automatic inference of precise values from unlabeled graphs.", "- Bank-specific live rates and institute eligibility for loan subsidies were not established.", "- Historical annual reports and dated statistics remain historical.", "- See `kb_state/extraction_report.json`, the source inventory, extraction review queue, and the offline checklist for traceable gaps."]
    if evaluation:
        failed = [r['id'] for r in evaluation.get('results',[]) if r['passed'] is False]
        summary += ["", "Retrieval cases still failing: " + (", ".join(failed) if failed else "none")]
    live = read_json(docs / "kb_live_evaluation.json", [])
    if live:
        unavailable = sum(r["turns"][-1]["status"] == "unavailable" for r in live)
        summary += ["", "## Live answer checks", "",
                    f"Attempted {len(live)} fixed public questions; {sum(r['passed'] for r in live)} met expected answer statuses and {unavailable} returned unavailable.",
                    "The recorded 2026-09-22 run hit Groq rate limits. This does not validate factual generation or abstention on the new corpus. See [saved live results](kb_live_evaluation.json). No ticket or reminder writes were permitted."]
    checks = read_json(docs / "kb_code_checks.json", {})
    if checks:
        summary += ["", "## Code and integration checks", "",
                    f"- Agent offline suite: {checks.get('agent_tests', '?')} passed; Demo 2 suite: {checks.get('demo2_tests', '?')} passed.",
                    "- Regression cases cover exact rank dimensions, source-bound financial conditions, failed fetch/build preservation, and activation/rollback.",
                    f"- Demo 2 shared release smoke: {checks.get('demo2_shared_release', 'pending')}.",
                    f"- Original index backup: `{checks.get('legacy_backup', 'pending')}`."]
    (docs / "KB_REBUILD_VALIDATION.md").write_text("\n".join(summary) + "\n")
    return {"offline_questions": count, "offline_checklist": str(target), "source_inventory": str(docs / "KB_SOURCE_INVENTORY.md")}
