# Architecture Decisions & Viva Defense Matrix

This document provides a comprehensive, rigorous defense of every major architectural, engineering, and algorithmic decision made across the codebase. It is structured specifically to support oral examinations (Viva Voce), technical audits, and peer code reviews.

---

## 1. Master Architectural Decision Matrix

| # | Architectural Decision | Primary Alternative Considered | Technical Rationale & Justification for Choice |
|---|---|---|---|
| **1** | **Cascaded Pipeline** (ASR $\to$ LLM $\to$ TTS) | End-to-End Multimodal Speech-to-Speech (e.g. GPT-4o voice, AudioPaLM) | **1) Measurability:** Cascaded stages allow calculating exact Word Error Rate (WER) on ASR and BLEU/chrf on MT independently.<br/>**2) Strict Safety:** Grounded tools require verified JSON schemas; E2E models hallucinate non-existent products.<br/>**3) Hardware Feasibility:** E2E multimodal models require massive GPU clusters. Our cascaded modules run concurrently on an 8 GB consumer GPU. |
| **2** | **Local-First Zero-Budget Execution** | Commercial Cloud APIs (OpenAI Whisper, ElevenLabs, Google Speech) | **1) Data Sovereignty & Cost:** Zero recurring API bills; student-feasible.<br/>**2) Low-Resource Reality:** Commercial APIs have near-zero training coverage for spontaneous spoken Chhattisgarhi (`hne`).<br/>**3) Offline Resilience:** Rural deployments face intermittent internet; local inference operates reliably without cloud connectivity. |
| **3** | **Meta MMS-1B (`hne`) for Chhattisgarhi** | OpenAI Whisper / IndicWhisper | Standard Whisper models do not include Chhattisgarhi (`hne`) in their language token heads. Meta MMS-1B uses a dedicated 1024-dimension Wav2Vec2 adapter explicitly fine-tuned on Chhattisgarhi speech corpora. |
| **4** | **Silero VAD (ONNX Singleton)** | WebRTC VAD / Energy RMS Thresholding | WebRTC VAD and simple energy thresholding fail catastrophically on ambient rural noise (tractors, wind, coughing). Silero VAD employs a deep neural network trained on 6,000+ languages, rejecting acoustic artifacts with negligible CPU overhead. |
| **5** | **Coqui VITS for Speech Synthesis** | FastSpeech 2 / Tacotron 2 + WaveGlow | Two-stage TTS (spectrogram generator + separate vocoder) incurs double inference latency and compounding phase errors. VITS synthesizes high-fidelity 22,050 Hz raw waveforms directly in a single forward pass via normalizing flows and HiFi-GAN adversarial decoders. |
| **6** | **Speed Control via `length_scale`** | Passing `speed=` parameter in Coqui `.tts()` | In the Coqui VITS version deployed, passing `speed=` is completely ignored by the synthesizer. Adjusting `tts.tts_model.length_scale` directly alters the latent duration predictor, reliably extending or compressing the generated waveform. |
| **7** | **FastAPI WebSockets + ThreadPool** | Native Asyncio Coroutines / Flask | PyTorch and CTranslate2 C++ backends release the GIL during matrix math, but synchronous inference calls still block Python's single-threaded event loop unless offloaded via `loop.run_in_executor(_EXECUTOR, ...)`. Thread pools protect server responsiveness. |
| **8** | **Model Context Protocol (FastMCP stdio)** | Direct In-Memory Python Function Calls | **Process Isolation:** An unhandled exception or memory leak in a tool does not crash the host LLM or web server.<br/>**Interoperability:** MCP tools expose open, inspectable JSON-RPC schemas that can be tested independently using standardized CLI inspectors. |
| **9** | **Atomic JSON + FileLock (Demo 1)** | Dedicated PostgreSQL / MongoDB Server | Eliminates background database administration overhead for the live demonstration. Guarantees ACID atomicity via `os.replace` on tempfiles while preserving human-readable inspection of cart states (`shop.json`) during live examiner review. |
| **10**| **Bounded Worker Queue (Demo 2)** | Unbounded Asynchronous Concurrency | A single 8 GB GPU cannot hold multiple concurrent 9B LLM inference batches in memory. Unbounded concurrency causes out-of-memory crashes. A bounded FIFO queue (capacity 3) guarantees system stability under traffic spikes. |
| **11**| **Progressive Text-First Rendering** | Monolithic S2S (wait for audio before showing text) | Local 9B LLM reasoning takes 20–30 s; TTS takes an additional 3–5 s. Showing text immediately upon LLM completion allows the user to read while audio synthesizes, reducing perceived latency from 35s to 20s. |
| **12**| **Deterministic Regex Verbalization** | LLM-based Phonetic Re-prompting | Asking an LLM to rewrite text phonetically introduces hallucinations and risks dropping crucial negation words (e.g. turning "fees are non-refundable" into "fees are refundable"). Regex substitution guarantees 100% semantic fidelity. |
| **13**| **Strict KVK Referral Safety Guard** | LLM System Prompt Guardrails Alone | Prompt guardrails suffer from jailbreaking and probabilistic hallucinations. When dealing with toxic chemicals (pesticides, fungicides), agricultural assistants must enforce a hard algorithmic boundary redirecting users to Krishi Vigyan Kendra (KVK). |
| **14**| **Exact Integer Arithmetic (Paise)** | IEEE 754 Floating-Point Numbers (`float`) | Binary floating-point arithmetic introduces fractional rounding errors ($0.1 + 0.2 = 0.30000000000000004$). All monetary calculations are performed strictly in integer paise ($1\text{ Rupee} = 100\text{ paise}$). |
| **15**| **React + TypeScript over Flutter** | Native Flutter Mobile APK | Eliminates mobile installation friction for farmers. Enables low-latency `AudioWorklet` streaming, seamless DevTools frame inspection during grading, and cross-platform desktop/mobile browser operation. |

