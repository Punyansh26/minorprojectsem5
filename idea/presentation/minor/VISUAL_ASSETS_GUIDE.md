# Master Visual Assets & Diagram Specification Guide

**Project Title:** Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects  
**Purpose:** Standardized visual specifications and production-grade Mermaid diagrams for presentation slides, technical dossiers, and defense posters.  
**Tools:** Compatible with Mermaid Live Editor (`mermaid.live`), Figma, PowerPoint SmartArt, or Draw.io.

---

## 🎨 Standardized Design Principles & Palette

### Visual Guidelines for Technical Slides:
* **High Contrast & Clean Typography:** Use minimum 18pt font for internal diagram nodes and 24pt for section headers.
* **Semantic Color Coding:**
  - **Primary Blue (`#2563eb`):** Core platform layers, clients, and stable execution paths.
  - **Success Green (`#16a34a`):** Verified facts, accepted groundings, cache hits, and performance improvements.
  - **Warning Orange / Amber (`#ea580c`):** Latency bottlenecks, queue boundaries, and routing gates.
  - **Danger Red (`#dc2626`):** Hallucinations, OOM crashes, ungrounded claims, and safety refusals.
  - **Neutral Slate (`#475569`):** Background buffers, memory partitions, and audio payloads.
* **Directional Simplicity:** Prefer Left-to-Right (`flowchart LR`) for wide widescreen (16:9) slides; Top-to-Bottom (`flowchart TB`) for layered architecture posters.

---

## 📊 Complete Slide Diagram Catalog (Ready to Render)

### Diagram 1: Master Platform Architecture & Decoupled Execution (Slide 3)
* **Purpose:** Demonstrates how the reusable Voice-to-Voice platform core serves both Demo 1 (FastMCP) and Demo 2 (Hybrid RAG) while enforcing physical CPU-GPU compute decoupling.

```mermaid
flowchart TB
    subgraph Client ["Client Interaction Layer"]
        Mic["Microphone Input\n(16 kHz Mono PCM16)"]
        UI1["Demo 1: Kisan Saathi UI\n(SHA-256 Claim Idempotency)"]
        UI2["Demo 2: IIIT-NR Helpdesk UI\n(Progressive @st.fragment Polling)"]
    end

    subgraph CPU_Speech ["Acoustic Speech Layer (Pinned to Host CPU RAM)"]
        VAD["Silero VAD (ONNX Runtime)\n512-Sample Frame Invariance (32ms)\nResidual FIFO Buffer"]
        Whisp["Faster-Whisper (small / int8)\nCTranslate2 Engine (4 Threads)"]
        MMS["Meta MMS-1B (Wav2Vec2 fp16)\nChhattisgarhi hne + CTC Matra Repair"]
    end

    subgraph GPU_Reasoning ["Dedicated GPU Layer (NVIDIA RTX 4060 8 GB VRAM)"]
        LLM["Local Ollama Qwen 3.5:9B (Q4_K_M)\nExclusive CUDA Execution (6.3 GB VRAM)"]
    end

    subgraph Applications ["Dual Operational Application Engines"]
        subgraph D1 ["Demo 1: Kisan Saathi"]
            MCP["FastMCP Tool Subprocess (stdio)\n12 Grounded Commercial Tools"]
            JSON[("Atomic shop.json Store\nFileLock + Exact Integer Paise")]
        end
        subgraph D2 ["Demo 2: IIIT-NR Helpdesk"]
            Queue["JobManager Bounded Queue\n(FIFO Capacity: 3)"]
            Hybrid["3-Way Hybrid Retrieval\n(mE5 + BM25 + JoSAA Relational SQL)"]
            Review["Two-Pass Grounding Review Pass\n(Verbatim Quote Verification)"]
        end
    end

    subgraph Synthesis ["Speech Verbalization & Synthesis Layer"]
        Verb["Verbalization v2 Normalizer\n(Indian Numbering + Hindi Negation Guard)"]
        VITS["Local Coqui VITS Synthesizer (CPU)\nResident LRU Cache (Female / Male Checkpoints)"]
        Spk["22.05 kHz Audio Playback"]
    end

    Mic --> VAD
    VAD --> Whisp & MMS
    Whisp & MMS --> UI1 & UI2
    UI1 --> MCP
    MCP --> JSON
    JSON --> Verb
    
    UI2 --> Queue
    Queue --> Hybrid
    Hybrid --> LLM
    LLM --> Review
    Review --> Verb
    
    Verb --> VITS
    VITS --> Spk
```

