"""Build immutable releases and atomically switch both retrieval stores together."""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from assistant.config import settings
from assistant.kb.common import PIPELINE_VERSION, active_release, digest, now, read_json, write_json
from assistant.kb.embeddings import LocalE5
from assistant.kb.structured import create_database, record_text
from assistant.kb.provenance import finance_parents, financial_spans
from assistant.kb.integrity import content_hashes, content_digest, verify, file_hash


def chunk_block(block: dict, tokenizer) -> list[Document]:
    """Bound model input while retaining section context and complete table rows."""
    heading = "\n".join(x for x in (block["title"], block.get("period", "")) if x)
    heading_tokens = tokenizer.encode(heading, add_special_tokens=False)[:70]
    heading = tokenizer.decode(heading_tokens, skip_special_tokens=True)
    budget = settings.KB_CHUNK_TOKENS - len(heading_tokens) - 10
    text = block["text"]
    pieces = []
    if block["kind"] in {"table", "cutoff"}:
        lines = text.splitlines()
        header = "\n".join(lines[:2])
        header_len = len(tokenizer.encode(header, add_special_tokens=False))
        if header_len >= budget:
            header = ""
        current = header
        for line in lines[2:] if header else lines:
            if len(tokenizer.encode(line, add_special_tokens=False)) > budget:
                raise ValueError(f"Table row exceeds token budget; review block {block['id']}")
            candidate = current + "\n" + line if current else line
            if len(tokenizer.encode(candidate, add_special_tokens=False)) > budget:
                if current.strip():
                    pieces.append(current)
                current = (header + "\n" + line).strip()
                if len(tokenizer.encode(current, add_special_tokens=False)) > budget:
                    raise ValueError(f"Table header plus row exceeds token budget: {block['id']}")
            else:
                current = candidate
        if current.strip():
            pieces.append(current)
    else:
        tokens = tokenizer.encode(text, add_special_tokens=False)
        for start in range(0, len(tokens), max(1, budget - settings.KB_OVERLAP_TOKENS)):
            pieces.append(tokenizer.decode(tokens[start:start + budget], skip_special_tokens=True))
            if start + budget >= len(tokens):
                break
    metadata = {key: value for key, value in block.items() if isinstance(value, (str, int, float, bool)) and key not in {"text", "review_reason"}}
    metadata["years"] = ",".join(map(str, block.get("years", [])))
    metadata["bbox"] = json.dumps(block.get("bbox", []))
    metadata["parent_id"] = block["id"]
    documents = []
    for i, text in enumerate(pieces):
        content = heading + "\n" + text
        if len(tokenizer.encode("passage: " + content)) > 512:
            raise ValueError("Chunk exceeds embedding input limit")
        documents.append(Document(page_content=content, metadata={**metadata, "chunk_number": i}))
    return documents