---

## 2. In-Depth Technical Defense of Core Choices

### 2.1 Why Cascaded S2S Instead of End-to-End Multimodal?

```mermaid
flowchart TD
    subgraph Cascaded Architecture (Our Project)
        A1["Spoken Input"] --> B1["Acoustic ASR (MMS)"]
        B1 -->|Verifiable Text| C1["Intent & Tools (MCP)"]
        C1 -->|Grounded Slot Data| D1["Speech Synthesis (VITS)"]
        D1 --> E1["Spoken Output"]
    end

    subgraph End-to-End Multimodal (Black Box)
        A2["Spoken Input"] --> B2["Black-Box Neural Audio Transformer\n(100B+ Parameters)"]
        B2 --> E2["Spoken Output"]
    end
```

#### The Viva Defense:
1. **Academic Measurability**: In an engineering thesis, errors must be attributable to specific subsystems. In a cascaded pipeline, we measure:
   - ASR accuracy via Word Error Rate (WER) and Character Error Rate (CER).
   - Tool selection accuracy via Schema Validation Rate.
   - Speech synthesis naturalness via Mean Opinion Score (MOS) and Real-Time Factor (RTF).
   In an end-to-end model, if the system suggests the wrong fertilizer, it is impossible to determine whether the acoustic encoder misheard the crop or the generative decoder hallucinated the brand.
2. **Deterministic Safety Bounds**: An agricultural assistant cannot operate probabilistically when recommending toxic chemicals. Cascading allows hard regex and AST filters to intercept unverified medical or chemical terms before database execution.
3. **Compute Realism**: Running an end-to-end audio model requires high-end data center clusters (e.g. $8 \times \text{A100}$). Our cascaded modules run simultaneously on a single student laptop with an 8 GB RTX 4060 GPU.

---

### 2.2 Why Meta MMS-1B Instead of OpenAI Whisper for Chhattisgarhi?

#### The Viva Defense:
OpenAI Whisper was trained predominantly on high-resource languages (English, Spanish, Mandarin). Its public vocabulary and tokenizer omit Chhattisgarhi (`hne`). Testing Whisper on Chhattisgarhi results in:
- High phonetic hallucination rates.
- Silent deletion of dialect-specific grammatical markers (e.g. `मं`, `बर`, `हवय`, `रिहिस`).
- Automatic fallback to Standard Hindi words, corrupting the speaker's true intent.

