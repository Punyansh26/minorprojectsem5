"""Fetch public primary sources and retain failures without erasing previous evidence."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag

import requests
from bs4 import BeautifulSoup

from assistant.config import settings
from assistant.kb.common import digest, now, read_json, write_json

TOPICS = re.compile(r"admission|scholar|financial|loan|vidya|fee|refund|cut.?off|opening|closing|rank|spot|counsel|calendar|syllabus|curricul|ordinance|regulation|hostel|mess|library|facilit|placement|remuneration|contact|nirf|annual.report|faq|fellowship|seat|vacan|academic|student", re.I)
EXCLUDE = re.compile(r"recruitment|tender|career|vacanc.*(?:post|faculty|staff)|publication|research.paper|login|logout|register|registration\.aspx|facebook|twitter|youtube|gallery", re.I)
ASSETS = (".pdf", ".png", ".jpg", ".jpeg", ".webp")


def approved_host(url: str) -> bool:
    """Limit automatic discovery to public institutional and government publishers."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    domains = ("iiitnr.ac.in", "iiitnr.edu.in", "gov.in", "nic.in", "sbi.co.in", "bank.sbi", "bankofbaroda.in", "aicte-india.org")
    return parsed.scheme in {"https", "http"} and not parsed.username and any(host == d or host.endswith("." + d) for d in domains)


def source_id(url: str) -> str:
    """Give source aliases stable identities independent of their downloaded bytes."""
    return digest(url)[:16]


def html_main(html: str):
    """Prefer article content over menus; preserve tables for a separate extractor."""
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select("script, style, nav, header, footer, aside, noscript, form, .breadcrumb, .breadcrumbs, .menu, #sidebar-first, #sidebar-second"):
        item.decompose()
    content = (soup.select_one(".field-name-body") or soup.select_one(".field--name-body")
               or soup.select_one("article") or soup.select_one("main")
               or soup.select_one("#content") or soup.body or soup)
    return soup, content


def discover_links(html: str, source: dict) -> list[dict]:
    """Follow topical public links and information images within the source article."""
    soup = BeautifulSoup(html, "html.parser")
    _, main = html_main(html)
    results = []
    for a in soup.find_all("a", href=True):
        url = urldefrag(urljoin(source["url"], a["href"]))[0]
        title = a.get_text(" ", strip=True)
        label = title + " " + urlsplit(url).path
        if approved_host(url) and TOPICS.search(label) and not EXCLUDE.search(label):
            if re.search(r"20(?:0\d|1\d|2[01])", label):
                continue
            results.append({"url": url, "title": title or urlsplit(url).path.rsplit("/", 1)[-1],
                            "category": source.get("category", "general"),
                            "topic": source.get("topic", "general"), "discovered_from": source["url"],
                            "verification_status": "needs_review", "years": []})
    for img in main.find_all("img", src=True):
        url = urldefrag(urljoin(source["url"], img["src"]))[0]
        if approved_host(url) and not re.search(r"logo|icon|banner|bullet|social|arrow", url, re.I):
            results.append({"url": url, "title": img.get("alt") or source["title"] + " — image",
                            "category": source.get("category", "general"),
                            "topic": source.get("topic", "general"), "discovered_from": source["url"],
                            "verification_status": "needs_review", "years": source.get("years", [])})
    return results


def fetch_one(source: dict, state_dir: Path) -> dict:
    """Keep raw bytes and exact retrieval provenance; failures never refresh checked_at."""
    result = {**source, "id": source.get("id", source_id(source["url"])), "attempted_at": now()}
    if not approved_host(source["url"]):
        return {**result, "fetch_status": "rejected_host"}
    try:
        url = source["url"]
        response = None
        for redirect in range(6):
            response = requests.get(url, timeout=(5, settings.KB_HTTP_TIMEOUT), stream=True,
                                    allow_redirects=False, headers={"User-Agent": "IIITNR-KnowledgeAudit/2.0 (public academic helpdesk sources)"})
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                response.close()
                if not approved_host(url):
                    raise ValueError("Unapproved redirect")
                continue
            break
        if response is None:
            raise ValueError("No response")
        with response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Too many redirects")
            chunks, total = [], 0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > settings.KB_MAX_DOWNLOAD_BYTES:
                    raise ValueError("Document exceeds configured size limit")
                chunks.append(chunk)
            body = b"".join(chunks)
            mime = response.headers.get("Content-Type", "").split(";")[0]
        if body.startswith(b"%PDF"):
            ext = ".pdf"
        elif mime.startswith("image/"):
            ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime)
            if ext is None:
                raise ValueError("Unsupported image")
        elif b"<html" in body[:10000].lower() or "html" in mime:
            ext = ".html"
            if urlsplit(url).path.lower().endswith(".pdf"):
                raise ValueError("HTML returned for PDF URL")
            soup = BeautifulSoup(body, "html.parser")
            if len(soup.get_text(" ", strip=True)) < 100 or re.search(r"access denied|verify you are human|request rejected", soup.get_text()[:500], re.I):
                raise ValueError("Empty page or access challenge")
        else:
            raise ValueError("Unsupported response type")
        checksum = digest(body)
        relative = Path("raw") / (checksum + ext)
        target = state_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(body)
        changed = source.get("sha256") and source["sha256"] != checksum
        result.update(path=relative.as_posix(), sha256=checksum, content_type=mime,
                      final_url=url, fetched_at=now(), fetch_status="ok", bytes=len(body))
        if changed:
            result["verification_status"] = "needs_review"
        result.pop("fetch_error", None)
    except (requests.RequestException, ValueError) as error:
        result.update(fetch_status="failed", fetch_error=type(error).__name__)
        if isinstance(error, requests.HTTPError):
            result["http_status"] = error.response.status_code
    return result


