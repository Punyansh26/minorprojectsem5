# Farmer shopping demo

## Scope and environment

The user explicitly requested this separate Streamlit + Groq free-tier MCP demo.
Keep implementation in this directory. The wider local S2S research pipeline remains
in `../STT` and `../TTS`; this demo uses their local speech models with Groq routing and push-to-talk.
The 2026-09-06 user request supersedes the previous API speech/SQLite design.

Use the existing Conda environment **minor** for all development, running, and tests:
`conda activate minor`. On this machine its Python is
`/home/rtx/miniconda3/envs/minor/bin/python`. Do not create another venv or change
the system Python. Install missing demo dependencies into minor; preserve its
existing speech/model stack. A sandbox may require approval to install there.

## Implementation invariants

- Use actual MCP stdio discovery and calls to a separate server, including UI actions.
- Keep session identity and idempotency outside model arguments; validate all schemas.
- Store money in integer paise, use file-locked atomic JSON updates, and isolate browser sessions.
- Checkout is simulated and requires explicit confirmation of a current cart preview.
- Catalogue/prices are synthetic fixtures. Never invent agronomic rates or dosage.
- Reuse the local STT engine and notebook VITS checkpoints via local_speech.py.
  Report the configured STT language; do not claim measured native speech accuracy.
- User-requested voice flow: press the browser microphone, speak, then stop to
  transcribe and submit automatically. Show the transcript and assistant reply
  in chat. Do not restore mandatory uploads or separate Transcribe/Send steps.
  This supersedes the older local skill's transcript-review step. Claim each
  recording before processing so Streamlit reruns cannot replay cart mutations.
- Keep keys in `.env` or password input; never write keys or recordings to traces.
- Use grounded response templates; model prose must not become agricultural advice.
- Run `python -m pytest -q` here and check actual MCP transport before handoff.

## Reusable guidance and memory

Use `skills/farmer-mcp-demo/SKILL.md` when extending this demo and
`skills/demo-verification/SKILL.md` when validating or preparing a presentation.
These skills are local references (not a global installation).
Read `README.md` for commands and limits. Save important decisions and measured
results in `../../idea/conversations/`, without overwriting previous notes.
