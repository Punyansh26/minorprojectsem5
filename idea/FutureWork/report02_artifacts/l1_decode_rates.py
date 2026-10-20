#!/usr/bin/env python3
"""L1 — measure real prefill/decode rates on T0, warm vs cold, across offload settings.

Sends short fixed prompts to Ollama's /api/chat with stream:false and reads the
numeric fields (prompt_eval_count/eval_count and their nanosecond durations). It
does not change any project configuration; it talks to Ollama directly. Use
`--check` for a fast, no-generation validation of arguments and reachability.
"""
import argparse, json, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
PROMPT = "List three primary colours. Answer in one short sentence."

def _post(path, body, timeout):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def one_call(num_ctx, num_predict, keep_alive):
    body = {"model": MODEL, "stream": False, "keep_alive": keep_alive,
            "messages": [{"role": "user", "content": PROMPT}],
            "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict}}
    t0 = time.monotonic()
    out = _post("/api/chat", body, timeout=300)
    wall = time.monotonic() - t0
    pc, pd = out.get("prompt_eval_count"), out.get("prompt_eval_duration")
    ec, ed = out.get("eval_count"), out.get("eval_duration")
    ld = out.get("load_duration", 0) or 0
    return {"num_ctx": num_ctx, "num_predict": num_predict, "wall_s": round(wall, 3),
            "prompt_tokens": pc, "output_tokens": ec,
            "prefill_tok_s": round(pc / (pd / 1e9), 2) if pc and pd else None,
            "decode_tok_s": round(ec / (ed / 1e9), 2) if ec and ed else None,
            "load_s": round(ld / 1e9, 3), "cold": (ld / 1e9) > 0.5}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        try:
            _post("/api/show", {"model": MODEL}, timeout=10)
            reachable = True
        except (urllib.error.URLError, OSError):
            reachable = False
        json.dump({"check": True, "ollama_reachable": reachable, "model": MODEL},
                  open(args.out, "w"), indent=2)
        print(json.dumps({"check": True, "ollama_reachable": reachable}))
        return
    rows = []
    # Cold first (unload, then one call), then warm repeats at two contexts.
    _post("/api/chat", {"model": MODEL, "keep_alive": 0,
                        "messages": [{"role": "user", "content": "hi"}],
                        "options": {"num_predict": 1}}, timeout=120)
    time.sleep(3)
    rows.append({"phase": "cold", **one_call(8192, 64, "5m")})
    for _ in range(5):
        rows.append({"phase": "warm", **one_call(8192, 64, "5m")})
    for _ in range(5):
        rows.append({"phase": "warm", **one_call(4096, 64, "5m")})
    decode = [r["decode_tok_s"] for r in rows if r["phase"] == "warm" and r["decode_tok_s"]]
    summary = {"model": MODEL, "rows": rows,
               "warm_decode_tok_s_mean": round(sum(decode) / len(decode), 2) if decode else None,
               "note": "Record `ollama ps` CPU/GPU split alongside this run; "
                       "repeat after freeing desktop VRAM to get the on-GPU rate."}
    _post("/api/chat", {"model": MODEL, "keep_alive": 0,
                        "messages": [{"role": "user", "content": "bye"}],
                        "options": {"num_predict": 1}}, timeout=120)
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"warm_decode_tok_s_mean": summary["warm_decode_tok_s_mean"]}))

if __name__ == "__main__":
    main()