def refresh(registry: Path, state_dir: Path, discover: bool = False, only_new: bool = False) -> dict:
    """Refresh bounded source batches while preserving past successful copies and reviews."""
    seeds = read_json(registry, {}).get("sources", [])
    existing = read_json(state_dir / "sources.json", {"sources": []})["sources"]
    by_url = {s["url"]: s for s in existing if s.get("url") and s.get("fetch_method") != "public_form"}
    known_urls = set(by_url)
    for seed in seeds:
        by_url[seed["url"]] = {**by_url.get(seed["url"], {}), **seed}
    pending = [s for url, s in by_url.items() if s.get("source_status") != "retired" and (not only_new or url not in known_urls)]
    visited = set()
    all_sources = {s["id"]: s for s in existing if s.get("id")}
    for depth in range(3 if discover else 1):
        pending = [s for s in pending if s["url"] not in visited and (not only_new or s["url"] not in known_urls)][:max(0, settings.KB_MAX_SOURCES - len(visited))]
        if not pending:
            break
        next_batch = []
        with ThreadPoolExecutor(max_workers=min(settings.KB_THREADS, 4)) as pool:
            for result in pool.map(lambda s: fetch_one(s, state_dir), pending):
                visited.add(result["url"])
                all_sources[result["id"]] = result
                print(result["fetch_status"], result["url"], flush=True)
                write_json(state_dir / "sources.json", {"updated_at": now(), "sources": list(all_sources.values())})
                if discover and result.get("fetch_status") == "ok" and result["path"].endswith(".html"):
                    next_batch.extend(discover_links((state_dir / result["path"]).read_text(errors="replace"), result))
        pending = list({s["url"]: by_url.get(s["url"], s) for s in next_batch}.values())
        if pending:
            time.sleep(0.5)
    return {"attempted": len(visited), "ok": sum(s.get("fetch_status") == "ok" for s in all_sources.values()),
            "failed": sum(s.get("fetch_status") == "failed" for s in all_sources.values())}


def register_local(kb_dir: Path, registry: Path, state_dir: Path) -> None:
    """Retain supplied documents as local copies, never claim a fresh remote verification."""
    configured = read_json(registry, {}).get("local_sources", {})
    manifest = read_json(state_dir / "sources.json", {"sources": []})
    sources = {s["id"]: s for s in manifest["sources"]}
    for path in sorted(kb_dir.rglob("*")):
        if path.suffix.lower() not in {".pdf", ".txt"} or not path.is_file():
            continue
        relative = path.relative_to(kb_dir).as_posix()
        metadata = configured.get(relative, {})
        key = "local-" + digest(relative)[:16]
        body = path.read_bytes()
        raw = Path("raw") / (digest(body) + path.suffix.lower())
        (state_dir / "raw").mkdir(parents=True, exist_ok=True)
        if not (state_dir / raw).exists():
            (state_dir / raw).write_bytes(body)
        sources[key] = {**metadata, "id": key, "path": raw.as_posix(), "source_file": relative,
                        "title": metadata.get("title", path.stem), "category": relative.split("/")[0],
                        "sha256": digest(body), "bytes": len(body), "fetch_status": "local_copy",
                        "verification_status": metadata.get("verification_status", "needs_review"),
                        "registered_at": now(), "years": metadata.get("years", [])}
    write_json(state_dir / "sources.json", {"updated_at": now(), "sources": list(sources.values())})
