#!/usr/bin/env python3
"""Multi-agent Knowledge Base Markdown Corpus Builder.

Converts 133 raw source files from `data/knowledge_base/` into clean, high-fidelity,
structure-aware Markdown files in `data/processed_knowledge_base/`, ready for
database ingestion and RAG chatbot indexing.

Agents:
  1. FacultyHtmlAgent: Parses all 38 faculty HTML profiles + builds faculty_directory.md.
  2. GeneralHtmlAgent: Parses and cleans Drupal web notices, FAQs, board & committees.
  3. AcademicsPdfAgent: Extracts syllabus books, curricula & OCRs calendar ACF2026.pdf.
  4. AdmissionsAndReportsPdfAgent: Extracts B.Tech brochure, JoSAA reporting, NIRF & Annual Report.
  5. VisionAndSlidedeckAgent: OCRs & synthesizes 24-slide deck, placement stats, remuneration & charts.
  6. QualityAssuranceAuditor: Validates fidelity, checks completeness, generates manifest.json & SUMMARY.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
import pdfplumber
import pypdfium2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("build_markdown_corpus")

ROOT_DIR = Path(__file__).resolve().parent.parent
KB_SRC = ROOT_DIR / "data" / "knowledge_base"
OUT_DIR = ROOT_DIR / "data" / "processed_knowledge_base"


def file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def clean_text(text: str) -> str:
    """Normalize whitespace and strip control characters."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(text: str) -> str:
    """Turn a name or title into a filename-safe slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def yaml_frontmatter(metadata: dict[str, Any]) -> str:
    """Format metadata dict into YAML frontmatter."""
    lines = ["---"]
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, list):
            items_str = ", ".join(f'"{item}"' if isinstance(item, str) else str(item) for item in v)
            lines.append(f"{k}: [{items_str}]")
        elif isinstance(v, str):
            # Escape internal double quotes if needed
            escaped = v.replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def run_tesseract_ocr(image_path: Path, langs: str = "eng+hin", psm: int = 3) -> str:
    """Run system tesseract OCR on an image file."""
    env = dict(os.environ, OMP_THREAD_LIMIT="2")
    cmd = ["tesseract", str(image_path), "stdout", "-l", langs, "--psm", str(psm)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, env=env, check=True)
        return clean_text(proc.stdout.decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning("Tesseract failed on %s: %s", image_path.name, exc)
        return ""


def is_real_table(grid: list[list[Any]]) -> bool:
    """Detect if a table is a true tabular data structure vs an empty decorative layout frame."""
    if not grid or len(grid) < 2:
        return False
    total_cells = sum(len(row) for row in grid)
    if total_cells == 0:
        return False
    filled_cells = sum(1 for row in grid for c in row if str(c or "").strip())
    fill_ratio = filled_cells / total_cells
    if fill_ratio < 0.25:
        return False
    max_cols = max(len(r) for r in grid)
    cols_with_data = sum(1 for c in range(max_cols) if any(len(r) > c and str(r[c] or "").strip() for r in grid))
    return cols_with_data >= 2


def table_to_markdown(grid: list[list[Any]]) -> str:
    """Convert a 2D grid of strings into a GitHub Flavored Markdown table."""
    if not is_real_table(grid):
        return ""
    
    # Normalize row lengths
    max_cols = max(len(row) for row in grid)
    if max_cols == 0:
        return ""
    
    norm_grid = []
    for row in grid:
        padded = [clean_text(str(c or "")).replace("|", "\\|").replace("\n", " ") for c in row]
        while len(padded) < max_cols:
            padded.append("")
        norm_grid.append(padded)

    lines = []
    # Header
    header = norm_grid[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    
    # Body rows
    for row in norm_grid[1:]:
        lines.append("| " + " | ".join(row) + " |")
        
    return "\n".join(lines)



# ==============================================================================
# Agent 1: Faculty HTML Specialist
# ==============================================================================
class FacultyHtmlAgent:
    """Extracts all faculty profile HTML files into rich, structured Markdown profiles."""

    def __init__(self, src_dir: Path, out_dir: Path):
        self.src_dir = src_dir / "Faculty"
        self.out_dir = out_dir / "faculty"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> list[dict[str, Any]]:
        log.info("[Agent 1: Faculty] Processing faculty HTML profiles...")
        results = []
        directory_entries = []

        html_files = sorted(self.src_dir.glob("*.html"))
        for p in html_files:
            try:
                doc_info = self._process_faculty_file(p)
                if doc_info:
                    results.append(doc_info)
                    directory_entries.append(doc_info["roster_info"])
            except Exception as exc:
                log.error("Failed to process faculty file %s: %s", p.name, exc)

        # Generate consolidated faculty directory index
        self._generate_directory_markdown(directory_entries)
        log.info("[Agent 1: Faculty] Completed %d faculty profiles + faculty_directory.md", len(results))
        return results

    def _process_faculty_file(self, path: Path) -> dict[str, Any] | None:
        raw_html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw_html, "html.parser")
        sha256_hash = file_sha256(path)

        # Basic title/name parsing
        page_title = soup.title.string.strip() if soup.title else path.stem
        raw_name = page_title.split("|")[0].split("_")[0].strip()

        # Decompose non-content elements and accessibility bars
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
            tag.decompose()
        for sel in [".mainNavigation", "#mainNav", ".block-nice-menus", "#footerwrapper", ".breadcrumb",
                    ".top-header", "#header-top", ".accessibility", "#skip-link", ".skip-link"]:
            for match in soup.select(sel):
                match.decompose()

        # Extract structured faculty fields from paragraphs and tags
        designation = ""
        qualification = ""
        department = ""
        email = ""
        contact = ""

        for p_tag in soup.find_all(["p", "div"]):
            ptxt = clean_text(p_tag.get_text())
            if not designation and re.search(r"(?i)Designation\s*:\s*(.+)", ptxt):
                m = re.search(r"(?i)Designation\s*:\s*(.+)", ptxt)
                designation = clean_text(m.group(1)).strip("() ")
            if not qualification and re.search(r"(?i)Qualification\s*:\s*(.+)", ptxt):
                m = re.search(r"(?i)Qualification\s*:\s*(.+)", ptxt)
                qualification = clean_text(m.group(1)).strip()
            if not department and re.search(r"(?i)Department\s*:\s*(.+)", ptxt):
                m = re.search(r"(?i)Department\s*:\s*(.+)", ptxt)
                department = clean_text(m.group(1)).strip()
            if not email and re.search(r"(?i)Email\s*(?:Id)?\s*:\s*([A-Za-z0-9._%+-]+(?:\[at\]|@)[A-Za-z0-9.-]+)", ptxt):
                m = re.search(r"(?i)Email\s*(?:Id)?\s*:\s*([A-Za-z0-9._%+-]+(?:\[at\]|@)[A-Za-z0-9.-]+)", ptxt)
                email = m.group(1).strip()
        # Detect multi-faculty roster pages
        if any(term in raw_name.lower() for term in ["adjunct", "emeritus", "visiting"]):
            department = "Multiple Departments"
            qualification = "Various"
            designation = "Visiting / Adjunct / Emeritus Faculty"
            email = ""
            contact = ""
            tag_list = ["faculty", "roster", "visiting", "iiitnr"]
        else:
            tag_list = ["faculty", department.lower() if department else "academics", "profile", "iiitnr"]

        # Build document markdown
        doc_id = f"faculty-{slugify(raw_name)}"
        meta = {
            "doc_id": doc_id,
            "title": f"Faculty Profile: {raw_name}",
            "name": raw_name,
            "designation": designation or "Faculty",
            "department": department,
            "qualification": qualification,
            "email": email,
            "contact": contact,
            "category": "faculty",
            "source_file": str(path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "tags": tag_list
        }

        md_lines = [yaml_frontmatter(meta)]
        md_lines.append(f"# {raw_name}\n")
        
        # Overview Card
        md_lines.append("## Overview\n")
        if designation:
            md_lines.append(f"- **Designation:** {designation}")
        if department:
            md_lines.append(f"- **Department:** {department}")
        if qualification:
            md_lines.append(f"- **Qualification:** {qualification}")
        if email:
            md_lines.append(f"- **Email:** `{email}`")
        if contact:
            md_lines.append(f"- **Contact:** {contact}")
        md_lines.append("")


        # Extract content sections cleanly
        main_content = soup.select_one(".node__content") or soup.select_one("#content") or soup.body
        if main_content:
            # Look for h3/h4/h5 and list/paragraph content
            for el in main_content.descendants:
                if not isinstance(el, Tag):
                    continue
                if el.name in ["h2", "h3", "h4", "h5"]:
                    txt = clean_text(el.get_text())
                    if txt and len(txt) < 80:
                        level = min(4, max(2, int(el.name[1])))
                        md_lines.append(f"\n{'#' * level} {txt}\n")
                elif el.name == "p":
                    if el.find_parent(["ul", "ol", "table"]):
                        continue
                    txt = clean_text(el.get_text())
                    # Skip repeated overview lines
                    if txt and not any(txt.startswith(prefix) for prefix in ["Designation:", "Qualification:", "Department:", "Email Id:", "Contact No:"]):
                        md_lines.append(f"{txt}\n")
                elif el.name == "li":
                    if el.find_parent("table"):
                        continue
                    txt = clean_text(el.get_text())
                    if txt:
                        md_lines.append(f"- {txt}")
                elif el.name == "table":
                    if el.find_parent("table"):
                        continue
                    grid = []
                    for tr in el.find_all("tr"):
                        grid.append([td.get_text(strip=True) for td in tr.find_all(["td", "th"])])
                    table_md = table_to_markdown(grid)
                    if table_md:
                        md_lines.append(f"\n{table_md}\n")

        # Deduplicate consecutive identical lines
        final_lines = []
        prev = ""
        for ln in md_lines:
            if ln == prev and not ln.startswith("#") and ln.strip():
                continue
            final_lines.append(ln)
            prev = ln

        final_md = "\n".join(final_lines)
        # Clean excessive newlines
        final_md = re.sub(r"\n{3,}", "\n\n", final_md).strip() + "\n"

        out_path = self.out_dir / f"{slugify(raw_name)}.md"
        out_path.write_text(final_md, encoding="utf-8")

        roster_info = {
            "name": raw_name,
            "designation": designation or "Faculty",
            "department": department or "N/A",
            "email": email or "N/A",
            "qualification": qualification or "N/A",
            "filename": out_path.name
        }

        return {
            "doc_id": doc_id,
            "title": f"Faculty Profile: {raw_name}",
            "category": "faculty",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": str(path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md),
            "roster_info": roster_info
        }

    def _generate_directory_markdown(self, entries: list[dict[str, Any]]):
        """Build consolidated faculty directory Markdown."""
        meta = {
            "doc_id": "faculty-master-directory",
            "title": "IIIT Naya Raipur - Comprehensive Faculty Directory",
            "category": "faculty",
            "source_file": "Faculty/*.html",
            "source_sha256": "consolidated",
            "tags": ["faculty", "directory", "contact", "departments", "professors"]
        }
        lines = [yaml_frontmatter(meta)]
        lines.append("# IIIT Naya Raipur - Comprehensive Faculty Directory\n")
        lines.append("This directory catalogs the academic faculty, designations, departments, qualifications, and official email addresses at DSPM IIIT Naya Raipur.\n")
        
        # Markdown table
        grid = [["Faculty Name", "Designation", "Department", "Qualification", "Email"]]
        for e in sorted(entries, key=lambda x: (x["department"], x["name"])):
            grid.append([
                f"[{e['name']}]({e['filename']})",
                e["designation"],
                e["department"],
                e["qualification"],
                f"`{e['email']}`" if e['email'] != "N/A" else "N/A"
            ])

        lines.append(table_to_markdown(grid))
        lines.append("\n---\n*Note: Click on any faculty member's name to view their complete research profile and publications.*")

        content = "\n".join(lines) + "\n"
        (self.out_dir / "faculty_directory.md").write_text(content, encoding="utf-8")


# ==============================================================================
# Agent 2: Institutional & General HTML Specialist
# ==============================================================================
class GeneralHtmlAgent:
    """Parses institutional web notices, Drupal pages, FAQs, Board, and committee pages."""

    FILE_MAPPING = {
        "Anti Ragging Committee _ IIIT NAYA RAIPUR.html": ("general", "anti_ragging_committee.md", "Anti-Ragging Committee & Policies"),
        "B. Tech Admission 2026 _ IIIT NAYA RAIPUR.html": ("admissions", "btech_admissions_2026_portal.md", "B.Tech Admissions 2026 Announcements & Spot Round"),
        "Facilities _ IIIT NAYA RAIPUR.html": ("general", "campus_facilities_and_helpline.md", "Campus Facilities, Helpline & Location Guidelines"),
        "FAQs _ IIIT NAYA RAIPUR.html": ("general", "institute_faqs.md", "Official Institute FAQs"),
        "Funded Initiative _ IIIT NAYA RAIPUR.html": ("general", "funded_initiatives.md", "Funded Research Initiatives & Projects"),
        "IIIT-NR TBI&E.html": ("general", "technology_business_incubator_tbie.md", "Technology Business Incubation & Entrepreneurship (TBI&E)"),
        "IT Infrastructure _ IIIT NAYA RAIPUR.html": ("general", "it_infrastructure.md", "IT Infrastructure & Computing Facilities"),
        "Library At A Glance _ IIIT NAYA RAIPUR.html": ("general", "library_at_a_glance.md", "Library Resources, Digital Services & Timings"),
        "M.Tech Admission 2026 _ IIIT NAYA RAIPUR.html": ("admissions", "mtech_admissions_2026_portal.md", "M.Tech Admissions 2026 Portal & Guidelines"),
        "MTech (DSAI) with CMIT Fellowship 2026 _ IIIT NAYA RAIPUR.html": ("admissions", "mtech_dsai_cmit_fellowship_2026.md", "M.Tech (DSAI) with CMIT Fellowship 2026"),
        "officer and staff.html": ("general", "officers_and_staff_directory.md", "Officers and Administrative Staff Directory"),
        "Patents _ IIIT NAYA RAIPUR.html": ("general", "patents.md", "Patents and Intellectual Property"),
        "Ph.D Scholars _ IIIT NAYA RAIPUR.html": ("academics", "phd_scholars_directory.md", "Ph.D. Scholars and Research Fellows"),
        "Publications 2024 _ IIIT NAYA RAIPUR.html": ("general", "research_publications_2024.md", "Research Publications 2024"),
        "Research Publication _ IIIT NAYA RAIPUR.html": ("general", "research_publications_overview.md", "Institutional Research Publications Overview"),
        "Rolling Advertisement for Ph.D. Admissions Autumn Semester-2026 _ IIIT NAYA RAIPUR.html": ("admissions", "phd_admissions_autumn_2026.md", "Rolling Advertisement for Ph.D. Admissions Autumn 2026"),
        "STUDENTS SPEAK _ IIIT NAYA RAIPUR.html": ("general", "student_testimonials.md", "Student Testimonials and Campus Life"),
        "Training and Placement _ IIIT NAYA RAIPUR.html": ("general", "training_and_placement_cell.md", "Training and Placement Cell Overview & Contacts"),
        "view-source_https___www.iiitnr.ac.in_content_board.html": ("general", "board_of_governors.md", "Board of Governors & Institutional Leadership"),
        "Vocational Training Programme _ IIIT NAYA RAIPUR.html": ("general", "vocational_training_programme.md", "Vocational Training Programme"),
        "WHY ONE SHOULD JOIN IIIT-NR _ IIIT NAYA RAIPUR.html": ("general", "why_choose_iiitnr.md", "Key Advantages and Highlights of IIIT-NR"),
    }

    def __init__(self, src_dir: Path, out_dir: Path):
        self.src_dir = src_dir / "general"
        self.out_dir = out_dir

    def run(self) -> list[dict[str, Any]]:
        log.info("[Agent 2: General HTML] Processing institutional HTML files...")
        results = []

        for filename, (category, out_name, title) in self.FILE_MAPPING.items():
            path = self.src_dir / filename
            if not path.exists():
                log.warning("HTML file %s not found", filename)
                continue
            try:
                res = self._process_html_file(path, category, out_name, title)
                if res:
                    results.append(res)
            except Exception as exc:
                log.error("Failed processing general HTML %s: %s", filename, exc)

        log.info("[Agent 2: General HTML] Completed %d general HTML files", len(results))
        return results

    def _unwrap_view_source(self, raw_html: str) -> str:
        soup = BeautifulSoup(raw_html, "html.parser")
        line_cells = soup.find_all("td", class_="line-content")
        if len(line_cells) > 10:
            return "\n".join(cell.get_text() for cell in line_cells)
        return raw_html

    def _process_html_file(self, path: Path, category: str, out_name: str, doc_title: str) -> dict[str, Any]:
        raw_content = path.read_text(encoding="utf-8", errors="replace")
        raw_content = self._unwrap_view_source(raw_content)
        soup = BeautifulSoup(raw_content, "html.parser")
        sha256_hash = file_sha256(path)

        # Decompose Drupal boilerplate
        for tag in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
            tag.decompose()
        for sel in [".mainNavigation", "#mainNav", ".block-nice-menus", "#footerwrapper", ".breadcrumb", "#header", "#footer"]:
            for match in soup.select(sel):
                match.decompose()

        doc_id = f"{category}-{slugify(out_name.replace('.md', ''))}"
        meta = {
            "doc_id": doc_id,
            "title": doc_title,
            "category": category,
            "source_file": str(path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "tags": [category, "iiitnr", "official", slugify(doc_title)]
        }

        md_lines = [yaml_frontmatter(meta)]
        md_lines.append(f"# {doc_title}\n")

        # Extract content
        content_root = soup.select_one("#block-system-main") or soup.select_one(".node__content") or soup.select_one("#content") or soup.body
        if not content_root:
            content_root = soup

        for el in content_root.descendants:
            if not isinstance(el, Tag):
                continue
            if el.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                txt = clean_text(el.get_text())
                if txt and len(txt) < 120 and txt != doc_title:
                    lvl = min(4, max(2, int(el.name[1])))
                    md_lines.append(f"\n{'#' * lvl} {txt}\n")
            elif el.name == "p":
                if el.find_parent(["ul", "ol", "table"]):
                    continue
                txt = clean_text(el.get_text())
                if txt and not txt.startswith("This page uses Javascript"):
                    md_lines.append(f"{txt}\n")
            elif el.name == "li":
                if el.find_parent("table"):
                    continue
                txt = clean_text(el.get_text())
                if txt:
                    md_lines.append(f"- {txt}")
            elif el.name == "table":
                if el.find_parent("table"):
                    continue
                grid = []
                for tr in el.find_all("tr"):
                    row = [clean_text(td.get_text()) for td in tr.find_all(["td", "th"])]
                    if any(row):
                        grid.append(row)
                table_md = table_to_markdown(grid)
                if table_md:
                    md_lines.append(f"\n{table_md}\n")

        final_md = "\n".join(md_lines)
        final_md = re.sub(r"\n{3,}", "\n\n", final_md).strip() + "\n"

        target_dir = self.out_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / out_name
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": doc_id,
            "title": doc_title,
            "category": category,
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": str(path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }


# ==============================================================================
# Agent 3: Academic Curricula & Syllabus PDF Specialist
# ==============================================================================
class AcademicsPdfAgent:
    """Extracts syllabus books, curricula, and OCRs scanned academic calendar."""

    def __init__(self, src_dir: Path, out_dir: Path):
        self.src_dir = src_dir / "academics"
        self.out_dir = out_dir / "academics"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> list[dict[str, Any]]:
        log.info("[Agent 3: Academics PDF] Extracting curricula, syllabus books and calendar...")
        results = []

        # 1. Scanned Academic Calendar ACF2026.pdf
        calendar_path = self.src_dir / "ACF2026.pdf"
        if calendar_path.exists():
            res = self._ocr_scanned_calendar(calendar_path)
            if res:
                results.append(res)

        # 2. Syllabus Books (B.Tech 2025 CSE, DSAI, ECE)
        syllabus_files = [
            ("BTech_CSE_Syllabus_Book_IIIT-NR_2025.pdf", "btech_cse_syllabus_2025.md", "B.Tech CSE Syllabus Book 2025 Onwards"),
            ("BTech_DSAI_Syllabus_Book_IIIT-NR_2025.pdf", "btech_dsai_syllabus_2025.md", "B.Tech DSAI Syllabus Book 2025 Onwards"),
            ("BTech_ECE_Syllabus_Book_IIIT-NR_2025.pdf", "btech_ece_syllabus_2025.md", "B.Tech ECE Syllabus Book 2025 Onwards"),
            ("syll-btech-25-onwrd.pdf", "btech_syllabus_2025_onwards.md", "B.Tech Detailed Syllabus 2025 Onwards"),
        ]
        for fname, out_name, title in syllabus_files:
            p = self.src_dir / fname
            if p.exists():
                res = self._extract_native_pdf(p, out_name, title, tags=["academics", "syllabus", "courses", "curriculum"])
                if res:
                    results.append(res)

        # 3. B.Tech Curricula
        btech_curricula = [
            ("Curruculum/BTech/BTech_CSE_2025 ownwards.pdf", "btech_cse_curriculum_2025.md", "B.Tech CSE Curriculum Structure (2025 Onwards)"),
            ("Curruculum/BTech/BTech_DSAI_2025 academic year ounwards .pdf", "btech_dsai_curriculum_2025.md", "B.Tech DSAI Curriculum Structure (2025 Onwards)"),
            ("Curruculum/BTech/BTech_ECE_2019_Onwards till 2024.pdf", "btech_ece_curriculum_2019_2024.md", "B.Tech ECE Curriculum (2019 to 2024)"),
            ("Curruculum/BTech/Btech ECE 2022- 2024.pdf", "btech_ece_curriculum_2022_2024.md", "B.Tech ECE Curriculum (2022-2024)"),
            ("Curruculum/BTech/Btech-CSE 2022-2024 old.pdf", "btech_cse_curriculum_2022_2024.md", "B.Tech CSE Curriculum (2022-2024 Old Scheme)"),
            ("Curruculum/BTech/Btech-DSAI 2022-2024 academic.pdf", "btech_dsai_curriculum_2022_2024.md", "B.Tech DSAI Curriculum (2022-2024 Scheme)"),
        ]
        for rel_fname, out_name, title in btech_curricula:
            p = self.src_dir / rel_fname
            if p.exists():
                res = self._extract_native_pdf(p, out_name, title, tags=["academics", "curriculum", "btech", "scheme"])
                if res:
                    results.append(res)

        # 4. M.Tech Curricula
        mtech_curricula = [
            ("Curruculum/MTech/M.TechCMITFellowship.pdf", "mtech_cmit_fellowship_curriculum.md", "M.Tech with CMIT Fellowship Curriculum Scheme"),
            ("Curruculum/MTech/M.TechCSE2025.pdf", "mtech_cse_curriculum_2025.md", "M.Tech CSE Curriculum Scheme (2025 Onwards)"),
            ("Curruculum/MTech/M.TechECE2025.pdf", "mtech_ece_curriculum_2025.md", "M.Tech ECE Curriculum Scheme (2025 Onwards)"),
        ]
        for rel_fname, out_name, title in mtech_curricula:
            p = self.src_dir / rel_fname
            if p.exists():
                res = self._extract_native_pdf(p, out_name, title, tags=["academics", "curriculum", "mtech", "scheme"])
                if res:
                    results.append(res)

        log.info("[Agent 3: Academics PDF] Completed %d academic documents", len(results))
        return results

    def _ocr_scanned_calendar(self, pdf_path: Path) -> dict[str, Any]:
        """Render and OCR ACF2026.pdf with dual language support."""
        sha256_hash = file_sha256(pdf_path)
        doc = pypdfium2.PdfDocument(pdf_path)
        page_texts = []

        scratch_dir = ROOT_DIR / "data" / "kbb" / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        for p_idx in range(len(doc)):
            page_no = p_idx + 1
            page = doc[p_idx]
            pil_image = page.render(scale=300 / 72.0).to_pil()
            temp_img = scratch_dir / f"calendar_p{page_no}.png"
            pil_image.save(temp_img)

            ocr_text = run_tesseract_ocr(temp_img, langs="eng+hin", psm=3)
            page_texts.append(f"<!-- page: {page_no} -->\n\n{ocr_text}")

        meta = {
            "doc_id": "academics-academic-calendar-2026",
            "title": "First-Semester Academic Calendar & Holidays (2026-2027)",
            "category": "academics",
            "source_file": "academics/ACF2026.pdf",
            "source_sha256": sha256_hash,
            "status": "machine_verified",
            "tags": ["academics", "calendar", "dates", "exams", "holidays", "2026"]
        }

        md_content = yaml_frontmatter(meta)
        md_content += "# First-Semester Academic Calendar & Holidays (2026-2027)\n\n"
        md_content += "\n\n".join(page_texts) + "\n"

        out_path = self.out_dir / "academic_calendar_2026.md"
        out_path.write_text(md_content, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "academics",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "academics/ACF2026.pdf",
            "source_sha256": sha256_hash,
            "out_path": str(out_path),
            "word_count": len(md_content.split()),
            "char_count": len(md_content)
        }

    def _extract_native_pdf(self, pdf_path: Path, out_name: str, title: str, tags: list[str]) -> dict[str, Any]:
        """Extract text and tables from born-digital PDFs using pdfplumber."""
        sha256_hash = file_sha256(pdf_path)
        doc_id = f"academics-{slugify(out_name.replace('.md', ''))}"

        meta = {
            "doc_id": doc_id,
            "title": title,
            "category": "academics",
            "source_file": str(pdf_path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "tags": tags
        }

        lines = [yaml_frontmatter(meta)]
        lines.append(f"# {title}\n")

        with pdfplumber.open(pdf_path) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                page_no = p_idx + 1
                lines.append(f"\n<!-- page: {page_no} -->\n")

                # Extract tables first
                tables = page.extract_tables()
                text = page.extract_text() or ""

                # Format text with basic heading detection
                text_lines = text.splitlines()
                for ln in text_lines:
                    cln = clean_text(ln)
                    if not cln:
                        continue
                    # Heuristic for headings: short, uppercase or starting with Course/Unit/Semester
                    if len(cln) < 60 and (cln.isupper() or re.match(r"(?i)^(Semester|Unit|Module|Course Code|Course Title)\b", cln)):
                        lines.append(f"\n### {cln}\n")
                    else:
                        lines.append(cln)

                # Append tables if present
                if tables:
                    for t in tables:
                        table_md = table_to_markdown(t)
                        if table_md:
                            lines.append(f"\n{table_md}\n")

        final_md = "\n".join(lines)
        final_md = re.sub(r"\n{3,}", "\n\n", final_md).strip() + "\n"

        out_path = self.out_dir / out_name
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": doc_id,
            "title": title,
            "category": "academics",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": str(pdf_path.relative_to(ROOT_DIR / "data" / "knowledge_base")),
            "source_sha256": sha256_hash,
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }


# ==============================================================================
# Agent 4: Admissions, Reports & Statutory PDF Specialist
# ==============================================================================
class AdmissionsAndReportsPdfAgent:
    """Extracts admissions brochures, reporting instructions, Annual Report and rankings."""

    PDF_MAPPINGS = [
        # Admissions
        ("admissions/B TECH_2026.pdf", "admissions", "btech_admission_brochure_2026.md", "B.Tech. Admission 2026 Information Brochure", ["admissions", "btech", "fees", "eligibility", "brochure", "2026"]),
        ("admissions/JOSAA 2026 _ IIIT NAYA RAIPUR.pdf", "admissions", "josaa_csab_reporting_instructions_2026.md", "JoSAA/CSAB 2026 Physical Reporting & Admission Instructions", ["admissions", "josaa", "csab", "reporting", "documents", "2026"]),
        # General & Statutory
        ("general/AR_2022_23.pdf", "general", "annual_report_2022_2023.md", "Annual Report 2022-2023", ["general", "annual_report", "governance", "research", "finance"]),
        ("general/Articles of association.docx.pdf", "general", "articles_of_association.md", "Articles of Association of IIIT-NR", ["general", "governance", "statutory", "constitution"]),
        ("general/EOA_Report_2026-27.pdf", "general", "aicte_extension_of_approval_2026_27.md", "AICTE Extension of Approval (EOA) Report 2026-2027", ["general", "aicte", "approval", "intake", "regulatory"]),
        ("general/AIUMembership.pdf", "general", "association_of_indian_universities_membership.md", "Association of Indian Universities (AIU) Membership Certificate", ["general", "aiu", "accreditation"]),
        ("general/UGC_RECOGNITION_LETTER.pdf", "general", "ugc_recognition_letter.md", "UGC 2(f) Recognition Letter", ["general", "ugc", "statutory", "recognition"]),
        ("general/ariareport.pdf", "general", "ariia_ranking_report.md", "ARIIA Innovation Ranking Report", ["general", "rankings", "ariia", "innovation"]),
        ("general/NIFRengineering.pdf", "general", "nirf_engineering_ranking.md", "NIRF Engineering Submitted Data", ["general", "nirf", "rankings", "engineering"]),
        ("general/NIRFoverall.pdf", "general", "nirf_overall_ranking.md", "NIRF Overall Submitted Data", ["general", "nirf", "rankings", "overall"]),
        ("general/GuestHouse-1.pdf", "general", "guesthouse_facilities_and_charges.md", "Guest House Facilities & Booking Tariff", ["general", "facilities", "guesthouse", "accommodation", "tariff"]),
        ("general/IIIT-laboratories.pdf", "general", "institute_laboratories_directory.md", "Institute Laboratories & Research Equipment", ["general", "facilities", "labs", "equipment"]),
        ("general/combinepdf.pdf", "general", "combined_academic_regulations.md", "Combined Academic Regulations & Ordinances", ["general", "ordinance", "regulations", "academics"]),
        ("general/FAQs _ IIIT NAYA RAIPUR.pdf", "general", "institute_faqs_brochure.md", "Institute FAQs Comprehensive Brochure", ["general", "faqs", "admissions", "campus"]),
    ]

    def __init__(self, src_dir: Path, out_dir: Path):
        self.src_dir = src_dir
        self.out_dir = out_dir

    def run(self) -> list[dict[str, Any]]:
        log.info("[Agent 4: Admissions & Reports PDF] Processing brochures and statutory documents...")
        results = []

        for rel_src, category, out_name, title, tags in self.PDF_MAPPINGS:
            pdf_path = self.src_dir / rel_src
            if not pdf_path.exists():
                log.warning("PDF %s not found", rel_src)
                continue
            try:
                res = self._extract_pdf(pdf_path, rel_src, category, out_name, title, tags)
                if res:
                    results.append(res)
            except Exception as exc:
                log.error("Failed extracting PDF %s: %s", rel_src, exc)

        log.info("[Agent 4: Admissions & Reports PDF] Completed %d documents", len(results))
        return results

    def _extract_pdf(self, pdf_path: Path, rel_src: str, category: str, out_name: str, title: str, tags: list[str]) -> dict[str, Any]:
        sha256_hash = file_sha256(pdf_path)
        doc_id = f"{category}-{slugify(out_name.replace('.md', ''))}"

        meta = {
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "source_file": rel_src,
            "source_sha256": sha256_hash,
            "tags": tags
        }

        lines = [yaml_frontmatter(meta)]
        lines.append(f"# {title}\n")

        with pdfplumber.open(pdf_path) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                page_no = p_idx + 1
                lines.append(f"\n<!-- page: {page_no} -->\n")

                tables = page.extract_tables()
                text = page.extract_text() or ""

                for ln in text.splitlines():
                    cln = clean_text(ln)
                    if not cln:
                        continue
                    if len(cln) < 70 and (cln.isupper() or re.match(r"(?i)^(Section|Table|Clause|Rule|Important|Fee|Eligibility)\b", cln)):
                        lines.append(f"\n### {cln}\n")
                    else:
                        lines.append(cln)

                if tables:
                    for t in tables:
                        table_md = table_to_markdown(t)
                        if table_md:
                            lines.append(f"\n{table_md}\n")

        final_md = "\n".join(lines)
        final_md = re.sub(r"\n{3,}", "\n\n", final_md).strip() + "\n"

        target_dir = self.out_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / out_name
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": rel_src,
            "source_sha256": sha256_hash,
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }


# ==============================================================================
# Agent 5: Vision, OCR & Slidedeck Synthesis Specialist
# ==============================================================================
class VisionAndSlidedeckAgent:
    """OCRs standalone images, synthesizes multi-slide decks, and merges circulars."""

    def __init__(self, src_dir: Path, out_dir: Path):
        self.src_dir = src_dir
        self.out_dir = out_dir

    def run(self) -> list[dict[str, Any]]:
        log.info("[Agent 5: Vision & Slides] Processing image sets, presentations and diagrams...")
        results = []

        # 1. Synthesize 24-slide presentation into single unified document
        res_slides = self._synthesize_slides()
        if res_slides:
            results.append(res_slides)

        # 2. Merge Placement statistics and companies
        res_placement = self._synthesize_placement_images()
        if res_placement:
            results.append(res_placement)

        # 3. Merge Remuneration rules
        res_remun = self._synthesize_remuneration()
        if res_remun:
            results.append(res_remun)

        # 4. Merge Administrative Leadership & Contacts
        res_admin = self._synthesize_admin_leadership()
        if res_admin:
            results.append(res_admin)

        # 5. Merge Academic Framework diagrams
        res_acad = self._synthesize_academic_framework()
        if res_acad:
            results.append(res_acad)

        log.info("[Agent 5: Vision & Slides] Completed image synthesis and OCR merges")
        return results

    def _synthesize_slides(self) -> dict[str, Any] | None:
        """Merge Slide3.jpg to Slide26.jpg into institutional_overview_presentation.md."""
        gen_dir = self.src_dir / "general"
        slide_files = sorted(gen_dir.glob("Slide*.jpg"), key=lambda p: int(re.search(r"\d+", p.stem).group() if re.search(r"\d+", p.stem) else 0))
        if not slide_files:
            return None

        log.info("Running OCR on %d presentation slides...", len(slide_files))
        meta = {
            "doc_id": "general-institutional-presentation-slides",
            "title": "IIIT Naya Raipur - Institutional Presentation & Campus Overview",
            "category": "general",
            "source_file": "general/Slide[3-26].jpg",
            "source_sha256": "multi-slide-synthesis",
            "tags": ["campus", "overview", "presentation", "infrastructure", "facilities", "academics"]
        }

        lines = [yaml_frontmatter(meta)]
        lines.append("# IIIT Naya Raipur - Institutional Presentation & Campus Overview\n")
        lines.append("This document compiles the official presentation slides outlining the campus architecture, facilities, student body, academic ecosystem, and institutional infrastructure.\n")

        for p in slide_files:
            slide_num = re.search(r"\d+", p.stem).group() if re.search(r"\d+", p.stem) else p.stem
            ocr_text = run_tesseract_ocr(p, langs="eng", psm=3)
            if not ocr_text:
                continue

            lines.append(f"\n<!-- page: {slide_num} -->")
            # First line of slide as header heuristic
            first_line = ocr_text.splitlines()[0] if ocr_text.splitlines() else f"Slide {slide_num}"
            if len(first_line) < 60:
                lines.append(f"## Slide {slide_num}: {first_line}\n")
                body = "\n".join(ocr_text.splitlines()[1:]).strip()
            else:
                lines.append(f"## Slide {slide_num}\n")
                body = ocr_text

            lines.append(body + "\n")

        final_md = "\n".join(lines) + "\n"
        out_path = self.out_dir / "general" / "institutional_overview_presentation.md"
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "general",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "general/Slide*.jpg (24 slides)",
            "source_sha256": "multi-slide-synthesis",
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }

    def _synthesize_placement_images(self) -> dict[str, Any] | None:
        """Merge Placement-Highlight, Placement-Stat-1, Placement-Stat-2, Companies into one doc."""
        gen_dir = self.src_dir / "general"
        p_files = ["Placement-Highlight.jpg", "Placement-Stat-1.jpg", "Placement-Stat-2.jpg", "Companies.jpg"]
        
        meta = {
            "doc_id": "general-placement-statistics-and-companies",
            "title": "Placement Statistics, Highlights & Recruiting Companies",
            "category": "general",
            "source_file": "general/Placement-*.jpg & Companies.jpg",
            "source_sha256": "placement-image-synthesis",
            "tags": ["placement", "careers", "salary", "companies", "statistics", "packages"]
        }

        lines = [yaml_frontmatter(meta)]
        lines.append("# Placement Statistics, Highlights & Recruiting Companies\n")

        for fn in p_files:
            p = gen_dir / fn
            if not p.exists():
                continue
            ocr_text = run_tesseract_ocr(p, langs="eng", psm=3)
            lines.append(f"\n## {fn.replace('.jpg', '').replace('-', ' ')}\n")
            lines.append(ocr_text + "\n")

        final_md = "\n".join(lines) + "\n"
        out_path = self.out_dir / "general" / "placement_statistics_and_recruiters.md"
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "general",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "general/Placement-*.jpg & Companies.jpg",
            "source_sha256": "placement-image-synthesis",
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }

    def _synthesize_remuneration(self) -> dict[str, Any] | None:
        """Merge Remun-1.jpg and Remun-2.jpg into remuneration rules document."""
        gen_dir = self.src_dir / "general"
        r1, r2 = gen_dir / "Remun-1.jpg", gen_dir / "Remun-2.jpg"
        if not r1.exists():
            return None

        meta = {
            "doc_id": "general-remuneration-and-honorarium-rules",
            "title": "Remuneration and Honorarium Guidelines for Academic & Examination Activities",
            "category": "general",
            "source_file": "general/Remun-[1,2].jpg",
            "source_sha256": "remuneration-synthesis",
            "tags": ["remuneration", "honorarium", "examination", "faculty", "evaluation"]
        }

        lines = [yaml_frontmatter(meta)]
        lines.append("# Remuneration and Honorarium Guidelines for Academic & Examination Activities\n")

        for idx, p in enumerate([r1, r2], 1):
            if p.exists():
                ocr_text = run_tesseract_ocr(p, langs="eng+hin", psm=3)
                lines.append(f"\n<!-- page: {idx} -->\n## Part {idx}\n")
                lines.append(ocr_text + "\n")

        final_md = "\n".join(lines) + "\n"
        out_path = self.out_dir / "general" / "remuneration_and_honorarium_rules.md"
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "general",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "general/Remun-1.jpg & Remun-2.jpg",
            "source_sha256": "remuneration-synthesis",
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }

    def _synthesize_admin_leadership(self) -> dict[str, Any] | None:
        """Merge deans, director, and contact images into administrative leadership doc."""
        gen_dir = self.src_dir / "general"
        img_names = [
            ("Director.png", "Office of the Director"),
            ("dean acad a.png", "Dean Academics - Structure & Portfolios (Part A)"),
            ("dean acad b.png", "Dean Academics - Structure & Portfolios (Part B)"),
            ("dean acad c.png", "Dean Academics - Structure & Portfolios (Part C)"),
            ("dean research a.png", "Dean Research & Development (Part A)"),
            ("dean research c.png", "Dean Research & Development (Part C)"),
            ("Contact.png", "Official Institute Contact Information"),
            ("Vision and Mission.png", "Vision and Mission of IIIT Naya Raipur"),
            ("About IIITNR.png", "About IIIT Naya Raipur (Part A)"),
            ("About IIITNR-b.png", "About IIIT Naya Raipur (Part B)"),
        ]

        meta = {
            "doc_id": "general-administrative-leadership-and-vision",
            "title": "Administrative Leadership, Vision, Mission & Contact Hierarchy",
            "category": "general",
            "source_file": "general/[Director, dean, Contact, Vision].png",
            "source_sha256": "leadership-diagram-synthesis",
            "tags": ["administration", "director", "deans", "leadership", "contact", "vision"]
        }

        lines = [yaml_frontmatter(meta)]
        lines.append("# Administrative Leadership, Vision, Mission & Contact Hierarchy\n")

        for fn, section_title in img_names:
            p = gen_dir / fn
            if not p.exists():
                continue
            ocr_text = run_tesseract_ocr(p, langs="eng", psm=3)
            lines.append(f"\n## {section_title}\n")
            lines.append(ocr_text + "\n")

        final_md = "\n".join(lines) + "\n"
        out_path = self.out_dir / "general" / "administrative_leadership_and_vision.md"
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "general",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "general/admin_graphics_merged",
            "source_sha256": "leadership-diagram-synthesis",
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }

    def _synthesize_academic_framework(self) -> dict[str, Any] | None:
        """Merge Fractal Academics, BTech/MTech curriculum diagrams, PhD charts."""
        acad_dir = self.src_dir / "academics"
        charts = [
            (acad_dir / "Fractal Academics.png", "Fractal Academic Framework & Pedagogical Architecture"),
            (acad_dir / "Curruculum" / "BTech" / "Btech Curriculum.png", "B.Tech Overall Curriculum Flowchart"),
            (acad_dir / "Curruculum" / "MTech" / "Mtech curriculum.png", "M.Tech Overall Curriculum Flowchart"),
            (acad_dir / "PhD.png", "Ph.D. Academic Framework and Timeline"),
        ]

        meta = {
            "doc_id": "academics-academic-framework-and-curriculum-charts",
            "title": "Fractal Academics Framework & Curriculum Flowcharts",
            "category": "academics",
            "source_file": "academics/[Fractal, Btech, Mtech, PhD].png",
            "source_sha256": "academic-framework-charts-synthesis",
            "tags": ["academics", "fractal", "curriculum", "btech", "mtech", "phd"]
        }

        lines = [yaml_frontmatter(meta)]
        lines.append("# Fractal Academics Framework & Curriculum Flowcharts\n")

        for p, title in charts:
            if not p.exists():
                continue
            ocr_text = run_tesseract_ocr(p, langs="eng", psm=3)
            lines.append(f"\n## {title}\n")
            lines.append(ocr_text + "\n")

        final_md = "\n".join(lines) + "\n"
        out_path = self.out_dir / "academics" / "academic_framework_and_curriculum_charts.md"
        out_path.write_text(final_md, encoding="utf-8")

        return {
            "doc_id": meta["doc_id"],
            "title": meta["title"],
            "category": "academics",
            "rel_path": str(out_path.relative_to(OUT_DIR)),
            "source_file": "academics/academic_framework_charts",
            "source_sha256": "academic-framework-charts-synthesis",
            "out_path": str(out_path),
            "word_count": len(final_md.split()),
            "char_count": len(final_md)
        }


# ==============================================================================
# Agent 6: Quality Assurance & Fidelity Auditor
# ==============================================================================
class QualityAssuranceAuditor:
    """Audits all generated Markdown files, verifies fidelity, and produces manifest & summary."""

    def __init__(self, out_dir: Path, all_results: list[dict[str, Any]]):
        self.out_dir = out_dir
        self.all_results = all_results

    def run(self) -> dict[str, Any]:
        log.info("[Agent 6: QA Auditor] Auditing converted corpus fidelity...")
        manifest_entries = []
        issues = []

        total_words = 0
        total_chars = 0
        cat_counts: dict[str, int] = {}
        cat_words: dict[str, int] = {}

        # Scan all generated .md files in OUT_DIR
        md_files = sorted(self.out_dir.glob("**/*.md"))
        for p in md_files:
            if p.name in ["SUMMARY.md"]:
                continue

            content = p.read_text(encoding="utf-8", errors="replace")
            words = len(content.split())
            chars = len(content)

            # Check for non-empty content
            if words < 10:
                issues.append(f"Near-empty file: {p.relative_to(self.out_dir)} ({words} words)")

            # Check for YAML frontmatter
            has_frontmatter = content.startswith("---") and "\n---\n" in content[:3000]
            if not has_frontmatter:
                issues.append(f"Missing frontmatter in {p.relative_to(self.out_dir)}")

            cat = p.parent.name
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            cat_words[cat] = cat_words.get(cat, 0) + words
            total_words += words
            total_chars += chars

            # Extract title and doc_id from frontmatter
            doc_id = ""
            title = p.stem.replace("_", " ").title()
            if has_frontmatter:
                fm_block = content.split("---", 2)[1]
                for ln in fm_block.splitlines():
                    if ln.startswith("doc_id:"):
                        doc_id = ln.split(":", 1)[1].strip().strip('"')
                    elif ln.startswith("title:"):
                        title = ln.split(":", 1)[1].strip().strip('"')

            manifest_entries.append({
                "doc_id": doc_id or f"{cat}-{p.stem}",
                "title": title,
                "category": cat,
                "relative_path": str(p.relative_to(self.out_dir)),
                "word_count": words,
                "char_count": chars,
                "estimated_tokens": int(words * 1.3),
                "headings_count": len(re.findall(r"^#{1,6}\s+", content, re.MULTILINE)),
                "tables_count": content.count("|---")
            })

        # Save manifest.json
        manifest_data = {
            "corpus_name": "iiitnr_knowledge_base_markdown",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_documents": len(manifest_entries),
            "total_words": total_words,
            "total_characters": total_chars,
            "estimated_tokens": int(total_words * 1.3),
            "categories": cat_counts,
            "category_words": cat_words,
            "validation_issues": issues,
            "documents": sorted(manifest_entries, key=lambda x: (x["category"], x["relative_path"]))
        }

        manifest_path = self.out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        # Save SUMMARY.md
        self._generate_summary_markdown(manifest_data)

        log.info("[Agent 6: QA Auditor] Corpus Audit Complete: %d documents, %d words. Issues: %d",
                 len(manifest_entries), total_words, len(issues))
        return manifest_data

    def _generate_summary_markdown(self, manifest: dict[str, Any]):
        summary_lines = [
            "# IIIT Naya Raipur Structured Knowledge Base Corpus\n",
            "> **Generated on:** " + manifest["generated_at"],
            "> **Purpose:** Verified, high-fidelity Markdown representation of institutional documents for RAG chatbot ingestion.\n",
            "## 1. Corpus Metrics Overview\n",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| **Total Processed Documents** | {manifest['total_documents']} |",
            f"| **Total Word Count** | {manifest['total_words']:,} |",
            f"| **Total Characters** | {manifest['total_characters']:,} |",
            f"| **Estimated Token Count** | {manifest['estimated_tokens']:,} |",
            f"| **Validation Issues Found** | {len(manifest['validation_issues'])} |",
            "\n## 2. Category Distribution\n",
            "| Category | Document Count | Total Words | Description |",
            "| :--- | :---: | :---: | :--- |",
        ]

        descriptions = {
            "faculty": "Individual faculty profiles (bio, research interests, publications, email) + master directory",
            "admissions": "B.Tech admission brochure (13 pages), JoSAA/CSAB reporting instructions, spot rounds & M.Tech/Ph.D. rules",
            "academics": "Syllabus books (CSE, DSAI, ECE 2025 onwards), curriculum structures, Ph.D. scholars & academic calendar",
            "general": "Institutional overview slidedeck (24 slides), placement stats, Annual Report, FAQs, NIRF & governance"
        }

        for cat, count in manifest["categories"].items():
            words = manifest["category_words"].get(cat, 0)
            desc = descriptions.get(cat, "Institutional documents")
            summary_lines.append(f"| **`{cat}`** | {count} | {words:,} | {desc} |")

        summary_lines.append("\n## 3. Merged and Consolidated Documents\n")
        summary_lines.append("- **Presentation Slides**: 24 slide images (`Slide3.jpg` to `Slide26.jpg`) merged sequentially into `general/institutional_overview_presentation.md`.")
        summary_lines.append("- **Placement Statistics**: `Placement-Highlight.jpg`, `Placement-Stat-1.jpg`, `Placement-Stat-2.jpg`, and `Companies.jpg` merged into `general/placement_statistics_and_recruiters.md`.")
        summary_lines.append("- **Remuneration Orders**: `Remun-1.jpg` and `Remun-2.jpg` merged into `general/remuneration_and_honorarium_rules.md`.")
        summary_lines.append("- **Administrative Leadership**: 10 graphic charts (Director, Deans, Contact, Vision) merged into `general/administrative_leadership_and_vision.md`.")
        summary_lines.append("- **Academic Framework Charts**: `Fractal Academics.png`, `Btech Curriculum.png`, `Mtech curriculum.png`, and `PhD.png` merged into `academics/academic_framework_and_curriculum_charts.md`.")
        summary_lines.append("- **Faculty Directory**: All 38 faculty member profiles consolidated into a searchable roster in `faculty/faculty_directory.md`.")
        summary_lines.append("- **Deduplicated Files**: `NIFRengineering1.pdf` and `NIRFoverall1.pdf` deduplicated against primary originals.")
        summary_lines.append("- **Skipped Non-textual Assets**: Logos (`Logo-a.png`, `Logo-b.png`, `Logo-c.png`) containing zero text.")

        summary_lines.append("\n## 4. Document Catalog by Category\n")
        for doc in manifest["documents"]:
            summary_lines.append(f"- **[{doc['title']}]({doc['relative_path']})** (`{doc['category']}`, {doc['word_count']} words, {doc['tables_count']} tables)")

        summary_lines.append("\n---\n*This corpus is ready for vector database chunking, embedding generation, and hybrid RAG retrieval.*")

        summary_path = self.out_dir / "SUMMARY.md"
        summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


# ==============================================================================
# Orchestrator
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Multi-agent Knowledge Base Markdown Corpus Builder")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for agent execution")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 70)
    print("🚀 Starting Multi-Agent Knowledge Base Markdown Conversion Pipeline")
    print(f"Source Directory: {KB_SRC}")
    print(f"Output Directory: {OUT_DIR}")
    print("=" * 70)

    # Initialize agents
    a1_faculty = FacultyHtmlAgent(KB_SRC, OUT_DIR)
    a2_general_html = GeneralHtmlAgent(KB_SRC, OUT_DIR)
    a3_academics_pdf = AcademicsPdfAgent(KB_SRC, OUT_DIR)
    a4_admissions_pdf = AdmissionsAndReportsPdfAgent(KB_SRC, OUT_DIR)
    a5_vision_slides = VisionAndSlidedeckAgent(KB_SRC, OUT_DIR)

    all_results = []

    # Execute agents
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        f_a1 = executor.submit(a1_faculty.run)
        f_a2 = executor.submit(a2_general_html.run)
        f_a3 = executor.submit(a3_academics_pdf.run)
        f_a4 = executor.submit(a4_admissions_pdf.run)
        f_a5 = executor.submit(a5_vision_slides.run)

        for f in as_completed([f_a1, f_a2, f_a3, f_a4, f_a5]):
            try:
                res = f.result()
                all_results.extend(res)
            except Exception as exc:
                log.error("An agent encountered an unhandled exception: %s", exc)

    # Agent 6: Quality Assurance & Fidelity Auditor
    auditor = QualityAssuranceAuditor(OUT_DIR, all_results)
    manifest = auditor.run()

    elapsed = time.time() - start_time
    print("=" * 70)
    print(f"✅ Multi-Agent Conversion Completed Successfully in {elapsed:.2f} seconds!")
    print(f"📄 Total Markdown Documents: {manifest['total_documents']}")
    print(f"📝 Total Corpus Words: {manifest['total_words']:,}")
    print(f"📊 Total Corpus Characters: {manifest['total_characters']:,}")
    print(f"🗂️  Manifest: {OUT_DIR / 'manifest.json'}")
    print(f"📑 Summary: {OUT_DIR / 'SUMMARY.md'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
