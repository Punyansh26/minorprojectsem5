"""Temporary read-only Ollama probe for FutureWork Task 01. Not part of the repository."""
import json, subprocess, time, urllib.request

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
OPTS = {"temperature": 0, "num_ctx": 8192, "repeat_penalty": 1.0, "presence_penalty": 0}


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    data["_wall_s"] = time.monotonic() - t
    return data


def chat(system, user, num_predict, fmt=None):
    body = {"model": MODEL, "stream": False, "think": False, "keep_alive": "10m",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {**OPTS, "num_predict": num_predict}}
    if fmt:
        body["format"] = fmt
    return post("/api/chat", body)


def summary(label, d):
    pe, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 0) / 1e6
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0) / 1e6
    out = {"label": label, "wall_s": round(d["_wall_s"], 3), "load_ms": round(d.get("load_duration", 0) / 1e6, 1),
           "prompt_tokens_evaluated": pe, "prefill_ms": round(pd, 1),
           "decode_tokens": ec, "decode_ms": round(ed, 1),
           "decode_tok_s": round(ec / (ed / 1000), 2) if ed else None,
           "ms_per_token": round(ed / ec, 1) if ec else None}
    print(json.dumps(out), flush=True)
    return out


def ps():
    d = json.loads(urllib.request.urlopen(BASE + "/api/ps").read())
    for m in d.get("models", []):
        total, vram = m["size"], m["size_vram"]
        print(json.dumps({"ps": m["name"], "size_GB": round(total / 1e9, 2), "vram_GB": round(vram / 1e9, 2),
                          "gpu_pct": round(100 * vram / total, 1), "cpu_pct": round(100 - 100 * vram / total, 1),
                          "context": m.get("context_length")}), flush=True)


def smi():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    print("nvidia-smi memory.used,total:", out, flush=True)


# ~900-token deterministic system prompt (instruction-like prose; no repository data)
para = ("You answer questions about a university using only the numbered sources supplied by the user. "
        "Quote exact spans, never paraphrase numbers, and refuse when evidence is missing. ")
SYSTEM_A = (para * 40).strip()
SYSTEM_B = "ALTERNATE " + SYSTEM_A          # first token changed
USER_1 = "What is the fee? Sources: 1) Tuition 90000."
USER_2 = "When is the deadline? Sources: 1) July 5."

smi()
print("-- cold load", flush=True)
r = {}
r["cold_load"] = summary("cold load (1 token)", chat(SYSTEM_A, USER_1, 1))
ps(); smi()
r["prefill_cold_A"] = summary("prefill A (prefix new to slot after load)", chat(SYSTEM_A, USER_1 + " v2", 1))
r["prefill_repeat_A"] = summary("repeat identical A+user", chat(SYSTEM_A, USER_1 + " v2", 1))
r["prefill_change_user"] = summary("same system, different user msg", chat(SYSTEM_A, USER_2, 1))
r["prefill_change_first"] = summary("first token of system changed", chat(SYSTEM_B, USER_1, 1))
r["prefill_return_A"] = summary("return to A after B", chat(SYSTEM_A, USER_1, 1))
print("-- decode free text", flush=True)
r["decode_10"] = summary("free-text decode, num_predict=10", chat("Be concise.", "Write a long story about a farmer.", 10))
r["decode_64"] = summary("free-text decode, num_predict=64", chat("Be concise.", "Write a long story about a farmer.", 64))
print("-- grammar penalty", flush=True)
import random
random.seed(1)
spans = [f"Span number {i}: " + " ".join(random.choice(["fee", "rank", "hostel", "mess", "seat", "quota", "gate", "bus", "lab", "exam"]) for _ in range(8)) + f" {i * 37}." for i in range(300)]
schema_enum = {"type": "object", "properties": {"answer": {"type": "string"}, "quote": {"type": "string", "enum": spans}},
               "required": ["answer", "quote"], "additionalProperties": False}
schema_free = {"type": "object", "properties": {"answer": {"type": "string"}, "quote": {"type": "string"}},
               "required": ["answer", "quote"], "additionalProperties": False}
prompt_u = "Answer with a one-word answer, then copy the quote for span number 12 exactly. Spans:\n" + "\n".join(spans[:40])
for rep in range(2):
    r[f"schema_free_{rep}"] = summary(f"JSON schema, free quote (rep {rep})", chat("Return JSON.", prompt_u, 120, schema_free))
    r[f"schema_enum_{rep}"] = summary(f"JSON schema, 300-entry enum (rep {rep})", chat("Return JSON.", prompt_u, 120, schema_enum))
ps(); smi()
json.dump(r, open("/tmp/fw01_probe_result.json", "w"), indent=1)
# unload to restore original state
post("/api/generate", {"model": MODEL, "keep_alive": 0})
print("unloaded", flush=True)
