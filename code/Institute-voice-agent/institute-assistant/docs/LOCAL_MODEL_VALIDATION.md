# Local model validation — 23 September 2026

Demo 2 and the shared helpdesk default to Ollama `qwen3.5:9b` (Q4_K_M), with an
8192-token context and thinking disabled. Groq remains an explicit sidebar choice.
Routing, drafting, grounding review and pronunciation rendering share that selection.
There is no automatic cloud fallback. See [setup](LOCAL_INFERENCE.md).

## Hardware and tradeoff

Validated on this machine's 32 GB RAM and 8 GB RTX 4060 Laptop GPU, using the existing
`minor` environment and Ollama 0.32.6. Speech and embeddings run on CPU by default.
Ollama reported a 6.3 GB loaded model, with partial CPU offloading: 52% CPU/48% GPU
in the full run and 32% CPU/68% GPU in the final recheck. Desktop GPU usage varies.

The model runs locally, but it does **not** establish Groq speed or quality parity.
Answered turns in the full run had a median of **34.187 seconds**; individual questions
commonly took roughly 20–50 seconds. Each uncached factual answer includes routing,
generation and grounding review. First loading and long answers can take longer.

## Model comparisons

| Candidate | Observed behavior | Decision |
| --- | --- | --- |
| Llama 3.1 8B Q4 | Early six-case check passed four; Hindi/evidence and follow-up failures | Not selected |
| Qwen3 8B | Early quote/follow-up failures | Not selected |
| Qwen3.5 4B | Faster; constrained-evidence check passed 6/7, but category scope still failed | Not selected |
| Qwen3.5 9B Q4 | Passed 7/7 difficult comparison cases; full run 22/25 before follow-up fix | Selected |
| Qwen3.5 9B Q3_K_M | Full run 22/25 after follow-up fix; CG follow-up hit output limit and loan question was misrouted | Not selected |

These are development comparisons with evolving prompts, not a controlled leaderboard.
The early Llama/Qwen3 temporary artifacts were lost across the interrupted session;
their observations are not reproducible evidence of a complete benchmark.
Retained records include [9B comparison](local_model_qwen35_9b_evaluation.json),
[4B constrained comparison](local_model_qwen35_4b_constrained.json),
[9B Q4 full run](local_model_9b_final.json), and [Q3 full run](local_model_q3_final.json).

## Behavior and evidence

The full Q4 run passed **22/25** automated behavior expectations. Two failures were
English/Hinglish rank follow-ups: changing round 5 to round 4 reverted the latest ST
category to the older SC category. The fix applies only fully recognized short category
or round edits to the latest resolved query, preserving every other scope dimension.
It does not reuse historical answer facts. Other requests still use model routing.

The [final Q4 recheck](local_model_final_recheck.json), run with `GROQ_API_KEY` empty,
passed **5/5 cases (12 turns)**: CG-quota follow-up, loan scholarship exclusion, and
the complete English, Hindi and Hinglish category/round chains. The full 25-case suite
was not repeated after this narrow follow-up fix; these targeted results do not turn
the earlier full run into a claimed 25/25 pass.
The 12 rechecked turns had a median of **23.711 seconds**, ranging from 19.169 to
47.053 seconds under the later GPU allocation.

The third failure was the reporting-document question. The router correctly changed topics,
but the answer abstained because retrieved JoSAA reporting pages contain the checklist
heading without its entries. Other retrieved excerpts contain quota-specific application
certificates, not the complete reporting checklist. The existing test expects an answer;
that expectation remains failing. The approved index was not changed, and no checklist was
invented. Repairing this requires a separately reviewed source extraction.

Local structured decoding now binds evidence IDs to contiguous original source spans.
This prevents rewritten/misattributed quotations; it does not establish factual support
by itself. Grounding review and final citation validation remain mandatory, including
when a cached draft is reused. Public evaluation records retain answers and evidence for
inspection. Status checks alone are not an accuracy score.

## Cache measurement

The [exact-repeat benchmark](local_model_cache_final.json) passed **2/2 checks** in
separate conversation sessions with an isolated persistent cache:

| State | Total answer time | Logical model calls | Retrieval / draft cache |
| --- | --- | --- | --- |
| Empty application cache | 25.882 s | 3 | miss / miss |
| Repeated question | 12.687 s | 2 | hit / hit |

The repeated answer still ran routing and grounding review. This is one sample, not a
latency guarantee. The model was already resident; “cold” in the raw record means the
application cache was empty, not that Ollama was unloaded.

## Offline regression checks

`python -m pytest -q` in each project, using `minor`:

- Shared helpdesk: **142 passed**; 128 existing Chroma/LangChain Pydantic deprecation warnings.
- Demo 2: **17 passed**.

Coverage includes local operation without a Groq key, provider isolation between concurrent
graph sessions, malformed/truncated responses, model/context/tokenizer failures, bounded
history/evidence, model-digest cache invalidation, exact evidence grammar, multilingual
follow-up scope, sidebar switching without resubmission, and audio retry provider retention.
Tests use isolated state and mocked providers; real calls are recorded separately.

## Operational limits

Hindi VITS and Whisper recognition run locally after their model assets are cached.
English/Hinglish audio still uses **online Edge TTS**. A local answer therefore does not
mean every speech mode is offline. A failed speech request leaves the text answer available.
Chhattisgarhi remains experimental.

The final Demo 2 Hindi smoke test passed with an empty `GROQ_API_KEY`, `HF_HUB_OFFLINE=1`
and `TRANSFORMERS_OFFLINE=1`: synthesized question → Whisper transcript → grounded
Ollama answer with two sources → local VITS reply. The output was a 22,050 Hz,
7.47-second WAV. The question audio was generated by the app itself; this verifies
integration, not real microphone recognition accuracy. Both local VITS voices and
a separate Hindi STT check also passed. The local renderer needed an explicit
Devanagari pronunciation instruction for abbreviations such as IIIT and JEE;
the completed pipeline passed after that fix.

Groq code and configuration are preserved and regression-tested. The attempted live Groq
check encountered a rate limit; this work does not claim a successful current cloud check.
No Python speech/model dependency versions were upgraded and no knowledge-base rebuild
or action replay was needed.
