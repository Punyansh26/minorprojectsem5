# 02 — Latency, Cost Model and Metrics

This chapter gives the equations the other chapters use to estimate an effect before
building anything. Each worked number is labelled. Symbols are listed once in §8.

## 1. What the user feels: perceived latency

In a voice agent the number that matters is the silence between the user finishing and the
agent starting to speak [R02][R94]. For a cascaded pipeline (STT → LLM → TTS):

$$
T_{\text{perceived}} = t_{\text{EOU}} + t_{\text{ASR,residual}} + t_{\text{LLM,TTFT}} + t_{\text{TTS,TTFB}} + t_{\text{transport}}
$$

- $t_{\text{EOU}}$: time from the last spoken word until the system decides the turn ended
  (silence timeout or end-of-turn model). Today it is a button press plus upload.
- $t_{\text{ASR,residual}}$: ASR work still left after the end of turn. With streaming ASR
  most of the audio is already transcribed, so only the last chunk remains. With today's
  batch ASR it is the whole transcription.
- $t_{\text{LLM,TTFT}}$: time to the first token **that can be spoken**. For a JSON answer
  that must be reviewed, this is today the whole routing + generation + review time.
- $t_{\text{TTS,TTFB}}$: time until the first audio frame of the first sentence.

R02 measured $T_{\text{perceived}}$ p50 1.39 s / p95 3.38 s with LiveKit, Deepgram STT,
Ministral 3B on Ollama and Pocket TTS, of which LLM TTFT was the largest and most variable
term (p50 566 ms, p95 2.2 s) [Reported]. Human turn gaps are typically 200–300 ms; above
~800 ms calls start to feel unnatural [R94, Reported].

**Tool turns have two silences** [R02]: one before an acknowledgement ("let me check") and
one after the tool returns. The design goal is to make the first silence short and fill the
second with speech or a sound.

### 1.1 Sequential vs streaming overlap

With $n$ sequential stages, latency adds: $T = \sum_i t_i$.
With streaming, each stage starts on the first chunk of the previous one, so the time to
first output is the sum of each stage's **first-chunk** latency, not its full duration:

$$
T_{\text{first audio}}^{\text{stream}} = \sum_i t_i^{\text{first chunk}}
\quad\ll\quad
T^{\text{batch}} = \sum_i t_i^{\text{full}}
$$

Example **[Estimated]** with today's components on T0: if the reviewed answer could be
released sentence by sentence, the first sentence (~25 tokens) would need about
$25 / 17.7 \approx 1.4$ s of decoding instead of the full answer. This is only possible if
verification can work per sentence (see [06](06_VERIFICATION_AND_CACHING.md)).

## 2. One LLM call

$$
t_{\text{call}} = t_{\text{load}} + t_{\text{overhead}} + \frac{N_{\text{prompt}} - N_{\text{reused}}}{r_{\text{prefill}}} + \frac{N_{\text{out}}}{r_{\text{decode}}}
$$

Measured on T0 with `qwen3.5:9b` **[Measured-here, 01 §4.3]**:
$t_{\text{load}} = 8.3$ s cold (0 s when resident), $r_{\text{prefill}} \approx 820$ tok/s,
$r_{\text{decode}} \approx 17.7$ tok/s free text, ≈6.4 tok/s under a 300-entry enum grammar.
`IA/assistant/operations.py::record_attempt` already captures `prompt_eval_count`,
`prompt_eval_duration`, `eval_count` and `eval_duration` per call, so the terms can be
split for real traffic without new instrumentation. They are not written to the benchmark
JSON yet.

Decode dominates whenever $N_{\text{out}} / r_{\text{decode}} > N_{\text{prompt}} / r_{\text{prefill}}$,
i.e. here whenever $N_{\text{out}} > N_{\text{prompt}} \cdot 17.7/820 \approx 0.022\,N_{\text{prompt}}$.
A 3,000-token prompt with more than ~65 output tokens is decode-bound. Every answer with
evidence quotes is far above that. **Output tokens are the expensive resource**, which is
why the evidence-quote JSON and the duplicated review are costly.

### 2.1 Why decoding is memory-bound

Generating one token reads (almost) every weight once. With weights split between GPU and
CPU, a token costs roughly

$$
t_{\text{token}} \approx \frac{B_{\text{GPU}}}{\text{BW}_{\text{GPU}}} + \frac{B_{\text{CPU}}}{\text{BW}_{\text{CPU}}}
$$

where $B$ are bytes of weights resident on each device and BW the effective memory bandwidth.

