"""Keep financial fields on their original pages without changing JEV-bound rank helpers."""
import json

POLICY_VERSION = "scope-provenance-3"
PUBLIC_FIELDS = ("source_sha256", "audience", "conflict_note", "scope_note", "source_owner",
                 "review_by", "source_status", "superseded_by")


def financial_spans(record, blocks):
    """Require each curated financial field to occur on an explicitly identified page."""
    linked = [blocks[key] for key in [record["evidence_block_id"],*record.get("related_evidence_block_ids",[])]]
    spans = {}
    for field in ("benefit","conditions"):
        value = record.get(field)
        if not value:
            continue
        matches = [b for b in linked if " ".join(value.split()) in " ".join(b["text"].split())]
        if not matches:
            raise ValueError("Financial field lacks a single-page source span: "+field)
        block = matches[0]
        spans[field] = {"block_id":block["id"],"page_number":block["page_number"],
                       "source_sha256":block["source_sha256"],"quote":value}
    return spans


def finance_parents(record, blocks):
    """Index each cited page independently; related conditions still accompany benefits."""
    spans = financial_spans(record,blocks)
    keys = [record["evidence_block_id"],*record.get("related_evidence_block_ids",[])]
    for index,key in enumerate(dict.fromkeys(keys)):
        original = blocks[key]
        yield {**original,"id":f"record-{record['id']}-{index}","kind":record["kind"],
               "text":original["text"],"evidence_block_id":key,
               "field_evidence":json.dumps(spans,ensure_ascii=False,sort_keys=True),
               "related_evidence_block_ids":[k for k in keys if k != key],
               "scope_note":"General scheme rules; IIIT-NR applicability: "+record["institution_applicability"]}
