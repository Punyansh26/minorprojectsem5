#!/usr/bin/env python3
"""L0 — measure energy and cost per turn on T0 by sampling GPU and CPU power.

Samples `nvidia-smi --query-gpu=power.draw` and Intel RAPL energy counters while
driving a fixed set of generation calls through Ollama, then reports mean watts
and joules per turn. Pure measurement; changes no project configuration. Use
`--check` for fast validation without generation.

Cost: pass --price-per-kwh to convert; default leaves cost null (states its date
assumption as [Reported] when you fill it in).
"""
import argparse, glob, json, subprocess, threading, time, urllib.request

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
QUESTIONS = [
    "What is admission to B.Tech decided on?",
    "What documents are required for reporting?",
    "What is the fee structure?",
]

def gpu_power_w():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True, timeout=5)
        return float(out.strip().splitlines()[0])
    except Exception:
        return None

def rapl_microjoules():
    total = 0
    for path in glob.glob("/sys/class/powercap/intel-rapl:*/energy_uj"):
        try:
            total += int(open(path).read().strip())
        except (OSError, ValueError):
            pass
    return total or None

def _post(body, timeout=300):
    req = urllib.request.Request(BASE + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turns", type=int, default=21)
    ap.add_argument("--price-per-kwh", type=float, default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        info = {"check": True, "gpu_power_w": gpu_power_w(),
                "rapl_readable": rapl_microjoules() is not None}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    samples = []
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            samples.append((time.monotonic(), gpu_power_w()))
            time.sleep(0.2)
    th = threading.Thread(target=sampler, daemon=True); th.start()

    rapl0 = rapl_microjoules(); t0 = time.monotonic()
    answered = 0
    for i in range(args.turns):
        q = QUESTIONS[i % len(QUESTIONS)]
        out = _post({"model": MODEL, "stream": False, "keep_alive": "5m",
                     "messages": [{"role": "user", "content": q}],
                     "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 256}})
        if out.get("done"):
            answered += 1
    wall = time.monotonic() - t0
    stop.set(); th.join(timeout=2)
    rapl1 = rapl_microjoules()

    gpu_vals = [p for _, p in samples if p is not None]
    gpu_mean_w = sum(gpu_vals) / len(gpu_vals) if gpu_vals else None
    gpu_j = gpu_mean_w * wall if gpu_mean_w else None
    cpu_j = (rapl1 - rapl0) / 1e6 if (rapl0 and rapl1 and rapl1 >= rapl0) else None
    total_j = (gpu_j or 0) + (cpu_j or 0)
    per_turn_j = total_j / answered if answered else None
    cost = None
    if args.price_per_kwh and per_turn_j:
        cost = (per_turn_j / 3.6e6) * args.price_per_kwh
    summary = {"model": MODEL, "turns_requested": args.turns, "turns_answered": answered,
               "wall_s": round(wall, 2), "gpu_mean_w": round(gpu_mean_w, 2) if gpu_mean_w else None,
               "gpu_joules": round(gpu_j, 1) if gpu_j else None,
               "cpu_joules_rapl": round(cpu_j, 1) if cpu_j else None,
               "joules_per_turn": round(per_turn_j, 1) if per_turn_j else None,
               "cost_per_turn": cost, "price_per_kwh": args.price_per_kwh,
               "note": "idle GPU was 16.8 W [Measured-here, 01]. If a term is null, that "
                       "sensor was unreadable; state it. Cost is [Reported] with your tariff date."}
    _post({"model": MODEL, "keep_alive": 0,
           "messages": [{"role": "user", "content": "bye"}],
           "options": {"num_predict": 1}}, timeout=120)
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"joules_per_turn": summary["joules_per_turn"],
                      "gpu_mean_w": summary["gpu_mean_w"]}))

if __name__ == "__main__":
    main()
