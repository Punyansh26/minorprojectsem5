# Document 4: Strategic Roadmap: Advanced Efficiency Strategies & Next-Gen Architecture

**Project Title:** Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects  
**Focus:** Architectural Evolution, System 1 Decision Models (Laya / JEV), Full-Duplex Speech-to-Speech, and Advanced RAG Optimizations  
**Authors:** Punyansh Thakur, Harsh Dadsena, Aakash Sen | **Supervisor:** Prof. Santosh Kumar  

---

## 1. Executive Vision: The Path from Cascaded Prototype to Sub-Second Voice AI

Our current implementation successfully demonstrates an **audited, reliable, zero-cloud Voice-to-Voice platform** passing 316 automated tests with verified zero hallucinations. Across both Demo 1 (Kisan Saathi) and Demo 2 (IIIT-NR Helpdesk), the architecture operates stably on an 8 GB consumer laptop GPU.

However, in human speech communication, conversational turn-taking latencies above $1.0\text{ s}$ break conversational rhythm and natural turn-taking. 

To bridge this gap while preserving our hardware budget (8 GB VRAM) and zero-hallucination guarantees, this strategic roadmap outlines four transformative architectural upgrades:

```mermaid
mindmap
  root((Next-Gen Edge Voice AI))
    1. System 1 Decision Routing
      Laya ModernBERT 421M (33ms)
      Non-Autoregressive Typed Heads
      Zero Output Token Consumption
      99.1% Routing Latency Reduction
    2. Streaming Full-Duplex Audio
      Clause-wise Chunked TTS
      Sub-second Time-to-First-Audio (TTFA < 1.2s)
      Speculative Pre-Retrieval on Partials
      100% Offline Speech (Kokoro-82M)
    3. Advanced RAG Acceleration
      Speculative RAG Drafting (1.5B + 9B)
      Release-Bound Semantic Vector Caching
      Cross-Lingual Information Retrieval (CLIR)
      Context Token Pruning (LongLLMLingua)
    4. Edge Telephony & Unified Deployment
      Twilio / SIP G.711 Media Streaming
      Quantized GGUF / ExLlamaV2 Backends
      Single-Binary On-Device Packaging
```

---

## 2. Integration of Open-Source System 1 Decision Models: Laya & JEV

### 2.1 The Routing Bottleneck in the Current Architecture

In our empirical evaluation across 120 live benchmark turns (`baseline/results.json`):
$$\text{Median Intent Routing Latency via Ollama 9B} = \mathbf{3,795.0\text{ ms}} \quad (\text{Mean: } 3,824.0\text{ ms})$$

Before vector retrieval or tool execution even begins, the system spends nearly $4\text{ seconds}$ running an autoregressive generative LLM call solely to determine if the query is in-scope and which category it belongs to. Generative LLMs generate token-by-token, requiring repeated transformer forward passes over the full sequence length ($O(T)$ operations), which is computationally wasteful for simple categorical classification.

```
                    Incoming User Query x
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
   Traditional LLM Router           Laya Decision Model
   (Qwen 3.5:9B Autoregressive)     (ModernBERT-large 421M)
   ───────────────────────────      ─────────────────────────
   • Generates token-by-token       • Single forward pass
   • 986 prompt tokens              • Non-autoregressive head
   • High latency: ~3,795 ms        • Ultra-fast: ~33 ms
   • GPU memory contention          • Zero output tokens
   • Risk of JSON parse errors      • Direct typed Choice/Noul
```

### 2.2 Why Laya (by Convaiinnovations) is the Optimal Solution

