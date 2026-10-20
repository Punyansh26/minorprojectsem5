"""L0 — §b tool-retrieval accuracy vs schema-token cost (local, no model).

For each labelled transcript, compare the rule-narrowed tool set from
select_tools() against the full exposed set. "Accuracy" = the rule set still
contains the tool the gold intent needs (or, for safety/negation/ambiguous
turns, still contains the safety/clarify tools). Also report the mean fraction
of tool-schema characters kept. Pass: accuracy >= 1.0 AND mean ratio <= 0.5.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(DEMO))
OUT = HERE / "out" / "L0"
OUT.mkdir(parents=True, exist_ok=True)

from assistant import select_tools              # noqa: E402
from mcp_client import connect                  # noqa: E402

INTENT_TOOL = {
    "add": "add_to_cart", "view_cart": "view_cart", "price": "check_price",
    "area": "calculate_required_quantity", "checkout": "checkout",
}
SAFETY_SET = {"refuse_and_refer", "request_clarification"}


async def main():
    transcripts = json.loads((HERE / "transcripts.json").read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="l0-"))
    async with connect("l0", "1", tmp / "s.json") as (session, discovered, schemas, _):
        allowed = {t.name for t in discovered} - {"confirm_checkout"}

        def chars(names):
            payload = [{"type": "function", "function": {"name": t.name,
                        "description": t.description, "parameters": schemas[t.name]}}
                       for t in discovered if t.name in names]
            return len(json.dumps(payload, ensure_ascii=False))

        full_chars = chars(allowed)
        hits, ratios, rows = 0, [], []
        for item in transcripts:
            sel = select_tools(item["text"], allowed)
            need = INTENT_TOOL.get(item["intent"])
            ok = (need in sel) if need else bool(SAFETY_SET & sel)
            hits += ok
            ratio = chars(sel) / full_chars
            ratios.append(ratio)
            rows.append({"text": item["text"], "intent": item["intent"],
                         "exposed": sorted(sel), "ok": ok, "schema_ratio": round(ratio, 3)})
    accuracy = hits / len(transcripts)
    mean_ratio = sum(ratios) / len(ratios)
    summary = {"test": "L0", "n": len(transcripts), "accuracy": round(accuracy, 3),
               "mean_schema_chars_ratio": round(mean_ratio, 3), "full_schema_chars": full_chars,
               "pass": bool(accuracy >= 1.0 and mean_ratio <= 0.5), "rows": rows}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: summary[k] for k in ("accuracy", "mean_schema_chars_ratio", "pass")}))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
