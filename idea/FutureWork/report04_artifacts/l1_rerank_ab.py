#!/usr/bin/env python3
"""L1 — spot-check A/B of the kbb reranker on the served release (read-only).

Runs the 156-case eval/spotcheck.json through ReleaseSearch with rerank off, then with the
shipped Reranker at rerank_top in {10, 20, 30} under the 1.5 s budget, plus top 20 with a 60 s
budget (quality ceiling without timeouts). Reports pass@1/@3/@k, MRR, per-language results,
per-case regressions vs off, end-to-end search latency, and rerank status and latency.
Never calls release.evaluate (which writes validation.json) and never activates anything.
--check validates paths and imports only.
"""
import argparse, json, os, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KBB = HERE.parent.parent.parent / "code" / "knowledgebaseenhanced"
CONFIGS = [("off", None, None), ("top10", 10, 1.5), ("top20", 20, 1.5), ("top30", 30, 1.5), ("top20_nobudget", 20, 60.0)]


def pct(values, q):
    values = sorted(values)
    return round(values[int(q * (len(values) - 1))], 1) if values else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    active = KBB / "data/kbb/serving/active.json"
    if args.check:
        info = {"check": True, "kbb_root": str(KBB), "active_exists": active.is_file(),
                "cases_exist": (KBB / "eval/spotcheck.json").is_file()}
        try:
            sys.path.insert(0, str(KBB)); sys.path.insert(0, str(KBB / "scripts"))
            import spotcheck, kbb.rerank  # noqa: F401
            info["imports_ok"] = hasattr(spotcheck, "reciprocal_rank")
        except Exception as e:
            info["imports_ok"] = f"{type(e).__name__}: {e}"
        json.dump(info, open(args.out, "w"), indent=2); print(json.dumps(info)); return

    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HUB_OFFLINE"] = "1"
    sys.path.insert(0, str(KBB)); sys.path.insert(0, str(KBB / "scripts"))
    import spotcheck as sc
    from kbb.release import ReleaseSearch
    from kbb.rerank import Reranker
    release = json.load(open(active))["release"]
    engine = ReleaseSearch(KBB / "data/kbb/serving/releases" / release)
    cases = json.load(open(KBB / "eval/spotcheck.json"))

    # One model load shared by every configuration.
    shared = Reranker(engine.cfg.retrieval.reranker, device="cpu")
    if not shared.warm():
        json.dump({"error": "reranker unavailable; run L0 first", "reason": shared._load_error}, open(args.out, "w"), indent=2)
        sys.exit(1)
    score_fn = shared._score
    engine.search("warmup question about fees", 6)

    results, report = {}, {"release": release, "configs": {}}
    for name, top, budget in CONFIGS:
        if top is None:
            engine.reranker = None
        else:
            engine.reranker = Reranker(engine.cfg.retrieval.reranker, budget_s=budget,
                                       max_chars=engine.cfg.retrieval.rerank_max_chars, loader=lambda: score_fn)
            engine.cfg.retrieval.rerank_top = top
            engine.reranker.rerank("warmup", [("a", "fee"), ("b", "hostel")])
        latencies, statuses, rerank_ms = [], {}, []

        def search(q, k):
            t = time.monotonic()
            hits = engine.search(q, k)
            latencies.append((time.monotonic() - t) * 1000)
            if engine.reranker is not None:
                last = engine.reranker.last
                statuses[last["status"]] = statuses.get(last["status"], 0) + 1
                if last["status"] == "ok":
                    rerank_ms.append(last["ms"])
                engine.reranker.last = {"status": "not_called"}   # exact/policy paths skip reranking
            return hits

        rows = sc.run_engine(cases, search)
        results[name] = rows
        s = sc.summarize(rows)
        report["configs"][name] = {"rerank_top": top, "budget_s": budget, "passed": s["passed"], "scored": s["scored"],
                                   "ordering": s["ordering"], "by_language": s["by_language"],
                                   "search_ms_p50": pct(latencies, .5), "search_ms_p95": pct(latencies, .95),
                                   "rerank_ms_p50": pct(rerank_ms, .5), "rerank_ms_p95": pct(rerank_ms, .95),
                                   "rerank_status": statuses}
        # Let any abandoned job finish so the next configuration starts clean.
        if engine.reranker is not None and engine.reranker._inflight is not None:
            try:
                engine.reranker._inflight.result(timeout=120)
            except Exception:
                pass
        print(name, json.dumps(report["configs"][name]["ordering"]), flush=True)

    base = {r["id"]: r for r in results["off"]}
    for name in results:
        if name == "off":
            continue
        regress = [r["id"] for r in results[name] if base[r["id"]]["status"] == "pass" and r["status"] != "pass"]
        gained = [r["id"] for r in results[name] if base[r["id"]]["status"] != "pass" and r["status"] == "pass"]
        report["configs"][name]["regressions"] = regress
        report["configs"][name]["newly_passing"] = gained

    off = report["configs"]["off"]
    def ok(name):
        c = report["configs"][name]
        calls = sum(c["rerank_status"].values()) - c["rerank_status"].get("not_called", 0)
        slow = c["rerank_status"].get("timeout", 0) + c["rerank_status"].get("busy", 0)
        hindi, hindi_off = c["by_language"].get("hindi", {}).get("mrr"), off["by_language"].get("hindi", {}).get("mrr")
        return (not c["regressions"] and c["ordering"]["mrr"] > off["ordering"]["mrr"]
                and (hindi is None or hindi_off is None or hindi >= hindi_off)
                and (c["rerank_ms_p95"] or 0) <= 1500 and slow <= 0.05 * max(1, calls))
    passing = [n for n in ("top10", "top20", "top30") if ok(n)]
    report["recommended"] = max(passing, key=lambda n: report["configs"][n]["ordering"]["mrr"]) if passing else None
    report["passed"] = bool(passing)
    json.dump(report, open(args.out, "w"), indent=2, ensure_ascii=False)
    json.dump(results, open(out_dir / "rows.json", "w"), indent=1, ensure_ascii=False)
    (out_dir / "report.md").write_text(sc.compare(results), encoding="utf-8")
    print(json.dumps({"recommended": report["recommended"], "passed": report["passed"]}))


if __name__ == "__main__":
    main()