Worked check on T0 **[Estimated]**: Qwen3.5-9B text weights at Q4_K_M ≈ 9.7 B params ×
≈4.8 bit ≈ 5.6 GB (Ollama reports 6.3 GB including the vision tower and buffers). With 45%
on CPU: $B_{\text{CPU}} \approx 2.5$ GB, $B_{\text{GPU}} \approx 3.1$ GB. Assuming
≈60 GB/s effective dual-channel DDR5 and ≈180 GB/s effective of the 4060 Laptop's
256 GB/s peak (both assumptions; not measured):
$t_{\text{token}} \approx 3.1/180 + 2.5/60 \approx 17 + 42 = 59$ ms → **≈17 tok/s**, close to
the measured 17.7 tok/s. The CPU part costs about 2.4× the GPU part. Fully on GPU the same
formula gives $5.6/180 \approx 31$ ms → **≈32 tok/s**, so getting the model fully into
VRAM should roughly double decode speed on T0.

| Tier | Example GPU | Peak BW | 9B Q4 single-stream decode **[Estimated]** = 0.7·BW / 5.6 GB |
|---|---|---:|---:|
| T0 (all on GPU) | RTX 4060 Laptop | 256 GB/s | ~32 tok/s |
| T0 (today, 45% CPU) | — | — | ~17 tok/s (measured 17.7) |
| T1 | RTX 4090 | ~1,008 GB/s | ~125 tok/s |
| T2 | H100 SXM (FP8, 9.7 GB) | ~3,350 GB/s | ~240 tok/s per stream, more with batching |

Peak bandwidths are vendor specifications; the 0.7 efficiency factor is an assumption to be
replaced by measurement. Batching on T1/T2 reads the weights once for many sequences, so
aggregate throughput rises almost linearly until compute-bound ([10](10_THROUGHPUT_CONCURRENCY_AND_TELEPHONY.md)).

## 3. Memory: will it fit?

$$
M_{\text{VRAM}} = M_{\text{weights}} + M_{\text{KV}} + M_{\text{state}} + M_{\text{compute}} + M_{\text{other processes}} \le M_{\text{GPU}}
$$

For standard attention: $M_{\text{KV}} = 2 \cdot L_{\text{attn}} \cdot H_{\text{kv}} \cdot d_{\text{head}} \cdot n_{\text{ctx}} \cdot b$.

Qwen3.5-9B is hybrid [R90]: of 32 layers only 8 are full attention (every 4th); the other 24
are Gated DeltaNet linear-attention layers with a fixed-size recurrent state. With
$H_{\text{kv}} = 4$, $d_{\text{head}} = 256$:

| Item | Formula | Size **[Estimated]** |
|---|---|---:|
| KV cache, f16, 8,192 ctx | 2·8·4·256·8192·2 B | **256 MiB** |
| KV cache, q8_0 | half | 128 MiB |
| DeltaNet state (fp32), per sequence | 24 layers · 32 heads · 128 · 128 · 4 B | ≈48 MiB (+ small conv state) |
| Logits buffer for a 512-token prefill batch | 512 · 248,320 vocab · 4 B | ≈485 MiB |
| Output head (untied, 248,320 × 4,096) at ~Q6 | ≈1.0 B params | ≈0.8 GB of the weights |
| Desktop and other processes (measured) | — | 2,737 MiB **[Measured-here]** |

Consequences:

- **KV-cache quantization saves little on this model** (≈128 MiB), unlike dense models
  where it halves a multi-GB cache [R42].
- The levers that move gigabytes are: freeing desktop VRAM (≈2.7 GB, e.g. running the
  display on the integrated GPU), excluding the vision tower, a smaller prefill batch
  (smaller logits buffer), a lower-bit quant, or a smaller model ([05](05_LLM_INFERENCE_AND_SERVING.md)).
- Context length is cheap here, so lowering `num_ctx` from 8192 frees little memory. It
  matters for prefill time, not for fitting.

The vocabulary is large (248,320 tokens), which also makes JSON-grammar masking more work
per token, consistent with the 2.6× slowdown measured with a big enum.

## 4. Combining stages: Amdahl's law

If a fraction $p$ of the turn is sped up by factor $s$:

$$
S_{\text{turn}} = \frac{1}{(1-p) + p/s}
$$

Worked **[Estimated]** from the baseline answered-turn medians (01 §4.1), $T \approx 18.7$ s:

| Change | $p$ | $s$ | New turn |
|---|---:|---:|---:|
| 100× faster retrieval | 0.003 | 100 | 18.6 s (useless) |
| Remove routing call (learned router, 100% coverage) | 0.20 | ∞ | 14.9 s |
| Replace 9B review by a 0.3 s checker | 0.40 | ~25 | 11.6 s |
| Model fully on GPU (≈2× decode) | ~0.95 | 2 | ≈9.8 s |
| All three together | — | — | ≈4–5 s |

