"""Recompute doc 01 §4.1 statistics from code/demo2/data/upgrade-20260930/{baseline,candidate}/results.json (numpy, linear interpolation)."""
import json, sys
from collections import Counter
from pathlib import Path
import numpy as np

root = Path(sys.argv[1] if len(sys.argv) > 1 else "code/demo2/data/upgrade-20260930")
p = lambda a, q: float(np.percentile(np.array(a, float), q))
out = {}
for run in ("baseline", "candidate"):
    d = json.load(open(root / run / "results.json"))
    ans = [r for r in d if r["response_status"] == "answered"]
    st = lambda k: [r["rag_metrics"]["stage_ms"][k] for r in d if k in r["rag_metrics"].get("stage_ms", {})]
    three = [r for r in d if r["rag_metrics"].get("model_calls") == 3]
    out[run] = {
        "turn_s": [p([r["seconds"] for r in d], q) for q in (50, 95, 100)],
        "answered_s": [p([r["seconds"] for r in ans], q) for q in (50, 95)], "answered_n": len(ans),
        **{k: [p(st(k), 50), p(st(k), 95), len(st(k))] for k in ("routing_model", "retrieval", "generation_model", "review_model")},
        "calls": dict(Counter(r["rag_metrics"].get("model_calls") for r in d)),
        "status": dict(Counter(r["response_status"] for r in d)),
        "critical_policy_turns": sum(bool(r["rag_metrics"].get("critical_policy")) for r in d),
        "review_share_on_3call_median": float(np.median([r["rag_metrics"]["stage_ms"]["review_model"] / 1000 / r["seconds"] for r in three])),
    }
    w = json.load(open(root / run / "results-warmup.json"))
    out[run]["warmup"] = {"seconds": w["seconds"], "routing_ms": w["metrics"]["stage_ms"]["routing_model"], "retrieval_ms": w["metrics"]["stage_ms"]["retrieval"]}
print(json.dumps(out, indent=1))