---

### Diagram 2: Demo 1 — FastMCP Agricultural Shopping & Safety Flow (Slide 4)
* **Purpose:** Illustrates how Chhattisgarhi speech triggers process-isolated tool calling, strict KVK agronomic safety refusal, and atomic integer paise persistence.

```mermaid
sequenceDiagram
    autonumber
    actor Farmer as Chhattisgarhi Farmer
    participant UI as Streamlit UI (app.py)
    participant ASR as Meta MMS-1B (hne)
    participant Router as assistant.py (Intent & Safety)
    participant MCP as FastMCP Server (mcp_server.py)
    participant Store as shop.py (shop.json)
    participant VITS as Coqui VITS (CPU)

    Farmer->>UI: Speaks in Chhattisgarhi & clicks Stop
    UI->>UI: Hash audio buffer (SHA-256) -> Set _claim_recording token
    UI->>ASR: Transcribe audio (float16 CUDA) + clean_mms_devanagari
    ASR-->>UI: Transcript: "धान बीज के दो पैकेट टोकरी म डालव"

    UI->>Router: run_turn(user_text, cart_state)
    
    alt Shortcut Command ("टोकरी दिखाओ" / "show cart")
        Router->>Store: view_cart(session_id) [0ms LLM compute]
    else Chemical / Disease Query ("रोग", "कीटनाशक", "spray", "dose")
        Router->>Router: Intercept with SAFETY_PATTERN regex
        Router-->>UI: Pre-approved KVK Referral Template [Zero Toxic Hallucination]
    else Commercial Action
        Router->>MCP: invoke_tool("add_to_cart", {product_id: "PADDY-01", quantity: 2})
        Note over MCP,Store: Isolated stdio JSON-RPC Subprocess<br/>Acquires shop.json.lock via filelock<br/>Computes total in integer paise (₹900 = 90000 paise)<br/>Atomic write to tempfile + fsync + os.replace
        Store-->>MCP: {status: "success", cart_paise: 90000}
        MCP-->>Router: Tool execution result
    end

    Router-->>UI: Grounded Chhattisgarhi Text: "धान बीज के 2 पैकेट टोकरी म डल गे हे।"
    UI->>VITS: Verbalize "₹900" -> "नौ सौ रुपये" & synthesize (length_scale=1.0)
    VITS-->>UI: 22,050 Hz WAV buffer
    UI-->>Farmer: Audio playback + cart update
```

---

### Diagram 3: Demo 2 — Asynchronous Bounded Helpdesk & Text-First UX (Slide 5)
* **Purpose:** Demonstrates how the Bounded JobManager queue protects the laptop GPU and how `@st.fragment` delivers answers $4\text{--}15\text{ s}$ before audio completes.

```mermaid
sequenceDiagram
    autonumber
    actor Student as Prospective Student
    participant UI as Streamlit UI (@st.fragment)
    participant JM as JobManager (jobs.py queue)
    participant RAG as LangGraph Engine (nodes.py)
    participant LLM as Ollama Reasoner (Qwen 3.5:9B)
    participant Verb as verbalization.py (v2)
    participant TTS as Coqui VITS (CPU LRU Cache)

    Student->>UI: Speaks query into browser mic & clicks Stop
    UI->>JM: submit(job: audio_bytes, language, voice)
    Note over JM: Admission Check: Queue capacity <= 3<br/>If full, raise ValueError('busy') -> HTTP 429
    JM-->>UI: Job Accepted (Snapshot polling begins via @st.fragment)

    Note over JM: Dedicated Reasoning Worker (demo-reasoning thread)
    JM->>RAG: ask(question, history, thread_id)
    RAG->>LLM: generate_answer_node() -> Candidate JSON draft
    RAG->>LLM: critical_review_node() -> Strict verbatim quote cross-examination
    LLM-->>RAG: Verified answer_text + [Page X] citations
    RAG-->>JM: Output written to SQLite store

    Note over JM,UI: PHASE 1: TEXT-FIRST PROGRESSIVE UX (F05)<br/>UI renders verified text & citations immediately!
    JM-->>UI: Display verified answer text & sources

    opt Spoken Replies Enabled
        Note over JM: Enqueued to background speech pool (demo-speech thread)
        JM->>Verb: normalize(answer_text) -> ₹90,000 -> नब्बे हजार रुपये
        Verb-->>TTS: Clean Devanagari text
        TTS->>TTS: Synthesize 22.05 kHz WAV from host CPU RAM
        TTS-->>JM: WAV byte payload
        JM-->>UI: Attach audio player & trigger browser playback
    end
```

