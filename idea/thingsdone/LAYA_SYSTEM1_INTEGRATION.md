# Laya System 1 Routing Integration — Work Log

Date: 2026-10-16 Scope: Demo 2 (`code/demo2`) + shared agent (`code/Institute-voice-agent/institute-assistant`) Author: implementation session

## 1. Goal

Replace the non-working "Open Jev" System 1 router with the local **Laya** non-autoregressive decision engine (https://github.com/NandhaKishorM/laya), make it actually work, support **Hindi + English**, and reduce inference latency by skipping the LLM routing call for confident, safe queries.

## 2. What "System 1" is here, and why the old one did not work

The router is a **fast classifier** that runs before the main LLM. For each user message it decides `intent` / `category` / `language` and whether the message needs a rewrite. When it is confident and the message is safe, it returns a `RoutingDecision` and the graph **skips the LLM routing generation** (a multi-second Ollama call), going straight to retrieval or a canned reply. Otherwise it falls through to the LLM router.

The old "Open Jev" classifier never worked in practice because:

1. `JEV_ROUTING_MODE` defaults to `off`.
2. Even set to `shadow`/`enabled`, it requires a **locally trained + activated model artifact** (`model.pt`, `manifest.json`, `activation.json`, calibrated thresholds, a passing holdout evaluation). That artifact was never produced, so `try_route` always fell through to the LLM. The training/activation pipeline is long and gated.

Laya removes that blocker: it is a **published, zero-shot** checkpoint. No training, no activation certificate. It answers typed `choice`/`noul` questions in one forward pass (tens of ms), and it speaks the **same `POST /v1/systemone` wire protocol** the project's Jev integration already models.

## 3. The one hard constraint: do not replace the shared model stack

The `minor` conda env has `transformers 4.46.1`. Installing `laya` into it would force `transformers → 5.20.0`, `tokenizers → 0.23.3`, `huggingface_hub → 2.2.0` (verified with `pip install --dry-run laya`). The project rule is explicit and repeated in the README: **"Do not replace the shared model stack."** That upgrade would risk faster-whisper, Coqui TTS, sentence-transformers, the retrieval embeddings, and the whole passing test suite.

### Decision: isolated `laya-serve` + Jev-compatible HTTP

Laya runs in its **own virtual environment** (`code/laya-service/.venv`, Python 3.14, its own `transformers 5.20.0`, CPU `torch 2.14.1`). The agent talks to it over `POST /v1/systemone`. Nothing in the agent imports torch/transformers for routing — the adapter uses only `urllib` + `json`. The `minor` stack is untouched. Latency still improves, because a ~210 ms local HTTP classifier call replaces a multi-second LLM routing generation for every locally-routed query.

## 4. What was built

### 4.1 Isolated service — `code/laya-service/`

- `.venv/` — isolated venv with `laya[serve]` 0.4.8 (CPU torch).
- `models/` — the downloaded checkpoints (`laya` English + `laya-multilingual`), cached via `HF_HUB_CACHE`, ~2.3 GB, gitignored by size.
- `run-laya.sh` — launcher. Preloads `english,multilingual` on CPU, binds `127.0.0.1:8077`, caps threads. CPU by default to reserve GPU for Ollama.

### 4.2 Adapter — `assistant/jev/laya_adapter.py` (new)

- `LAYA_QUESTIONS` — the typed questions sent to Laya: `intent` (choice, 7 labels), `category` (choice, 5 labels), `rewrite` (noul). **Language is deliberately not a question** — see the key finding below.
- `language_from_detection(message, routing)` — derives english/hindi/hinglish (or None) from Laya's reliable `routing.detection` (script + language), mirroring `dialogue.language_hint`.
- `to_prediction(payload, message)` — maps the `/v1/systemone` answer payload onto the exact `prediction` dict the project's routing policies consume (intent/category/… `_probability`/`_confidence`/`_distribution`, `rewrite_probability`, plus the detection-derived language fields). Validates labels/distributions; raises `LayaUnavailable` on anything malformed.
- `request_prediction(base_url, message, timeout)` — the HTTP call (urllib). Only the message text leaves the process, only to the configured local URL. No history/profile.
- `institute_mentioned(message)` — bilingual institute matcher: the shared `INSTITUTE` regex (English) **plus** a Devanagari spelling (`IIIT नया रायपुर`, `आईआईआईटी`).
- `laya_route(message, prediction, thresholds)` — the **bilingual acceptance policy**. Reuses the shared safety gates (SAFE_INTENTS, confidence/probability thresholds, institute grounding, rewrite ceiling) but keeps Hindi/Hinglish instead of rejecting them. Returns `(RoutingDecision | None, reason)`.

### 4.3 Runtime wiring — `assistant/jev/runtime.py`

- `try_route` gets a `mode == "laya"` branch → `_try_laya(...)`, which **bypasses the artifact/activation machinery entirely**.
- `_laya_preflight` — keeps Hindi (unlike `common.preflight`, which rejects non-English) but still refuses empty/oversized input, pending actions, and action/reminder phrasing (those must reach the full graph).
- `_try_laya` — history defers before any HTTP call; calls the adapter; applies `laya_route`; records metrics (`router_backend=laya`, `router_path`, `router_fallback`, `stage_ms.classifier`). Any `LayaUnavailable` or error **fails safe to the LLM router**.

### 4.4 Config — `assistant/config.py`

- New settings: `LAYA_BASE_URL` (default `http://127.0.0.1:8077`), `LAYA_PROBABILITY_THRESHOLD` (0.5), `LAYA_CONFIDENCE_THRESHOLD` (0.5), `LAYA_REWRITE_THRESHOLD` (0.5).
- `JEV_ROUTING_MODE` now accepts `laya` (alongside `off`/`shadow`/`enabled`), with validation of the URL and the three probability thresholds.

### 4.5 Health — `demo2/health.py`

- When `JEV_ROUTING_MODE=laya`, `runtime_health()` reports `jev_backend=laya`, `jev_artifact=laya-serve`, `laya_base_url`, and `jev_activation` = `serving` / `unreachable` by probing `GET /models`. The artifact-reading block is skipped in laya mode so it never reports a (correctly) missing artifact.

### 4.6 Env — `demo2/.env`, `demo2/.env.example`

- Documented `JEV_ROUTING_MODE=laya`, `LAYA_BASE_URL`, and the three thresholds. Default stays `off` so nothing changes until laya-serve is started and the mode is set.

### 4.7 Tests — `tests/test_laya.py` (new, 21 tests)

- Fully offline (no server, no weights, no torch): fakes the `/v1/systemone` payload and monkeypatches `request_prediction`.
- Covers language detection (5 langs), schema mapping, malformed-payload rejection, the bilingual policy (EN/Hindi/Hinglish knowledge, smalltalk, institute grounding, unsafe intent, low confidence, high rewrite, Devanagari→defer), and `try_route` wiring (success, history-defer, action-defer-without-HTTP, unavailable-fail-safe).

## 5. Key engineering finding: use routing detection for language, not a question

Asking Laya a `choice` **language** question is unreliable zero-shot — it labelled `"Thanks a lot!"` as Hindi (0.43) and Devanagari Hindi as "unsupported" (0.63). But Laya's **`routing.detection`** (dependency-free script analysis, <0.5 ms) is accurate every time: `script` (latin/devanagari/…), `is_english`, `language`, and the routed checkpoint. The adapter therefore drops the language question and derives language from detection. This is exactly what Laya's own README recommends.

## 6. Multilingual (Hindi + English) behaviour

| Message                                                       | Routed?               | Why                                                                         |
| ------------------------------------------------------------- | --------------------- | --------------------------------------------------------------------------- |
| EN smalltalk ("Thanks", "Hello")                              | **laya**              | intent smalltalk ~1.0                                                       |
| Hindi smalltalk ("नमस्ते")                                    | **laya**              | detection=Hindi, smalltalk confident                                        |
| EN out_of_scope ("weather in Mumbai")                         | **laya**              | confident out_of_scope                                                      |
| Hinglish knowledge ("IIIT Naya Raipur hostel fees kitni hai") | **laya**              | knowledge 0.997, cat hostel 1.0                                             |
| EN knowledge ("hostel fees at IIIT Naya Raipur")              | laya when ≥ threshold | zero-shot knowledge conf ~0.5–0.56 is borderline                            |
| Hindi (Devanagari) knowledge                                  | **defer to LLM**      | retrieval needs an English rewrite Laya can't produce → `needs_translation` |
| Action ("remind me…")                                         | **defer (0 ms)**      | preflight catches it before any HTTP call                                   |

Design stance (matches the README): **Hindi/Hinglish smalltalk & out-of-scope route locally; Devanagari knowledge queries defer to the LLM for translation/rewrite.** Roman Hindi (Hinglish) knowledge routes locally because retrieval reads Latin text directly.

## 7. Latency

- Laya classifier (CPU, preloaded): **~210 ms median** per message; action messages defer at preflight in **0 ms** (no HTTP).
- It replaces the LLM routing generation, which on the tested machine is a multi-second Ollama call (local answers overall run 20–50 s per the README). Greetings/thanks now get an instant canned reply with **no LLM call at all**.
- Correctness is protected by confidence gating: anything below threshold, non-English needing rewrite, non-institute knowledge, or an action request falls through to the LLM. Laya only ever _shortcuts_; it never forces an unsafe answer.

## 8. Verification (all run in the `minor` env)

- New Laya suite: `pytest tests/test_laya.py` → **21 passed**.
- Full agent suite: `pytest` in `institute-assistant` → **309 passed, 0 failed**.
- Demo 2 suite: `pytest` in `demo2` → **42 passed, 0 failed**.
- Live end-to-end against a running `laya-serve`: EN/Hindi/Hinglish routing + latency table above reproduced.
- Isolated venv import check: `laya 0.4.8`, its own `transformers 5.20.0` — the `minor` env still reports `transformers 4.46.1` (shared stack untouched).

## 9. Reusing vs removing the old Jev files (decision)

The Laya path **reuses** the shared infrastructure: `common.py` (SAFE_INTENTS, INTENTS, CATEGORIES, INSTITUTE), `runtime.py`, `config.py`, `nodes.py`, `llm.RoutingDecision`, `dialogue.language_hint`. The integration is purely additive.

The old **trained-classifier** modules (`english_v3_training.py`, `english_training.py`, `data.py`, `evaluation.py`, `paired_benchmark.py`, the corpus `.txt` files, and `vendor/model.py`) were **kept, not removed**. They are not dead code: they are the alternative `shadow`/`enabled` backend and are covered by ~84 passing tests (`test_jev.py`, `test_jev_english.py`, `test_jev_v3.py`) plus the documented `ENGLISH_ROUTER_RECOVERY.md` / `OPEN_JEV.md` recovery paths. Deleting them would break the suite and remove a working (if unused-by-default) feature — a destructive, high-blast-radius change. If the trained-classifier path is ever formally abandoned, the safe removal set is: those modules **and** their three test files **and** the `shadow`/`enabled` branches in `runtime.try_route` **and** their doc pages — as one reviewed change.

## 10. How to run it

```bash
# 1) one-time: the isolated service + checkpoints already exist at code/laya-service/
#    (re-create with: python3 -m venv .venv && .venv/bin/pip install laya[serve])

# 2) start the service (keep it running)
cd "code/laya-service"
bash run-laya.sh            # http://127.0.0.1:8077, preloads english+multilingual (CPU)

# 3) point Demo 2 at it: in demo2/.env
JEV_ROUTING_MODE=laya
LAYA_BASE_URL=http://127.0.0.1:8077
# thresholds default to 0.5 / 0.5 / 0.5

# 4) restart Demo 2. Sidebar "Runtime status" shows jev_backend=laya,
#    jev_activation=serving when the service is reachable.
```

## 11. Files changed/added

Added:

- `code/laya-service/` (venv, models, `run-laya.sh`)
- `code/Institute-voice-agent/institute-assistant/assistant/jev/laya_adapter.py`
- `code/Institute-voice-agent/institute-assistant/tests/test_laya.py`
- `code/Institute-voice-agent/institute-assistant/docs/LAYA_SYSTEM1.md` (guide)
- this work log

Modified:

- `assistant/jev/runtime.py` — `laya` mode branch, `_try_laya`, `_laya_preflight`
- `assistant/config.py` — LAYA\_\* settings + `laya` mode validation
- `demo2/health.py` — laya-serve reachability in runtime status
- `demo2/.env`, `demo2/.env.example` — documented laya mode + thresholds

## 12. Honest limits

- Laya base checkpoints are **zero-shot**; `knowledge` intent confidence on this domain is borderline (~0.5–0.56), so some English knowledge queries still defer to the LLM. Fine-tuning (`laya-train`, see the README) on a few hundred institute decisions would raise coverage substantially. This is a coverage/latency tradeoff, not a correctness risk — the gates keep unsafe routes out.
- Devanagari knowledge intentionally defers (needs English rewrite for retrieval).
- The service must be running; if it is down, routing fails safe to the LLM.