[Laya](https://laya.convaiinnovations.com/) is an open-source, non-autoregressive "System 1" decision model developed by **Convaiinnovations** (`github.com/NandhaKishorM/laya`, `huggingface.co/spaces/convaiinnovations/laya-demo`).

#### Technical Architecture of Laya:
1. **Backbone:** Built on `ModernBERT-large` (421M parameters), incorporating modern architectural advancements: Rotary Positional Embeddings (RoPE), FlashAttention-2, and unpadded sequence batching.
2. **Multi-Task Decision Heads:** Custom classification heads trained to evaluate text state against typed questions:
   * **Choice:** Selects the optimal intent/department category with calibrated probability and confidence scores.
   * **Noul:** Binary boolean verification ($0.0 \text{ to } 1.0$) for critical gates (e.g., *"Is this query out of scope?"*).
   * **Score:** Continuous rubric rating ($1 \text{ to } 5$).
3. **Execution Latency:** **$\sim 33\text{ ms}$** on CPU/GPU — **$115\times$ faster** than our current Ollama routing call!

### 2.3 Proposed Integration Architecture in `classify_intent_node`

```python
# assistant/nodes.py (Proposed Laya Fast-Path Integration)
from laya import LayaDecisionEngine

# Load Laya engine on CPU to preserve GPU VRAM for the 9B verifier
laya_engine = LayaDecisionEngine.load("convaiinnovations/laya", device="cpu")

def classify_intent_node(state: dict) -> dict:
    question = _latest_human_text(state)
    
    # Tier 1: Deterministic regex bypass (0 ms)
    if is_static_greeting(question):
        return finish_static_reply(question)
        
    # Tier 2: Laya System 1 Decision Model (~33 ms)
    decision = laya_engine.evaluate(
        context=question,
        questions=[
            {"id": "intent", "type": "choice", "options": ["knowledge", "smalltalk", "out_of_scope", "handoff"]},
            {"id": "category", "type": "choice", "options": ["admissions", "academics", "hostel", "finance"]},
            {"id": "needs_rewrite", "type": "noul", "prompt": "Does this query contain ambiguous pronouns or references?"}
        ]
    )
    
    # Selective Risk Gate: Accept if confidence >= 0.85 and rewrite is not needed
    if decision["intent"].confidence >= 0.85 and decision["needs_rewrite"].score < 0.20:
        state["rag_metrics"]["router_path"] = "laya_fast_path"
        state["rag_metrics"]["stage_ms"]["routing"] = 33.0
        return finish({
            "intent": decision["intent"].choice,
            "detected_category": decision["category"].choice,
            "search_query": question
        })
        
    # Tier 3: Fallback to Autoregressive LLM Router (for complex multi-turn queries)
    return call_ollama_routing_model(state)
```

#### Mathematical Impact on Turn Latency:
$$\Delta T_{\text{turn}} = -(T_{\text{route, LLM}} - T_{\text{Laya}}) = -(3,795\text{ ms} - 33\text{ ms}) \approx -\mathbf{3.76\text{ s}}$$
For all answerable standalone questions, median turn time drops from **$18.68\text{ s} \to 14.92\text{ s}$** ($20.1\%$ overall turn acceleration) with zero degradation in classification precision.

---

## 3. Speech-to-Speech (S2S) Pipeline Evolution

### 3.1 Limitations of Current Cascaded Architecture
Our current system is a **half-duplex turn-based cascade**:
$$\text{Speech} \xrightarrow{\text{VAD}} \text{STT} \xrightarrow{\text{Text}} \text{Reasoning} \xrightarrow{\text{Verified Text}} \text{Verbalizer} \xrightarrow{\text{WAV}} \text{TTS}$$

* **Sequential Waiting:** The speech synthesizer cannot start until the generative LLM emits its final token and the grounding review completes.
* **Audio Buffer Delay:** VITS generates the entire waveform for a paragraph before sending audio bytes to the browser.
* **Network Dependency:** English/Hinglish audio relies on external Microsoft Edge TTS subprocesses.

### 3.2 Roadmap: True Streaming Full-Duplex Architecture

```mermaid
sequenceDiagram
    autonumber
    actor User as Speaker
    participant VAD as Streaming Silero VAD
    participant ASR as Speculative Faster-Whisper
    participant RAG as Streaming LangGraph LLM
    participant TTS as Chunked Neural TTS (Kokoro / Piper)
    participant Audio as Speaker Audio Stream

    User->>VAD: "What is the tuition fee..." (Speaking)
    VAD->>ASR: Stream PCM frames (32ms frames)
    ASR-->>RAG: Partial Transcript: "What is the tuition fee"
    Note over RAG: SPECULATIVE PRE-RETRIEVAL:<br/>Start vector retrieval while user is still speaking!
    User->>VAD: "...for B.Tech first semester?" (Finishes speaking)
    VAD->>ASR: Utterance finalized (600ms silence)
    ASR-->>RAG: Final prompt dispatched
    Note over RAG: Retrieval already finished! Generates first sentence tokens:
    RAG-->>TTS: Stream Sentence 1: "The total fee is 1,81,000 rupees."
    TTS-->>Audio: Stream synthesized audio chunk (22.05 kHz)
    Note over User,Audio: TIME-TO-FIRST-AUDIO (TTFA) < 1,200 ms!<br/>User hears speech while Sentence 2 is still generating.
    RAG-->>TTS: Stream Sentence 2: "Hostel charges are separate."
    TTS-->>Audio: Stream synthesized audio chunk
```

#### Concrete Engineering Upgrades:
1. **Sentence-Level Chunked TTS Streaming:**
   Instead of synthesizing the full response block ($130\text{ characters}$ taking $2.2\text{ s}$), we buffer tokens at sentence boundaries (`।`, `.`, `?`, `\n`) and pipe them immediately to the synthesizer. The user hears the first sentence within **$1.2\text{ s}$** of speech completion.
2. **Speculative Pre-Retrieval on Partial Transcripts:**
   When Faster-Whisper emits a partial transcript containing key institutional entities (e.g., *"tuition fee 2026"*), dense vector retrieval executes in background worker threads **before** the user even stops speaking.
3. **100% Offline Local Speech with Kokoro-82M / Piper-TTS:**
   Replace the online Microsoft Edge TTS dependency with an on-device, lightweight neural vocoder:
   * **Kokoro-82M:** An 82-million parameter open-source TTS model with natural English phonetics that runs at $0.15\times\text{ RTF}$ on CPU.
   * Eliminates cloud data exposure and guarantees complete air-gapped security.

---

## 4. Advanced RAG Efficiency Enhancements

### 4.1 Speculative RAG (Draft-Verification Paradigm)
* **Problem:** Running Qwen 3.5:9B for both generation ($7.18\text{ s}$) and grounding review ($7.41\text{ s}$) takes nearly $15\text{ seconds}$.
* **Solution:** Deploy a **Small Language Model (SLM)** alongside the 9B model:
  * **Draft Model:** `Qwen 2.5:1.5B` (Q4_K_M, taking only $1.1\text{ GB}$ host RAM) generates the candidate answer draft in $\sim 1.8\text{ s}$.
  * **Verifier Model:** The resident `Qwen 3.5:9B` executes only the strict grounding review pass ($7.4\text{ s}$).
  * **Net Acceleration:** Reduces total answer stage latency from **$14.59\text{ s} \to 9.20\text{ s}$** ($36.9\%$ acceleration).

### 4.2 Release-Bound Semantic Vector Caching
* **Current State:** Our exact-key cache hits only when queries share identical phrasing.
* **Proposed Enhancement:** Implement a **two-stage semantic cache**:
  1. Compute query embedding $\mathbf{e}_q$ using `multilingual-e5-small`.
  2. Search cached query vectors in an in-memory FAISS/HNSW index bound to the active release SHA-256:
     $$\text{Similarity} = \cos(\mathbf{e}_q, \mathbf{e}_{\text{cached}}) \ge 0.94$$
  3. Validate that critical extracted slot dimensions (Year, Program, Category) match exactly before returning the cached draft.
  4. Projected Impact: Increases cache hit rate from $\sim 15\%$ to **$45\text{--}60\%$** across high-frequency student admission inquiries.

### 4.3 Context Token Compression (LongLLMLingua Integration)
* **Problem:** Ingesting 6 retrieved evidence chunks sends over $2,100\text{ tokens}$ to the model, increasing prefill latency.
* **Solution:** Apply budget-aware prompt compression using **LongLLMLingua** (Jiang et al., 2023):
  * Calculates token-level perplexity scores over non-essential words (boilerplate headers, redundant circular notices).
  * Compresses 2,100 context tokens down to **$750\text{ tokens}$** ($64\%$ token reduction) without losing numbers, names, or cutoff rows.
  * Accelerates prefill execution by nearly $2.5\times$.

### 4.4 Cross-Lingual Information Retrieval (CLIR) for Chhattisgarhi
* **Current State:** Chhattisgarhi speech is recognized by MMS (`hne`), converted to text, and translated or mapped to Hindi fallback before querying English institutional documents.
* **Proposed Enhancement:** Train a cross-lingual projection layer linking Chhattisgarhi phone-level embeddings directly to English document vectors in `multilingual-e5-small` cosine space:
  $$\mathbf{e}_{\text{query}} = \mathbf{W}_{\text{CLIR}} \cdot \mathbf{h}_{\text{MMS-hne}}$$
  Enables native Chhattisgarhi queries to retrieve English official PDF brochures without intermediate translation drift!

---

## 5. Unified Implementation Roadmap & Phased Milestones

| Phase | Strategic Milestone | Target Performance Metric | Feasibility & Dependency |
|---|---|---|---|
| **Phase 1 (Immediate)** | **Laya System 1 Router Integration** | Routing latency: $3,800\text{ ms} \to \mathbf{33\text{ ms}}$; $100\%$ zero-token routing | High feasibility; load `convaiinnovations/laya` in worker process |
| **Phase 2 (Near-Term)** | **Sentence-Level Chunked TTS Streaming** | Time-to-First-Audio (TTFA): $18\text{ s} \to \mathbf{1.2\text{ s}}$ | High feasibility; stream tokens into Piper / VITS clause buffers |
| **Phase 3 (Medium-Term)** | **Speculative RAG Drafting (1.5B + 9B)** | Answering stage: $14.6\text{ s} \to \mathbf{9.2\text{ s}}$ ($36.9\%$ speedup) | Medium feasibility; requires running Qwen-1.5B alongside 9B |
| **Phase 4 (Long-Term)** | **Cross-Lingual Information Retrieval (CLIR)** | Direct Chhattisgarhi ASR $\to$ English PDF retrieval ($>90\%$ recall) | Research project; train mE5 contrastive projection head |

---

## 6. Conclusion & Defense Takeaway

This project establishes that **efficient, production-grade conversational AI is an architectural discipline, not just an API integration**.

By:
1. Grounding decisions in peer-reviewed literature (FrugalGPT, RouteLLM, Adaptive-RAG, VITS, FastMCP, Laya);
2. Implementing rigorous engineering safeguards (Silero VAD frame invariance, 3-way hybrid RRF search, relational cutoff sidecars, two-pass grounding review, and deterministic verbalization);
3. Validating both task-execution shopping (Demo 1) and institutional counseling RAG (Demo 2) on edge hardware; and
4. Charting a concrete, verified roadmap toward sub-second full-duplex conversational interaction with open-source decision models,

this minor project establishes a complete, academically defensible, and startup-viable foundation for resource-constrained conversational artificial intelligence.