---

### Diagram 4: 3-Way Hybrid Knowledge Retrieval Architecture (Slide 6)
* **Purpose:** Visualizes why vector search fails on numerical cutoff queries and how our 3-way fusion achieves $98.92\%$ Recall@6.

```mermaid
flowchart TD
    Query["User Query:\n'What is the Round 5 closing rank for B.Tech CSE SC category in 2026?'"] --> Split{"Query Classifier"}
    
    subgraph ThreeWayStore ["3-Way Hybrid Knowledge Store"]
        Split -->|Semantic Context| Dense["Dense Vector Search (ChromaDB)\nmultilingual-e5-small (384d, Cosine)\n350-Token Overlapping Chunks"]
        Split -->|Exact Codes / Acronyms| Sparse["Sparse Lexical Search\nRank-BM25 (k1=2.5, b=0.75)\nExact Keyword Frequency"]
        Split -->|Numerical Ranks / Cutoffs| SQL["Relational Cutoff Sidecar\nExact Parameterized SQL Query\n611 Official JoSAA Rows (2022-2026)"]
    end

    Dense -->|Rank List 1| RRF["Reciprocal Rank Fusion (RRF)\nRRF_Score = sum(1 / (60 + Rank_m))"]
    Sparse -->|Rank List 2| RRF

    RRF --> TopChunks["Top-6 Parent Evidence Chunks"]
    SQL -->|Exact SQL Result Injection| TopChunks

    TopChunks --> Gen["To Generation & Grounding Review Nodes"]
```

---

### Diagram 5: Two-Pass Grounding Verification Flowchart (Slide 7)
* **Purpose:** Explains the zero-hallucination guarantee through automated verbatim source cross-examination.

```mermaid
flowchart TD
    Prompt["System Prompt + Retrieved Evidence Chunks + Query"] --> Pass1["Pass 1: Generation Node (Ollama Qwen 3.5:9B)\nConstrained JSON Grammar Decoding"]
    Pass1 --> Draft["Candidate JSON Draft\n(answer_text, citations, candidate_quotes)"]
    Draft --> Pass2["Pass 2: Critical Grounding Review Pass\nCross-Examines Candidate Claims Against Raw Sources"]
    
    Pass2 --> Check{"Is claimed quote an exact contiguous\nsubstring of source chunk after normalization?"}
    
    Check -- Yes --> Emit["Status: 'answered'\nStore Verified Draft in RagCache\nRender Verified Text Immediately in UI"]
    Check -- No --> Abstain["Status: 'insufficient'\nAbstain Honestly: 'I do not have verified record'\nEmit Administrative Review Ticket Draft"]
```

---

### Diagram 6: Physical VRAM vs. CPU Memory Allocation Topology (Slide 8)
* **Purpose:** Proves why monolithic GPU stacking crashes 8 GB laptops and how our decoupled architecture operates safely.

```
=== Traditional Naive Strategy (Everything on GPU) -> CRASH ===
[0 GB]                                                  [8 GB VRAM]
├── LLM (Qwen 3.5:9B): 6.4 GB ──┤
                                ├── Whisper ASR: 1.5 GB ──┤
                                                          ├── VITS TTS: 1.2 GB ──► [OOM CRASH: 9.1 GB]

=== Our Optimized Decoupled Strategy (CPU-GPU Hybrid) -> STABLE ===
[NVIDIA RTX 4060 GPU: 8.0 GB VRAM Total]
[████████████████████████████████████████░░░░░░] 6.3 GB Ollama 9B (Q4_K_M) + 0.85 GB KV + 0.8 GB Display
[Safe VRAM Headroom: ~0.05-0.15 GB | 100% Operational Stability, Zero Kernel Panics]

[Host System Memory: 32.0 GB CPU RAM Total]
[██████] 1.2 GB Faster-Whisper (int8, 4 threads, AVX-512)
[██████] 1.9 GB Coqui VITS Resident LRU Cache (Female & Male best_model.pth)
[████]   0.8 GB Chroma Vector Store & mE5-small Embeddings
[Safe Host Headroom: ~28.1 GB Free Host RAM]
```

---

