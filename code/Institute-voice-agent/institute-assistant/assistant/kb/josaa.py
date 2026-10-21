"""Read public JoSAA rank filters; never submit applications or candidate information."""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from assistant.kb.common import digest, now, read_json, write_json
from assistant.kb.extraction import make_block
from assistant.kb.sources import source_id

CURRENT = "https://josaa.admissions.nic.in/Applicant/SeatAllotmentResult/currentorcr.aspx"
ARCHIVE = "https://josaa.admissions.nic.in/applicant/seatmatrix/openingclosingrankarchieve.aspx"


def published_year(html):
    """Read the selected archive year or authoritative counselling heading, never the clock."""
    soup = BeautifulSoup(html,"html.parser")
    selector = soup.find("select",attrs={"name":re.compile(r"ddlYear$",re.I)})
    if selector is None:
        selector = soup.find("select",id=re.compile(r"ddlYear$",re.I))
    if selector:
        selected = selector.find("option",selected=True)
        if selected and re.fullmatch(r"20\d{2}",selected.get("value","")):
            return int(selected["value"])
    heading = soup.find(id=re.compile(r"lblCounsellingBoardHeader$",re.I))
    years = re.findall(r"\b20\d{2}\b",heading.get_text(" ",strip=True) if heading else "")
    if len(set(years)) != 1:
        raise ValueError("Public rank page does not establish a unique admission year")
    return int(years[0])


class RankForm:
    """Preserve ASP.NET view state for public dependent dropdown lookups."""

    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        response = self.session.get(url, timeout=(10, 45))
        response.raise_for_status()
        self.html = response.text

    @property
    def soup(self):
        return BeautifulSoup(self.html, "html.parser")

    def name(self, suffix):
        item = self.soup.find("select", attrs={"name": re.compile(re.escape(suffix) + "$", re.I)})
        if item is None:
            raise ValueError("Public rank form changed: " + suffix)
        return item["name"]

    def options(self, suffix):
        item = self.soup.find("select", attrs={"name": self.name(suffix)})
        return [(option.get("value", ""), option.get_text(" ", strip=True)) for option in item.find_all("option")]

    def submit(self, suffix=None, value=None, button=False):
        """Perform a public search form postback using only server-provided values."""
        soup = self.soup
        data = {i["name"]: i.get("value", "") for i in soup.select("input[type=hidden][name]")}
        for select in soup.select("select[name]"):
            selected = select.find("option", selected=True) or select.find("option")
            if selected:
                data[select["name"]] = selected.get("value", "")
        if button:
            submit = soup.find("input", attrs={"type": re.compile(r"submit", re.I)})
            if submit is None:
                raise ValueError("Public rank search submit button missing")
            data[submit["name"]] = submit.get("value", "Submit")
            data["__EVENTTARGET"] = ""
        else:
            control = self.name(suffix)
            data[control] = value
            data["__EVENTTARGET"] = control
            data["__EVENTARGUMENT"] = ""
        response = self.session.post(self.url, data=data, timeout=(10, 45))
        response.raise_for_status()
        self.html = response.text
        time.sleep(.25)


