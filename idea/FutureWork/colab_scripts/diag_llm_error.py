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


if __name__ == "__main__":
    main()