def build_release(state: Path, *, embeddings=None) -> dict:
    """Finish extraction, embedding and sidecar writes before a release can be activated."""
    from langchain_chroma import Chroma
    from assistant.telemetry import chroma_settings
    started = time.monotonic()
    blocks = read_json(state / "blocks.json", [])
    accepted = {b["id"]: b for b in blocks if b["verification_status"] in {"extracted", "approved"} and b["text"].strip()}
    if not accepted:
        raise ValueError("No verified readable evidence; previous index preserved")
    source_map = {s["id"]: s for s in read_json(state / "sources.json", {"sources": []})["sources"]}
    accepted = {key:block for key,block in accepted.items()
                if source_map.get(block["source_id"],{}).get("source_status") != "retired"}
    for block in accepted.values():
        if block["source_id"] not in source_map or source_map[block["source_id"]].get("sha256") != block["source_sha256"]:
            raise ValueError("Source inventory changed after extraction; run extract before building")
        for key in ('source_owner','review_by','source_status','superseded_by'):
            if key in source_map[block['source_id']]:
                block[key] = source_map[block['source_id']][key]
    model_path = (state / "models/multilingual-e5-small").resolve()
    embeddings = embeddings or LocalE5(str(model_path), str(state / "embedding_cache"), settings.KB_EMBEDDING_REVISION)
    release_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = state / "releases" / release_id
    root.mkdir(parents=True)
    manifest = {"release": release_id, "status": "building", "created_at": now(), "pipeline_version": PIPELINE_VERSION,
                "model": settings.KB_EMBEDDING_MODEL, "revision": settings.KB_EMBEDDING_REVISION,
                "model_path": str(model_path), "model_artifact":"models/multilingual-e5-small",
                "manifest_version":2, "collection": "iiitnr_verified_v2", "metric": "cosine",
                "chunk_tokens": settings.KB_CHUNK_TOKENS, "overlap_tokens": settings.KB_OVERLAP_TOKENS}
    write_json(root / "release.json", manifest)
    try:
        retired = {s.get("sha256") for s in source_map.values() if s.get("source_status") == "retired"}
        retired_blocks = {b['id'] for b in blocks if b.get('source_sha256') in retired}
        records = create_database(root / "facts.sqlite", [r for r in read_json(state / "records.json", [])
                                                          if r.get("source_sha256") not in retired
                                                          and r.get('evidence_block_id') not in retired_blocks], accepted)
        for record in records:
            original = accepted[record["evidence_block_id"]]
            if record["kind"] == "finance":
                for parent in list(accepted.values()):
                    if parent["source_sha256"] == original["source_sha256"]:
                        parent["related_evidence_block_ids"] = record.get("related_evidence_block_ids", [])
                for parent in finance_parents(record,accepted):
                    accepted[parent["id"]] = parent
                continue
            # Cutoffs are exact-looked-up, never mixed across dimensions by semantic search.
            if record["kind"] != "cutoff":
                accepted["record-" + record["id"]] = {**original, "id": "record-" + record["id"],
                    "kind": record["kind"], "text": record_text(record, original),
                    "evidence_block_id": record["evidence_block_id"],
                    "related_evidence_block_ids": record.get("related_evidence_block_ids", [])}
        docs, excluded = [], []
        for block in accepted.values():
            if block["kind"] == "cutoff":
                continue
            try:
                docs.extend(chunk_block(block, embeddings.tokenizer))
            except ValueError as error:
                excluded.append({"block_id": block["id"], "reason": str(error)})
        if not docs:
            raise ValueError("All evidence failed chunk validation")
        unique = {}
        for doc in docs:
            key = digest(json.dumps(doc.metadata, sort_keys=True) + doc.page_content)
            unique[key] = doc
        store = Chroma(collection_name=manifest["collection"], persist_directory=str(root / "chroma"),
                       embedding_function=embeddings, client_settings=chroma_settings(),
                       collection_metadata={"hnsw:space": "cosine", "embedding_model": settings.KB_EMBEDDING_MODEL,
                                            "embedding_revision": settings.KB_EMBEDDING_REVISION})
        items = list(unique.items())
        for start in range(0, len(items), settings.KB_BATCH_SIZE):
            batch = items[start:start + settings.KB_BATCH_SIZE]
            store.add_documents([doc for _, doc in batch], ids=[key for key, _ in batch])
            print(f"indexed {min(start + len(batch), len(items))}/{len(items)}", flush=True)
        write_json(root / "parents.json", accepted)
        write_json(root / "sources.json", read_json(state / "sources.json", {}))
        policies = read_json(state / "policies.json", {"version":1,"rules":[]})
        policies['rules'] = [r for r in policies.get('rules',[]) if not any(s['source_sha256'] in retired for s in r.get('evidence',[]))]
        from assistant.kb.policies import validate as validate_policies
        validate_policies(policies,accepted)
        write_json(root / "policies.json", policies)
        write_json(root / "extraction_report.json", read_json(state / "extraction_report.json", {}))
        write_json(root / "excluded_chunks.json", excluded)
        manifest.update(status="complete", chunks=len(items), evidence_blocks=len(accepted), structured_records=len(records),
                        cutoff_records=sum(r["kind"] == "cutoff" for r in records), excluded_blocks=len(excluded),
                        seconds=round(time.monotonic() - started, 2))
        # Flush the ingestion queue/index before hashing persisted vector artifacts.
        # Chroma 0.5 persists a partial final batch on reopen. Materialize it now,
        # then close native handles so the manifest describes stable on-disk bytes.
        from chromadb.segment import SegmentManager, VectorReader
        segment = store._client._system.instance(SegmentManager).get_segment(store._collection.id, VectorReader)
        segment._apply_batch(segment._curr_batch)
        segment._persist()
        store._client._system.stop()
        manifest["content_sha256"] = content_hashes(root)
        manifest["model_sha256"] = {str(p.relative_to(model_path)):file_hash(p) for p in sorted(model_path.rglob("*"))
                                    if p.is_file() and not any(part.startswith(".") for part in p.relative_to(model_path).parts)} if model_path.exists() else {}
        write_json(root / "release.json", manifest)
        write_json(state / "latest_build.json", {"release": release_id})
        return manifest
    except Exception as error:
        write_json(root / "release.json", {**manifest, "status": "failed", "error": type(error).__name__})
        raise


def activate(state: Path, release_id: str, *, rollback: bool = False) -> dict:
    """Publish one pointer after explicit evaluation, retaining the previous configuration."""
    root = (state / "releases" / release_id).resolve()
    if root.parent != (state / "releases").resolve():
        raise ValueError("Invalid release identifier")
    manifest = read_json(root / "release.json", {})
    validation = read_json(root / "validation.json", {})
    if manifest.get("status") != "complete" or not (root / "facts.sqlite").exists():
        raise ValueError("Cannot activate incomplete release")
    if not validation.get("passed"):
        raise ValueError("Release has not passed evidence evaluation")
    if manifest.get("manifest_version",1) >= 2:
        verify(root,manifest,validation)
    previous = read_json(state / "active.json")
    if previous:
        write_json(state / "previous.json", previous)
    else:
        write_json(state / "previous.json", {"legacy": True, "persist_dir": str(Path(settings.CHROMA_PERSIST_DIR).resolve()),
                                             "collection": settings.CHROMA_COLLECTION_NAME, "model": settings.EMBEDDING_MODEL})
    pointer = {"release": release_id, "activated_at": now(),
               "manifest_sha256":file_hash(root/"release.json"),"validation_sha256":file_hash(root/"validation.json")}
    write_json(state / "active.json", pointer)
    return pointer


def rollback(state: Path) -> dict:
    """Restore the previous complete release or the untouched original index."""
    previous = read_json(state / "previous.json")
    if not previous:
        raise ValueError("No previous release recorded")
    if previous.get("legacy"):
        if not Path(previous["persist_dir"], "chroma.sqlite3").exists():
            raise ValueError("Legacy index is missing")
        os.replace(state / "active.json", state / "rolled_back.json")
        return previous
    return activate(state, previous["release"], rollback=True)