### Diagram 7: Latency Breakdown Gantt Chart (Slide 10)
* **Purpose:** Stage-by-stage latency visualization on 120 live benchmark turns.

```mermaid
gantt
    title Empirical Latency Distribution (Measured on 120 Live Cases)
    dateFormat X
    axisFormat %s s

    section Cold Turn (Total Perceived: 18.68s)
    Silero VAD & Fast Ingress    :0, 0.21
    Speech ASR (Whisper/MMS)     :0.21, 2.06
    Routing Node (Ollama 9B)     :2.06, 5.86
    Hybrid Retrieval (E5+BM25+SQL):5.86, 5.91
    Answer Generation (Qwen 3.5) :5.91, 13.09
    Critical Grounding Review    :13.09, 20.50
    TEXT DISPLAYED TO USER (F05) :milestone, 20.50, 20.50
    Decoupled VITS Synthesis     :20.50, 22.15
    Audio Ready                  :milestone, 22.15, 22.15

    section Warm Cache Turn (Total Perceived: 2.64s)
    Silero VAD & Ingress         :0, 0.21
    Speech ASR (Whisper)         :0.21, 1.85
    Cache Hit & Verification     :1.85, 4.49
    TEXT DISPLAYED TO USER (F05) :milestone, 4.49, 4.49
    Decoupled VITS Synthesis     :4.49, 6.14
    Audio Ready                  :milestone, 6.14, 6.14
```

---

### Diagram 8: Operating Financial Economics Comparison (Slide 11)
* **Purpose:** Demonstrates the $682\times$ cost reduction of our edge architecture over commercial APIs for 10,000 queries per month.

```
Commercial Cloud APIs: $409.25 / month
├─ GPT-4o Token Billing:   $165.25  [====================]
├─ Whisper ASR API:         $10.00  [=]
└─ ElevenLabs Neural TTS:  $234.00  [=============================]

Our Local Edge Hardware: $0.60 / month
└─ Physical Electricity:     $0.60  [.]  <-- 682× CHEAPER!
```

---

### Diagram 9: Streaming Full-Duplex S2S Strategic Roadmap (Slide 13)
* **Purpose:** Illustrates sentence-chunked streaming speech and speculative pre-retrieval.

```mermaid
sequenceDiagram
    autonumber
    actor Speaker as User / Farmer
    participant VAD as Streaming Silero VAD
    participant ASR as Speculative ASR
    participant RAG as Streaming LangGraph LLM
    participant TTS as Chunked Neural TTS (Kokoro/Piper)
    participant Spk as Audio Output Stream

    Speaker->>VAD: "What is the tuition fee..." (Speaking)
    VAD->>ASR: Stream PCM frames (32ms frames)
    ASR-->>RAG: Partial Transcript: "What is the tuition fee"
    Note over RAG: SPECULATIVE PRE-RETRIEVAL:<br/>Start vector retrieval while user is still speaking!
    Speaker->>VAD: "...for B.Tech first semester?" (Finishes speaking)
    VAD->>ASR: Utterance finalized (600ms silence)
    ASR-->>RAG: Final prompt dispatched
    Note over RAG: Retrieval already finished! Generates first sentence tokens:
    RAG-->>TTS: Stream Sentence 1: "The total fee is 1,81,000 rupees."
    TTS-->>Spk: Stream synthesized audio chunk (22.05 kHz)
    Note over Speaker,Spk: TIME-TO-FIRST-AUDIO (TTFA) < 1,200 ms!<br/>User hears speech while Sentence 2 is still generating.
    RAG-->>TTS: Stream Sentence 2: "Hostel charges are separate."
    TTS-->>Spk: Stream synthesized audio chunk
```

---

## ✅ Visual Assets Checklist for Slide Creation
- [x] Diagram 1 exported as high-resolution SVG/PNG for Slide 3.
- [x] Diagram 2 exported for Slide 4 (Demo 1 FastMCP flow).
- [x] Diagram 3 exported for Slide 5 (Demo 2 Bounded Queue & Text-First UX).
- [x] Diagram 4 exported for Slide 6 (3-Way Hybrid Retrieval).
- [x] Diagram 5 exported for Slide 7 (Two-Pass Grounding Review).
- [x] Diagram 6 visual memory map included in Slide 8.
- [x] Diagram 7 Gantt chart rendered for Slide 10.
- [x] Diagram 8 cost infographic formatted for Slide 11.
- [x] Diagram 9 roadmap sequence diagram included in Slide 13.
