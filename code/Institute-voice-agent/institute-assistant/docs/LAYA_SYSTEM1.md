# Laya System 1 routing (local, zero-shot, English + Hindi)

Laya (https://github.com/NandhaKishorM/laya) is a non-autoregressive **System 1**
decision engine. This project can use it as the fast router that classifies a message's
intent/category/language before the main LLM, and skips the LLM routing call for
confident, safe queries. Unlike the older Open Jev classifier, Laya needs **no training
and no activation** — it is a published zero-shot checkpoint.

## Why it runs as a separate service

Laya depends on `transformers` 5.x; this project pins the shared model stack
(faster-whisper, Coqui TTS, sentence-transformers) to `transformers` 4.x. To avoid
replacing that stack, Laya runs in its **own virtual environment** as `laya-serve`, and
the agent talks to it over the Jev-compatible `POST /v1/systemone` HTTP protocol. The
agent never imports torch/transformers for routing.

## One-time setup

The isolated service already lives at `code/laya-service/`. To recreate it:

```bash
cd code/laya-service
python3 -m venv .venv
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
.venv/bin/python -m pip install "laya[serve]"
```

Checkpoints (~2.3 GB) download on first use into `code/laya-service/models/`.

## Run

```bash
cd code/laya-service
bash run-laya.sh      # serves http://127.0.0.1:8077, preloads english + multilingual (CPU)
```

Then enable it for the agent / Demo 2 (`.env`):

```ini
JEV_ROUTING_MODE=laya
LAYA_BASE_URL=http://127.0.0.1:8077
LAYA_PROBABILITY_THRESHOLD=0.5   # min max-probability to accept a local route
LAYA_CONFIDENCE_THRESHOLD=0.5    # min calibrated confidence
LAYA_REWRITE_THRESHOLD=0.5       # above this a knowledge query defers for rewrite
```

Restart the app. In Demo 2, **Runtime status** shows `jev_backend=laya` and
`jev_activation=serving` when the service is reachable (`unreachable` otherwise).

## What routes locally vs defers to the LLM

- Routes locally (fast path): confident English/Hinglish knowledge about IIIT Naya
  Raipur; English and Hindi smalltalk/greetings; clearly out-of-scope messages.
- Defers to the LLM (fail-safe): low-confidence messages; Devanagari-Hindi knowledge
  (needs an English rewrite for retrieval); action/reminder requests; follow-ups that
  need conversation history; anything not grounded to the institute; and whenever
  laya-serve is unreachable.

Routing decisions reuse the existing safety gates. Laya only ever **shortcuts** the LLM;
it never forces an unsafe answer. Correctness is protected by confidence gating.

## Tuning / improving coverage

Base checkpoints are zero-shot, so some English knowledge queries still defer. Lower the
thresholds for more coverage (less safe) or raise them for fewer, safer routes. For a
real accuracy jump, fine-tune Laya on a few hundred institute decisions with `laya-train`
(see the Laya README) and point `LAYA_EXTRA_MODELS` / `LAYA_MODELS` at the result.

## Tests

`tests/test_laya.py` covers the adapter mapping, language detection, the bilingual
routing policy, and the `try_route` laya path — all offline (no server, no weights).
Run with `python -m pytest tests/test_laya.py -q`.