def collect_ranks(state: Path, years: list[int]) -> dict:
    """Persist each full result page and exact IIIT-NR rows for all published rounds."""
    records, blocks, audits = [], [], []
    for year in years:
        try:
            form = RankForm(CURRENT)
            if published_year(form.html) != year:
                form = RankForm(ARCHIVE)
                form.submit("ddlYear", str(year))
            if published_year(form.html) != year:
                raise ValueError("Requested and published rank years differ")
            rounds = [value for value, label in form.options("ddlroundno") if value.isdigit() and int(value) > 0]
            for round_no in rounds:
                form.submit("ddlroundno", round_no)
                types = [(v, label) for v, label in form.options("ddlInstype") if "information" in label.lower() or "iiit" in label.lower() or "government" in label.lower() or "gfti" in label.lower()]
                found = False
                for institute_type, label in types:
                    form.submit("ddlInstype", institute_type)
                    choices = [(v, text) for v, text in form.options("ddlInstitute") if "naya raipur" in text.casefold() or "naya raipur" in text.replace("-", " ").casefold()]
                    if not choices:
                        continue
                    found = True
                    form.submit("ddlInstitute", choices[0][0])
                    branches = form.options("ddlBranch")
                    all_branch = next((v for v, label in branches if label.lower() in {"all", "all programs", "all programmes"}), None)
                    if all_branch is None:
                        raise ValueError("All-programmes selector missing")
                    form.submit("ddlBranch", all_branch)
                    all_category = next((v for v, label in form.options("ddlSeattype") if label.lower() == "all"), None)
                    if all_category is None:
                        raise ValueError("All-categories selector missing")
                    form.submit("ddlSeattype", all_category)
                    form.submit(button=True)
                    if published_year(form.html) != year:
                        raise ValueError("Rank year changed during form navigation")
                    raw = form.html.encode()
                    checksum = digest(raw)
                    path = Path("raw") / (checksum + ".html")
                    (state / "raw").mkdir(parents=True, exist_ok=True)
                    (state / path).write_bytes(raw)
                    source = {"id": f"josaa-{year}-{round_no}", "sha256": checksum, "url": form.url,
                              "title": f"JoSAA {year} Round {round_no} IIIT Naya Raipur opening and closing ranks",
                              "source_file": f"JoSAA_{year}_round_{round_no}.html", "category": "admissions",
                              "topic": "cutoffs", "years": [year], "period": f"Admission {year}; JoSAA round {round_no}",
                              "fetched_at": now(), "path": path.as_posix(), "fetch_status": "ok",
                              "verification_status": "approved_official_table"}
                    count = 0
                    for table in form.soup.find_all("table"):
                        rows = table.find_all("tr")
                        if not rows:
                            continue
                        header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["td", "th"])]
                        if not any("Opening Rank" in h for h in header):
                            continue
                        for tr in rows[1:]:
                            values = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                            if len(values) != len(header):
                                continue
                            row = dict(zip(header, values))
                            institute = next((v for k, v in row.items() if "Institute" in k), "")
                            if "naya raipur" not in institute.casefold():
                                continue
                            program = next(v for k, v in row.items() if "Academic Program" in k)
                            branch = "DSAI" if "Data Science" in program else "CSE" if "Computer Science" in program else "ECE" if "Electronics" in program else program
                            seat = next(v for k, v in row.items() if "Seat Type" in k or "Seat Category" in k)
                            basis = "PwD category rank" if "PwD" in seat else "CRL" if seat == "OPEN" else "Category rank"
                            opening, closing = row["Opening Rank"], row["Closing Rank"]
                            if "P" in opening or "P" in closing:
                                basis += " (preparatory)"
                            text = "\n".join(f"{key}: {value}" for key, value in row.items()) + f"\nYear: {year}\nRound: {round_no}\nRank basis: {basis}"
                            block = make_block(source, -1, "cutoff", text, verification_status="approved", extraction_method="official_html_table")
                            blocks.append(block)
                            records.append({"kind": "cutoff", "year": year, "authority": "JoSAA", "round": round_no,
                                "programme": branch, "quota": row.get("Quota", ""), "seat_category": seat.replace("EWS", "GEN-EWS"),
                                "gender_pool": row.get("Gender", ""), "rank_basis": basis,
                                "opening_rank": opening, "closing_rank": closing,
                                "evidence_block_id": block["id"], "source_sha256": checksum})
                            count += 1
                    audits.append({"year": year, "round": round_no, "rows": count, "source": source})
                    print(f"JoSAA {year} round {round_no}: {count} rows", flush=True)
                    break
                if not found:
                    audits.append({"year": year, "round": round_no, "error": "Institute not present in selectable groups"})
        except Exception as error:
            audits.append({"year": year, "error": type(error).__name__, "detail": str(error)[:120] if isinstance(error, ValueError) else "Public rank endpoint unavailable"})
            print(f"JoSAA {year}: {type(error).__name__}", flush=True)
        write_json(state / "josaa_audit.json", audits)
        write_json(state / "josaa_blocks.json", blocks)
        write_json(state / "josaa_records.json", records)
    return {"records": len(records), "audits": audits}
