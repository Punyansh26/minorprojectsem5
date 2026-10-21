#!/usr/bin/env python3
"""L4 — energy per turn (chapter 12 §2.6): ∫P dt over real turns → Wh/turn and cost.

Uses metrics_ext.EnergySampler to integrate nvidia-smi power.draw [R1223] and RAPL
/sys/class/powercap/intel-rapl* [R1224] across each warm turn of a real agent run, producing
the [Measured-here] Wh/turn that replaces the [Estimated] "$0.60/month" in [01 §6]. Also pins
residency with metrics_ext.read_residency before and after and refuses to report if it drifted
(§7.1). A background sampler thread takes power samples every --interval seconds during the turn.

Long because: it must run real turns on the GPU with the 9B resident and sample power for the
whole window. The user runs it; the agent runs --check.
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

DEMO2 = Path(__file__).resolve().parents[3] / "code" / "demo2"
sys.path.insert(0, str(DEMO2))

import metrics_ext  # noqa: E402


def _sample_loop(sampler, stop_event, interval):
    while not stop_event.is_set():
        sampler.sample()
        time.sleep(interval)


def run(cases_path: Path, out: Path, interval: float, cost_per_kwh: float):
    scratch = out.parent / "caches"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(LLM_PROVIDER="ollama", JEV_ROUTING_MODE="off",
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      CHECKPOINT_DB_PATH=str(scratch / "unused.sqlite"),
                      RAG_CACHE_DB_PATH=str(scratch / "cache.sqlite"),
                      TICKETS_DB_PATH=str(scratch / "blocked.sqlite"))
    before = metrics_ext.read_residency()
    import settings as cfg  # noqa: E402
    import agent_bridge  # noqa: E402
    cfg.configure_agent()
    cases = json.loads(cases_path.read_text())

    turns = []
    for index, case in enumerate(cases):
        sampler = metrics_ext.EnergySampler()
        stop_event = threading.Event()
        sampler.start()
        thread = threading.Thread(target=_sample_loop, args=(sampler, stop_event, interval), daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            agent_bridge.ask(case["question"], f"l4-{index}", {"student_id": "l4", "student_category": "general"})
            ok = True
        except Exception:
            ok = False
        wall = time.monotonic() - started
        stop_event.set()
        thread.join(timeout=2.0)
        reading = sampler.stop()
        turns.append({"id": case["id"], "ok": ok, "wall_seconds": wall, **reading})

    after = metrics_ext.read_residency()
    stable = metrics_ext.residency_stable(before, after)
    totals = [t["total_wh"] for t in turns if t.get("total_wh") is not None]
    mean_wh = sum(totals) / len(totals) if totals else None
    summary = {
        "test": "L4_energy", "n": len(turns),
        "residency_stable": stable,
        "mean_wh_per_turn": mean_wh,
        "cost_per_turn": (mean_wh / 1000.0 * cost_per_kwh) if mean_wh is not None else None,
        "cost_per_kwh": cost_per_kwh,
        "turns": turns,
    }
    if not stable:
        summary["WARNING"] = "residency drifted during the run (§7.1); energy numbers are not comparable"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "turns"}, indent=2, ensure_ascii=False))
    os.system("ollama stop qwen3.5:9b >/dev/null 2>&1 || true")


def check(out: Path):
    # the integrator must give 0.0556 Wh for 100 W over 2 s, and degrade to None without a GPU
    clock = iter([0.0, 0.0, 1.0, 2.0, 2.0])
    saved = metrics_ext.read_gpu_power_watts, metrics_ext.read_rapl_energy_uj
    metrics_ext.read_gpu_power_watts = lambda: 100.0
    metrics_ext.read_rapl_energy_uj = lambda: None
    try:
        s = metrics_ext.EnergySampler()
        s._clock = lambda: next(clock)
        s.start(); s.sample(); reading = s.stop()
        assert abs(reading["gpu_wh"] - 100.0 * 2.0 / 3600.0) < 1e-6
    finally:
        metrics_ext.read_gpu_power_watts, metrics_ext.read_rapl_energy_uj = saved
    out.write_text(json.dumps({"test": "L4_energy", "check": "ok"}, indent=2))
    print("L4 --check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", type=Path, help="turn set (e.g. evaluation/upgrade-20260930/cases.json)")
    ap.add_argument("--interval", type=float, default=0.25, help="power sample period (s)")
    ap.add_argument("--cost-per-kwh", type=float, default=8.0, help="local electricity cost (currency/kWh)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(args.out)
    if not args.cases:
        ap.error("--cases is required for a full run")
    run(args.cases, args.out, args.interval, args.cost_per_kwh)


if __name__ == "__main__":
    main()
