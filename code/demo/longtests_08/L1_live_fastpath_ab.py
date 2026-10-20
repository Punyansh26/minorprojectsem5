"""L1 — live-Groq A/B: deterministic fast paths vs always-LLM (needs a key).

Runs each transcript twice through a REAL Groq model: once with the shipped
assistant (fast paths on) and once with the fast paths disabled (forced LLM).
Reports the used_llm share, median total_ms for each arm, and whether the final
cart state matches between arms (parity). Needs GROQ_API_KEY and network.
"""
import asyncio
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent
sys.path.insert(0, str(DEMO))
OUT = HERE / "out" / "L1"
OUT.mkdir(parents=True, exist_ok=True)

import assistant                                 # noqa: E402
from assistant import run_async                  # noqa: E402

KEY = os.getenv("GROQ_API_KEY", "")


async def run_arm(transcripts, force_llm):
    # Disable the deterministic add fast path for the "forced LLM" arm by
    # monkeypatching add_intent to always return None. §b/§h stay on (they do
    # not change the final cart state).
    original = assistant.add_intent
    if force_llm:
        assistant.add_intent = lambda text: None
    try:
        tmp = Path(tempfile.mkdtemp(prefix="l1-"))
        times, llm_turns, carts = [], 0, []
        for i, item in enumerate(transcripts):
            out = await run_async(item["text"], "hi", KEY, f"l1-{force_llm}-{i}", "1",
                                  state_path=tmp / f"{i}.json")
            times.append(out["timings"]["total_ms"])
            llm_turns += int(out.get("used_llm", True))
            carts.append(out["cart"]["item_count"])
        return {"median_total_ms": round(statistics.median(times), 1),
                "used_llm_share": round(llm_turns / len(transcripts), 3), "carts": carts}
    finally:
        assistant.add_intent = original


async def main():
    if not KEY:
        (OUT / "summary.json").write_text(json.dumps({"test": "L1", "status": "skipped",
            "reason": "GROQ_API_KEY not set"}, indent=2))
        print("L1 skipped: no GROQ_API_KEY")
        return 0
    transcripts = json.loads((HERE / "transcripts.json").read_text(encoding="utf-8"))
    fast = await run_arm(transcripts, force_llm=False)
    slow = await run_arm(transcripts, force_llm=True)
    parity = fast["carts"] == slow["carts"]
    summary = {"test": "L1", "n": len(transcripts), "fast_paths": fast, "forced_llm": slow,
               "cart_parity": parity,
               "latency_delta_ms": round(slow["median_total_ms"] - fast["median_total_ms"], 1),
               "pass": bool(parity and fast["used_llm_share"] < slow["used_llm_share"])}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: summary[k] for k in ("cart_parity", "latency_delta_ms", "pass")}))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
