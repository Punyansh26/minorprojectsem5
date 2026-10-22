#!/usr/bin/env python3
"""diag_llm_error.py — surface the hidden LocalModelError from the grounded agent.

04_demo2_latency.py only reads response_status/sources, so when a turn fails it
prints "routing failed (LocalModelError)" with no detail. The real, actionable
message is carried on the result dict as `llm_error` (see assistant/nodes.py::
_failure, which logs only the error *type* for safety but preserves the message
string for LocalModelError). This script calls agent_bridge.ask exactly as the
app does and prints that message, plus the resolved provider/model/endpoint so
we can see whether .env.colab actually reached the agent's settings.

Prereqs (run first, in this order):
    bash colab_scripts/01_bootstrap.sh qwen3.5:9b
    bash colab_scripts/02_serve_config.sh qwen3.5:9b
    # tokenizer for prompt-token budgeting:
    (cd /content/minor/code/Institute-voice-agent/institute-assistant && \
         set -a && source /content/colab_out/.env.colab && set +a && python setup_local.py)
    set -a && source /content/colab_out/.env.colab && set +a

Usage:
    python colab_scripts/diag_llm_error.py
    python colab_scripts/diag_llm_error.py --question "फीस कितनी है?" --provider ollama
"""
import argparse
import os
import sys
import traceback
from pathlib import Path
from uuid import uuid4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", default="What documents are required for admission?")
    ap.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    ap.add_argument("--demo2-dir", default=os.getenv("DEMO2_DIR", "/content/minor/code/demo2"))
    args = ap.parse_args()

    demo2 = Path(args.demo2_dir).resolve()
    if not (demo2 / "agent_bridge.py").is_file():
        sys.exit(f"demo2 not found at {demo2}. Set DEMO2_DIR or run 01_bootstrap.sh.")
    os.chdir(demo2)
    sys.path.insert(0, str(demo2))

    # Run demo2's configure_agent() FIRST, exactly as agent_bridge.get_graph() does:
    # it sets KB_BACKEND/KB_STATE_DIR (kbb release), KB_DIR, cache paths, etc. before
    # assistant.config's frozen Settings is instantiated. Importing assistant.config
    # earlier freezes the wrong defaults and makes this probe diverge from the app.
    from settings import configure_agent  # demo2/settings.py
    configure_agent()
    import agent_bridge  # noqa: E402,F401

    # Show what the agent's settings actually resolved to (did .env.colab land?).
    try:
        agent_root = os.getenv("DEMO2_CODE_ROOT", "/content/minor/code")
        ia = str(Path(agent_root) / "Institute-voice-agent" / "institute-assistant")
        if ia not in sys.path:
            sys.path.insert(0, ia)
        from assistant.config import settings  # type: ignore
        from assistant.llm import model_identity  # type: ignore
        ident = model_identity(settings, provider=args.provider)
        print("--- resolved agent config ---")
        for key in ("provider", "model", "endpoint", "context", "tokenizer"):
            print(f"  {key:9}: {ident.get(key)}")
        tok = ident.get("tokenizer")
        if tok:
            print(f"  tokenizer_exists: {Path(str(tok)).expanduser().is_file()}")
        print()
    except Exception as e:  # noqa: BLE001
        print(f"(could not import settings directly: {type(e).__name__}: {e})\n")

    import agent_bridge  # noqa: E402

    profile = {"student_id": "guest", "student_email": "", "student_category": "general"}
    print(f"--- ask (provider={args.provider}) ---")
    print(f"  question : {args.question}")
    try:
        r = agent_bridge.ask(args.question, str(uuid4()), profile, provider=args.provider)
    except Exception:  # noqa: BLE001
        print("  ask() raised:")
        traceback.print_exc()
        sys.exit(1)

    print(f"  status   : {r.get('response_status')}")
    print(f"  sources  : {len(r.get('sources') or [])}")
    print(f"  answer   : {(r.get('answer_text') or '')[:200]!r}")
    print(f"  llm_error: {r.get('llm_error')!r}")
    print(f"  rag_metrics: {r.get('rag_metrics')}")

    # --- RETRIEVAL PROBE: retrieve_node logs only the exception TYPE; print the traceback.
    print("\n--- retrieval probe ---")
    try:
        from assistant.config import settings as s  # type: ignore
        from assistant.kb.common import active_release  # type: ignore
        print(f"  KB_BACKEND   : {os.getenv('KB_BACKEND')}  KB_STATE_DIR: {s.KB_STATE_DIR}")
        release = active_release(Path(s.KB_STATE_DIR))
        print(f"  active release: {release[0] if release else None}")
        from assistant.retrieval import retrieve  # type: ignore
        hits = retrieve(args.question, release=release)
        print(f"  retrieve() OK: {len(hits)} chunks")
        for h in hits[:3]:
            print(f"    - {h.source_file} p{h.page_number}: {h.text[:90]!r}")
    except Exception:  # noqa: BLE001
        print("  retrieve() raised:")
        traceback.print_exc()

    # --- RAW PROBE: reconstruct the exact /api/chat body and print the 400 body ---
    # LocalModelError deliberately hides provider response bodies, so we bypass it
    # here and hit Ollama directly to see WHY /api/chat returns 400 while the
    # /api/generate benchmark returns 200. We toggle `think` and schema `format`
    # independently to isolate which field the installed Ollama build rejects.
    if args.provider == "ollama":
        try:
            import json
            import httpx
            from assistant import llm  # type: ignore
            from assistant.config import settings  # type: ignore

            base = settings.OLLAMA_BASE_URL.rstrip("/")
            schema = llm.RoutingDecision
            instruction = "Route"
            payload = {"message": args.question}
            messages = llm._messages(schema, instruction, payload)
            schema_format = llm.generation_schema(schema, payload)
            common = {"model": settings.OLLAMA_MODEL, "messages": messages,
                      "stream": False, "keep_alive": llm._keep_alive_value(),
                      "options": {"temperature": 0, "num_ctx": settings.OLLAMA_NUM_CTX,
                                  "repeat_penalty": 1.0, "presence_penalty": 0,
                                  "num_predict": settings.OLLAMA_NUM_PREDICT}}

            # /api/show capabilities (what the agent probes to gate `think`).
            with httpx.Client(base_url=base + "/", timeout=60, trust_env=False) as c:
                show = c.post("api/show", json={"model": settings.OLLAMA_MODEL})
                caps = show.json().get("capabilities") if show.status_code == 200 else None
                print(f"\n--- raw probe ---\n  /api/show capabilities: {caps}")

                variants = [
                    ("format=schema, think=false", {**common, "format": schema_format, "think": False}),
                    ("format=schema, no think",     {**common, "format": schema_format}),
                    ("format=json,   no think",     {**common, "format": "json"}),
                    ("no format,     no think",     {**common}),
                    ("format=schema, think=false (generate)", None),
                ]
                for label, body in variants:
                    if body is None:
                        # Mirror the working benchmark path: /api/generate.
                        gbody = {"model": settings.OLLAMA_MODEL,
                                 "prompt": messages[-1]["content"],
                                 "system": messages[0]["content"],
                                 "format": schema_format, "stream": False,
                                 "options": common["options"]}
                        resp = c.post("api/generate", json=gbody)
                    else:
                        resp = c.post("api/chat", json=body)
                    detail = ""
                    if resp.status_code != 200:
                        try:
                            detail = json.dumps(resp.json())
                        except Exception:  # noqa: BLE001
                            detail = resp.text[:500]
                    print(f"  [{resp.status_code}] {label}  {detail}")
        except Exception as e:  # noqa: BLE001
            print(f"  (raw probe failed: {type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