Retrieval is already fast; optimisation effort belongs in the LLM calls and in streaming.

## 5. Tails: p50 is not enough

Sequential stages add their delays, and tails compound: if each of three LLM calls has a
5% chance of being slow, the chance that at least one is slow is $1-0.95^3 \approx 14\%$.
Report p50, p95 and p99 per stage and per turn, with bootstrap confidence intervals
([12](12_EVALUATION_AND_BENCHMARKING.md)). The JEV router lowered the median but raised p95
(01 §5), so a change can look good at p50 and still fail users.

## 6. Energy and cost per turn

$$
E_{\text{turn}} = \int P(t)\,dt \approx \bar P_{\text{GPU}}\,t_{\text{GPU}} + \bar P_{\text{CPU}}\,t_{\text{CPU}},
\qquad C_{\text{turn}} = E_{\text{turn}} \cdot \text{price}_{\text{kWh}} + \frac{C_{\text{hardware}}}{N_{\text{turns over lifetime}}}
$$

Measure $P$ by sampling `nvidia-smi --query-gpu=power.draw` and CPU package power from
`/sys/class/powercap/intel-rapl*` during a benchmark run. Only idle GPU power was read for
this report (16.8 W) **[Measured-here]**, so the existing "$0.60/month" figure remains an
estimate (01 §6). A cloud comparison must state its price date and is labelled
[Reported]/[Estimated]; it is not part of the local design.

Hardware amortisation usually dominates electricity for a single laptop. Faster turns lower
energy per turn roughly in proportion to the GPU-busy time.

## 7. Latency budget sheet

Targets per stage for a **knowledge question** (one grounded answer). Today's values are
[Measured-here] where marked; targets are [Estimated] planning goals derived from §1–4 and
from the sources cited in chapters 03–07.

| Stage | Today T0 | Target T0 | Target T1 | Target T2 | Chapter |
|---|---:|---:|---:|---:|---|
| End of turn ($t_{\text{EOU}}$) | button + upload | 300–600 ms | 300–500 ms | 300–500 ms | 03 |
| ASR residual | not measured (full clip) | 150–400 ms | 100–200 ms | <100 ms | 03 |
| Routing | 3.8 s (p50) | 0–100 ms (classifier) | 0–50 ms | 0–50 ms | 05, 09 |
| Retrieval (+ rerank) | 50 ms | 50–200 ms | 30–100 ms | 20–50 ms | 04 |
| Generation to first speakable sentence | 7.2 s (whole JSON) | 1.5–3 s | 0.3–0.8 s | 0.2–0.5 s | 05 |
| Verification | 7.4 s (9B review) | 0.1–0.5 s (checker) + selective 9B | 0.1–0.3 s | <0.1 s | 06 |
| TTS first audio | whole file; greeting 3.7–4.5 s | 0.2–0.5 s | 0.1–0.3 s | <0.1 s | 07 |
| **Perceived latency** | ≈18–24 s + TTS | **2.5–5 s** | **≈1–1.5 s** | **<1 s** | 13 |

Each technique in later chapters states which row it moves and by how much.

## 8. Instrumentation good practice

- One trace per turn with one span per stage (EOU, ASR partial/final, routing, retrieval,
  rerank, LLM prefill/decode, verification, TTS first chunk, playback start). OpenTelemetry
  GenAI conventions and a self-hosted Langfuse instance do this locally [R92]; R02 shows
  the method on a voice agent.
- Extend the existing `rag_metrics.stage_ms` (`IA/assistant/metrics.py`) with Ollama's
  token counts and durations (already captured by `operations.record_attempt`), cache
  outcomes, CPU/GPU split from `ollama ps`, and audio timestamps from the browser.
- Always record model residency and other GPU users; the same code ran at 52/48 and 32/68
  CPU/GPU splits in two runs (01 §4.2).
- Separate cold (first turn after load) from warm measurements.

## 9. Symbols

| Symbol | Meaning |
|---|---|
| $t_{\text{EOU}}$ | end-of-utterance decision delay |
| TTFT / TTFB | time to first token / first audio byte |
| $r_{\text{prefill}}, r_{\text{decode}}$ | prompt and generation speed (tok/s) |
| $N_{\text{prompt}}, N_{\text{reused}}, N_{\text{out}}$ | prompt tokens, prefix tokens served from cache, output tokens |
| $L_{\text{attn}}, H_{\text{kv}}, d_{\text{head}}, n_{\text{ctx}}, b$ | attention layers, KV heads, head size, context length, bytes per element |
| BW | effective memory bandwidth |
| $p, s$ | Amdahl fraction and stage speedup |
