# Laya System 1 — Performance Results (routing latency, before vs after)

Date: 2026-10-16
Setup: tested machine (32 GB RAM, 8 GB RTX 4060), `minor` conda env, local Ollama
`qwen3.5:9b`, Laya served on CPU from the isolated `code/laya-service` venv.

## Headline

For a query Laya routes locally, the **routing stage** drops from a median of
**~2,100 ms** (LLM router) to **~210 ms** (Laya) — roughly **10× faster**, and up to
**~30×** against the heavier 9B evaluation runs (~6,000 ms median). Action messages
defer at preflight in **0 ms** (no call at all).

## Before — LLM routing via Ollama

Source: the project's own recorded `stage_ms.routing_model` values on this setup
(`Institute-voice-agent/institute-assistant/docs/local_model_*.json`,
`rag_memory_cache_live.json`). 90 recorded routing calls on qwen3.5 / 9B.

| Run file | n | min (ms) | median (ms) | max (ms) |
|---|---|---|---|---|
| `local_model_qwen35_9b_evaluation.json` | 9 | 4,671 | **6,089** | 11,024 |
| `local_model_9b_final.json` | 32 | 5,087 | **6,943** | 16,062 |
| `local_model_qwen35_full.json` | 32 | 1,589 | **1,914** | 5,695 |
| `rag_memory_cache_live.json` (warm) | 17 | 836 | **1,174** | 1,582 |
| **All combined** | **90** | **836** | **2,094** | **16,062** |

Mean across all 90 calls: **~4,113 ms**. The spread reflects model warm/cold state,
prompt length, and system load; the 9B "final evaluation" runs are the most
representative of a cold-ish local deployment.

## After — Laya System 1

Source: live end-to-end runs this session (`try_route` through the isolated
`laya-serve`, CPU, both checkpoints preloaded).

| Message | Routed? | Latency (ms) |
|---|---|---|
| EN smalltalk ("Thanks a lot!") | laya | 210 |
| Hindi smalltalk ("नमस्ते") | laya | 210 |
| Hinglish knowledge ("IIIT Naya Raipur hostel fees kitni hai") | laya | 220 |
| EN out_of_scope ("weather in Mumbai") | laya | 620 (first call, warming) |
| Action ("Please remind me…") | defer (preflight) | 0 (no HTTP) |

Laya classifier **median: ~210 ms**.

## The improvement, per route type

| Query type | Before (LLM routing) | After (Laya) | Speedup on routing stage |
|---|---|---|---|
| Routed locally (EN/Hinglish knowledge, smalltalk, out-of-scope) | ~2,100 ms median (≈6,000 ms on 9B eval runs) | ~210 ms | **~10× (up to ~30×)** |
| Smalltalk/greeting (whole turn) | full LLM routing + reply (seconds) | ~210 ms, canned reply, **no LLM at all** | largest end-to-end win |
| Action / history / low-confidence / Devanagari-knowledge | LLM path (unchanged) | LLM path (fail-safe) | 0 (no regression) |

## Caveats (so the numbers are not misread)

1. **Routing-stage latency, not whole-turn latency.** Routing is one stage. A full
   *knowledge* answer still runs retrieval + generation + grounding review (the 20–50 s
   the README documents). The dramatic end-to-end win is on smalltalk / greeting /
   out-of-scope turns, where routing *was* the entire LLM cost — those drop from seconds
   to ~210 ms.
2. **Only applies to queries Laya actually routes.** Zero-shot coverage is confident
   English/Hinglish knowledge, all smalltalk, and out-of-scope. Low-confidence and
   Devanagari-knowledge queries still take the LLM path — no speedup there, but no
   regression either (fail-safe).
3. **Measurement provenance.** The ~210 ms "after" was measured directly this session.
   The "before" numbers are from the project's own previously logged runs, **not**
   re-measured head-to-head in the same session. Treat the ratio as order-of-magnitude
   (≈10×, up to ≈30×), not a lab-controlled A/B.
4. **Correctness is gated, not traded for speed.** Laya only ever shortcuts the LLM; the
   confidence/institute/rewrite gates keep unsafe routes on the LLM path.

## How to reproduce a same-session A/B (optional, needs Ollama up)

Run the same message set twice — once with `JEV_ROUTING_MODE=off` (LLM router) and once
with `=laya` — comparing `rag_metrics.stage_ms` for the routing stage. This yields an
exact, controlled before/after on the current machine state.