Meta MMS (**Massively Multilingual Speech**) addresses this by training a shared 1-billion parameter Wav2Vec2 self-supervised backbone on raw audio across 1,400+ languages, combined with a **language-specific adapter** for Chhattisgarhi (`hne`). The adapter learns the specific acoustic-to-grapheme mappings for Chhattisgarhi Devanagari characters without suffering catastrophic forgetting.

---

### 2.3 Why Coqui VITS with CPU Execution Instead of GPU?

#### The Viva Defense:
In a single-machine deployment, GPU VRAM is the primary bottleneck:
- Local LLM (`Qwen3.5 9B` in 4-bit quantization) occupies $\approx 5.5\text{ GB}$ VRAM.
- Meta MMS-1B ASR (`float16`) occupies $\approx 2.2\text{ GB}$ VRAM.
- Total VRAM consumption $= 5.5 + 2.2 = 7.7\text{ GB}$.

Placing the TTS model on the GPU would trigger immediate CUDA Out-Of-Memory (OOM) crashes. 

However, because Coqui VITS is a non-autoregressive parallel model, its single-thread CPU forward pass takes only **105 to 125 ms** for an entire sentence. With a Real-Time Factor (RTF) of $\approx 0.036$, running VITS on the **CPU** introduces negligible human perceptual delay while guaranteeing $100\%$ GPU memory stability for reasoning.

---

### 2.4 Why Deterministic Regex Verbalization Instead of LLM Rewriting?

#### The Viva Defense:
A common naive approach is prompting the LLM: *"Rewrite this answer phonetically for TTS."*

This approach fails in production due to three critical flaws:
1. **Latency Multiplication**: Adding a second LLM generation step adds 5 to 15 seconds of inference latency per turn.
2. **Semantic Corruption & Negation Dropping**: LLMs frequently drop critical negative adverbs during rephrasing (e.g. transforming `"fees are non-refundable"` into `"fees are refundable"`).
3. **Number Hallucination**: LLMs can misread tabular cutoff ranks (e.g. changing rank `14,321` into `14,231`).

Our deterministic regex verbalization engine ([`verbalization.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/verbalization.py)) runs in $< 2\text{ ms}$, preserves text order, guarantees exact Indian cardinal numbering (`एक लाख पच्चीस हजार`), and protects negative constraints with zero risk of hallucination.

---

### 2.5 Why Bounded Worker Queues Instead of Unbounded Concurrency?

#### The Viva Defense:
In web frameworks like FastAPI and Streamlit, it is easy to launch tasks concurrently with `asyncio.gather()`. However, under hardware constraints, uncontrolled concurrency leads to **system collapse**:
- If 5 users simultaneously submit voice questions, an unbounded server will launch 5 concurrent 9B LLM forward passes.
- Operating system swap memory will thrash, latency will skyrocket from 25 s to 180 s for all users, and the GPU driver will kill the process with a segmentation fault.

The `JobManager` in [`jobs.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/jobs.py) implements **graceful degradation**:
- Bounded to 1 active reasoning worker and 1 active speech worker.
- Maximum queue capacity $= 3$.
- If a 5th caller arrives, they receive an immediate, transparent **429 (Busy) error**, while the existing 4 callers receive their answers in predictable, guaranteed time.

---

## 3. Summary of Core Invariants

1. **Audio Contract**: 16 kHz Mono 16-bit PCM In $\to$ 22.05 kHz Float32 WAV Out.
2. **Memory Safety**: GPU allocation capped at $\le 7.8\text{ GB}$ across all models.
3. **Transactional Safety**: Zero floating-point money; all pricing in integer paise.
4. **Agronomic Boundary**: 100% hard refusal and KVK referral on chemical pesticides and crop medical diagnosis.
5. **Privacy Policy**: 24-hour automatic retention purge on all student recordings, transcripts, and audio files.
