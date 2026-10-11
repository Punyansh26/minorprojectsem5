# Master Slide-by-Slide Revision Blueprint & Speaker Script
**Presentation:** `Progress PPT.ppt (3).pptx`  
**Target:** 5th Semester Minor Project Evaluation (AI-301) | IIIT Naya Raipur  
**Project:** Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects  

---

## Slide 1: Title Slide

### 1. Current State & Identified Flaws
- **Shapes Present:**
  - `TextBox 8`: Contains `..` (stray typo in top-left).
  - Main Title: *"Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects"*
  - Subtitle: *"B.Tech in Artificial Intelligence & Data Science, Semester 5 / 3rd Year | Minor Project, AI-301, 4 Credits"*
  - Date: `5 October 2026`
  - Team: Punyansh Thakur, Harsh Dadsena, Aakash Sen
  - Supervisor: Prof. Santosh Kumar
- **Flaws:**
  - Stray text box `..` in top left is visually amateurish.
  - No slide subtitle clarifying the real-world applications (Kisan Saathi & IIIT-NR Helpdesk).

### 2. Exact Changes to Make
- **Delete:** The text box containing `..`.
- **Add Subtitle / Tagline:** Under the main title, add a high-impact tag:
  > *"Zero-Cloud Speech Ingestion, Bounded Tool Execution & Strictly Grounded Multi-Turn RAG on Consumer Edge Hardware"*

### 3. Verbatim Content Layout
```
[ TOP LEFT LOGO: IIIT Naya Raipur Seal ]

                       ARCHITECTURE OF AN EDGE-OPTIMIZED,
                      LOW-LATENCY VOICE-TO-VOICE AGENT
                   FOR LOW-RESOURCE VERNACULAR DIALECTS

     A Zero-Cloud Framework for Agronomic Commerce (Kisan Saathi)
             & Grounded Institutional Helpdesk (IIIT-NR)

   Students: Punyansh Thakur | Harsh Dadsena | Aakash Sen
   Supervisor: Prof. Santosh Kumar
   B.Tech Artificial Intelligence & Data Science (Semester 5) | AI-301 Minor Project
   Date: 06 October 2026
```

### 4. Speaker Script (Slide 1)
> *"Respected guide Prof. Santosh Kumar and members of the evaluation committee, good morning. Today, my teammates Harsh, Aakash, and I are presenting our 5th-semester Minor Project: 'Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects'. In this work, we address the critical challenge of enabling private, reliable, zero-cloud voice AI that operates within consumer GPU limits, specifically validated across regional Chhattisgarhi, Hindi, and English."*

---

## Slide 2: 01 Introduction

### 1. Current State & Identified Flaws
- **Footer Bug:** Bottom-right displays unparsed template tag `<number>` instead of `2`.
- **Typo:** *"Runs On a single machine"* has a random capital "O".
- **Visual Weakness:** Bottom diagram has three generic boxes (`Input -> Edge Processing -> Verified Output`) that look like high-school placeholders.

### 2. Exact Changes to Make
- **Fix Footer:** Replace `<number>` with `2`.
- **Fix Typo:** Change `"Runs On"` to `"Runs on a single consumer machine (RTX 4060 8 GB / 32 GB RAM)"`.
- **Replace Bottom Diagram:** Replace the 3 trivial boxes with a **Dual-Application Validation Anchor**:

### 3. Verbatim Content Layout
* **Header:** `01  Introduction`
* **Column 1: Architectural Paradigm (Project Focus)**
  * **Edge-Native Zero-Cloud Core:** Eliminates recurring cloud API costs ($400+/mo) and preserves privacy by executing speech recognition, reasoning, and synthesis locally.
  * **Low-Resource Vernacular Support:** Custom pipeline for regional Chhattisgarhi (`hne`), code-mixed Hinglish, Hindi, and English.
  * **Strict Resource Budget:** Runs reliably within an 8 GB consumer GPU footprint (7.95 GB active VRAM) without out-of-memory crashes.
* **Column 2: Domain Validations (Application Heads)**
  * **Demo 1 — Kisan Saathi (Agronomic Commerce):**
    * Voice shopping for agricultural inputs.
    * 12 sandboxed FastMCP tools with strict KVK agronomic safety boundaries to prevent crop damage.
  * **Demo 2 — IIIT-NR Voice Helpdesk (Institutional RAG):**
    * Multi-turn admissions, fee schedule, and policy assistant.
    * Compiled LangGraph StateGraph with 3-way hybrid retrieval and two-pass citation verification.
* **Bottom Highlight Banner:**
  > **Core Philosophy:** Local Speech Processing + Bounded Tool Execution + Zero-Hallucination Grounded Reasoning.

### 4. Speaker Script (Slide 2)
> *"Most voice assistants today assume high-speed internet, cloud GPUs, and dominant languages like English. In rural and regional contexts, this model breaks down. Our project solves this by delivering an edge-native, zero-cloud voice agent running on standard consumer hardware. Rather than treating this as a generic chatbot, we validate our architecture across two demanding real-world domains: first, 'Kisan Saathi', which handles agricultural shopping for Chhattisgarhi farmers with strict safety guardrails; and second, the 'IIIT-NR Voice Helpdesk', which answers admissions and policy queries with zero-hallucination citation grounding."*

---

## Slide 3: 02 Motivation: Issues and Challenges

### 1. Current State & Identified Flaws
- **Footer Bug:** Bottom-right displays raw `<number>` instead of `3`.
- **Content:** Has 5 boxes (Vernacular coverage, Cloud dependence, Numerical factuality, Edge constraints, Sequential latency).
- **Flaw:** Content is good, but doesn't explain *why standard off-the-shelf solutions fail*.

### 2. Exact Changes to Make
- **Fix Footer:** Replace `<number>` with `3`.
- **Refine the 5 Cards:** Turn them into a clear **Problem vs Engineering Reality** format.

### 3. Verbatim Content Layout
* **Header:** `02  Motivation: Issues and Challenges`
* **Card 1: Low-Resource Dialect Gap (Vernacular Coverage)**
  * *Challenge:* Mainstream ASR (Whisper, Google Speech) deteriorates on regional Chhattisgarhi (`hne`), and CTC decoders drop Devanagari vowel matras.
* **Card 2: Cloud Fragility & Economics (Cloud Dependence)**
  * *Challenge:* Off-device cloud APIs require constant internet, compromise institutional privacy, and cost ~$409/month for 10,000 voice turns.
* **Card 3: The Dense-Vector "Hallucination Trap" (Numerical Factuality)**
  * *Challenge:* Semantic vector embeddings confuse numerical ranks, seat categories (SC vs ST), and quota cutoffs because embeddings measure semantic similarity, not tabular logic.
* **Card 4: Strict Hardware Boundaries (Edge Constraints)**
  * *Challenge:* Running ASR, a 9B reasoning model, and neural TTS concurrently exceeds 8 GB GPU VRAM (naive stacking crashes at 9.1 GB).
* **Card 5: Multi-Model Latency Compounding (Sequential Latency)**
  * *Challenge:* Chaining ASR + Intent Routing + Generation + Verification serially creates a ~18s turn delay, requiring decoupled text-first delivery.
* **Bottom Takeaway:**
  > *"Target: A fully private, locally executable agent that bridges low-resource vernacular speech with verifiable deterministic facts under consumer hardware limits."*

### 4. Speaker Script (Slide 3)
> *"Why is this problem technically challenging? First, dialect coverage: standard models fail on Chhattisgarhi, often detaching Devanagari matras during CTC decoding. Second, cloud dependence is expensive and fragile in rural areas. Third, and most crucially, dense vector retrieval alone is disastrous for institutional questions—an embedding cannot differentiate between Round 4 and Round 5 cutoff ranks because their text embeddings are 98% similar! Finally, on consumer hardware with only 8 GB of VRAM, naive model loading crashes the GPU at 9.1 GB. These engineering bottlenecks motivated our decoupled, verifiable architecture."*

---

## Slide 4: 03 Literature Review

### 1. Current State & Identified Flaws
- **Footer Bug:** Bottom-right displays page number `5` instead of `4`.
- **Content:** Good comparative table covering VITS, Whisper, FrugalGPT, Meta MMS, Adaptive-RAG, RouteLLM, and FastMCP.
- **Flaw:** The table lists works and limitations, but doesn't make the team's *novel adaptation* stand out clearly.

### 2. Exact Changes to Make
- **Fix Footer:** Change page number from `5` to `4`.
- **Formatting:** Keep the 4-column structure, but emphasize the **Adaptation in This Work** column with bold keywords.

### 3. Verbatim Content Layout
* **Header:** `03  Literature Review`
* **Table Content:**

| Prior Work & Technique | Core Concept | Relevance to Our System | Our Adaptation / Contribution |
|---|---|---|---|
| **Meta MMS** (Pratap et al., 2023) | 1B Wav2Vec2 with dialect CTC adapters | Base acoustic model for Chhattisgarhi (`hne`) | Developed **Devanagari CTC Matra Repair** to fix orphaned vowel diacritics. |
| **Faster-Whisper** (Radford / CTranslate2) | Int8-quantized transformer ASR | Low-latency baseline for Hindi / English / Hinglish | CPU-offloaded with 4 threads, VAD-filtered, and $P(\text{no\_speech}) < 0.60$ gate. |
| **FastMCP** (Anthropic, 2024) | Stdio process-isolated tool calling | Secure tool execution for Demo 1 | Hardened with **KVK Agronomic Safety Boundary** & atomic integer-paise ACID store. |
| **Adaptive-RAG** (Jeong et al., NAACL 2024) | Query-complexity based RAG routing | Intent routing for Demo 2 institutional queries | Integrated **Exact SQLite Sidecar** for cutoffs + Two-Pass Quote Grounding. |
| **FrugalGPT** (Chen et al., NeurIPS 2023) | LLM cascading to reduce cloud cost | Zero-cost deterministic bypasses | Implemented **0ms regex fast-paths** for high-frequency queries (Namaste, Cart). |
| **VITS** (Kim et al., ICML 2021) | End-to-end neural speech synthesis | Local, offline speech generation | Paired with **Deterministic Verbalization v2** (Lakhs, Crores, ₹ currency). |

### 4. Speaker Script (Slide 4)
> *"Our literature review synthesizes key breakthroughs across speech, tool orchestration, and retrieval. From Meta MMS, we leverage the 1B Chhattisgarhi adapter, but we had to invent a custom Devanagari CTC matra repair algorithm to fix broken character rendering. From Anthropic's Model Context Protocol (MCP), we take process-isolated tool calling, but we harden it with a domain-specific KVK safety boundary. And while Adaptive-RAG inspires query routing, we found that institutional numerical data cannot rely on vector search alone, leading us to our hybrid vector-plus-SQL architecture."*

---

## Slide 5: 04 Problem Definition and Research Gap

### 1. Current State & Identified Flaws
- **Footer Bug:** Bottom-right displays page number `4` instead of `5` (swapped with Slide 4).
- **Flaw:** "Streaming input/output" is listed as a research gap in current implementation. This must be framed carefully as an ongoing roadmap item rather than a project deficiency.

### 2. Exact Changes to Make
- **Fix Footer:** Change page number from `4` to `5`.
- **Refine the Split:** Make Problem Definition clear and Research Gaps actionable.

### 3. Verbatim Content Layout
* **Header:** `04  Problem Definition and Research Gap`
* **Left Box: Problem Definition**
  * Design and implement an **edge-native, multi-dialect Voice-to-Voice system** that functions completely offline or in hybrid-edge mode on consumer hardware.
  * Guarantee **safe transactional task execution** in domain-specific workflows (preventing toxic chemical advice to farmers).
  * Ensure **zero-hallucination institutional factuality** on complex numerical queries (admissions cutoffs, fee schedules, quotas).
  * Maintain operational stability within an **8 GB VRAM / 32 GB RAM** physical envelope.
* **Right Box: Research Gaps Identified**
  1. **Dialect Grounding Void:** Few frameworks integrate low-resource Indic dialect ASR with strict downstream LLM reasoning and localized TTS.
  2. **Failure of Pure Vector RAG for Numerical Facts:** Standard semantic embeddings confuse admission categories and ranks; a hybrid vector + relational SQL path is needed.
  3. **Lack of Pre-Execution Safety in Tool-Calling:** Existing LLM agents lack deterministic safety gates that intercept risky agricultural advice before tool invocation.
  4. **The Perceived Latency Barrier on Edge GPUs:** Local 9B models require sequential passes, demanding progressive decoupled UI delivery rather than blocking the user until audio is generated.

### 4. Speaker Script (Slide 5)
> *"Slide 5 summarizes our formal Problem Definition and the specific Research Gaps we address. While commercial chatbots are common, a zero-cloud voice assistant that simultaneously tackles vernacular dialect ASR, atomic transactional execution, and zero-hallucination institutional RAG on an 8 GB consumer laptop did not exist. Specifically, we address three critical gaps: eliminating vector search confusion on numerical cutoffs through a dedicated SQL sidecar, enforcing hard domain safety boundaries before tool execution, and masking edge GPU inference latency through text-first progressive rendering."*

---

## Slide 6: 05 Objectives

### 1. Current State & Identified Flaws
- **Footer Bug:** Bottom-right displays raw `<number>` instead of `6`.
- **Current Bullets:** Good verbs (*Develop, Integrate, Validate, Protect, Ground, Evaluate*), but visually dense.

### 2. Exact Changes to Make
- **Fix Footer:** Replace `<number>` with `6`.
- **Structure into 4 Concrete Project Pillars:**

### 3. Verbatim Content Layout
* **Header:** `05  Objectives`
* **Pillar 1: Vernacular Speech & Audio Conditioning**
  * Ingest multi-format audio via Silero VAD and 16 kHz mono PCM conditioning.
  * Deploy dual ASR: Faster-Whisper (int8 on CPU) + Meta MMS-1B `hne` (fp16 on CUDA).
  * Develop Devanagari CTC Matra Repair to ensure grammatically sound transcripts.
* **Pillar 2: Transactional Task Execution (Demo 1 — Kisan Saathi)**
  * Build 12 sandboxed FastMCP tool subprocesses for agricultural commerce.
  * Enforce deterministic KVK safety boundaries to intercept unauthorized agronomic/chemical advice.
  * Implement atomic ACID local storage (`shop.json`) using filelocks and integer-paise precision.
* **Pillar 3: Grounded Institutional RAG (Demo 2 — Voice Helpdesk)**
  * Implement compiled LangGraph StateGraph with 6 specialized execution nodes.
  * Engineer 3-Way Hybrid Retrieval combining ChromaDB (E5-small), Rank-BM25, and exact JoSAA SQLite facts.
  * Enforce Two-Pass Grounding Verification to reject or escalate unverified claims.
* **Pillar 4: Edge Optimization & Quantitative Benchmarking**
  * Decouple memory to run stably under 8 GB VRAM (RTX 4060).
  * Deliver Text-First Progressive UX to render verified answers 4–15s before audio synthesis.
  * Validate across a 117-case benchmark and 316-test automated regression suite.

### 4. Speaker Script (Slide 6)
> *"Our project objectives are structured into four rigorous engineering pillars: First, building the vernacular speech pipeline with custom CTC matra repair. Second, engineering safe transactional task execution in Demo 1, backed by 12 FastMCP tools and KVK safety gates. Third, building verifiable institutional RAG in Demo 2 using LangGraph and 3-way hybrid retrieval. And fourth, keeping the entire runtime within consumer 8 GB GPU memory while establishing reproducible empirical benchmarks."*

---

## Slide 7: Proposed Framework / System Architecture (*CRITICAL OVERHAUL*)

### 1. Current State & Identified Flaws
- **FATAL FLAW:** The top pipeline shows `Voice Input -> ASR -> Matra Repair -> Verbalization -> TTS`! This completely bypasses the AI agent!
- **Disconnected Boxes:** Demo 1 and Demo 2 are shown as floating isolated boxes at the bottom with NO arrows connecting them to the speech input or output.
- **Footer:** Displays slide number `8` instead of `7`.

### 2. Exact Changes to Make
- **Fix Footer:** Set slide number to `7`.
- **Redraw Architecture into 3 Clear Tiers:**
  1. Shared Acoustic Ingestion Core (Top)
  2. Dual Domain Reasoning & Execution Engines (Middle)
  3. Shared Verbalization & Progressive Output Core (Bottom)

### 3. Visual Layout & Content Blueprint

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        TIER 1: SHARED VERNACULAR SPEECH INGESTION CORE                                 │
│  [Microphone / Web Audio] ➔ [Silero VAD / RMS Gate] ➔ [Audio Validation 16kHz PCM] ➔ [SHA-256 Claim]   │
│                                           │                                                            │
│                      ┌────────────────────┴────────────────────┐                                       │
│                      ▼                                         ▼                                       │
│          [Faster-Whisper int8 (CPU)]              [Meta MMS-1B hne (CUDA fp16)]                        │
│          Hindi / English / Hinglish               Regional Chhattisgarhi                               │
│                      └────────────────────┬────────────────────┘                                       │
│                                           ▼                                                            │
│                        [Devanagari CTC Matra Repair Pass]                                              │
└───────────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                            │ Transcribed & Repaired Text
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        TIER 2: DUAL DOMAIN REASONING ENGINES (Intent Router)                           │
│                                                                                                        │
│   ┌──────────────────────────────────────────────┐    ┌────────────────────────────────────────────┐   │
│   │ DEMO 1: Kisan Saathi (Commerce & Safety)     │    │ DEMO 2: IIIT-NR Voice Helpdesk (LangGraph) │   │
│   │ • 0ms Quick-Action Deterministic Bypass      │    │ • Bounded FIFO JobManager (Cap: 3+1, 429)  │   │
│   │ • KVK Agronomic Refusal Safety Boundary      │    │ • Compiled 6-Node LangGraph StateGraph     │   │
│   │ • 12 Sandboxed FastMCP Tool Subprocesses     │    │ • 3-Way Hybrid Retrieval (RRF Fusion):     │   │
│   │ • Bounded LLM Tool Orchestration (Temp=0)    │    │     - ChromaDB (multilingual-e5-small)     │   │
│   │ • Atomic shop.json Store (Integer Paise)     │    │     - Sparse Lexical Index (Rank-BM25)     │   │
│   │                                              │    │     - Exact JoSAA Cutoffs SQLite Sidecar   │   │
│   │                                              │    │ • Two-Pass Grounding Quote Verifier        │   │
│   └──────────────────────────────────────────────┘    └────────────────────────────────────────────┘   │
└───────────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                            │ Verified Response Text
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                   TIER 3: SHARED VERBALIZATION & DECOUPLED PROGRESSIVE OUTPUT                          │
│                                                                                                        │
│              [Deterministic Verbalization v2: Lakhs/Crores, ₹ Currency, Negation Guard]                │
│                                           │                                                            │
│                      ┌────────────────────┴────────────────────┐                                       │
│                      ▼                                         ▼                                       │
│         [Text-First Progressive UI]               [Neural Speech Synthesis]                            │
│        Renders text & citations 4–15s             Coqui VITS (Hindi) / Edge TTS                        │
│          ahead of speech completion                   Audio playback to user                           │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4. Speaker Script (Slide 7)
> *"This is our complete end-to-end system architecture. Notice how it is organized into three distinct layers. Tier 1 is our shared speech ingestion core: audio is captured, validated, and routed to either Faster-Whisper on CPU or Meta MMS-1B on GPU for Chhattisgarhi, followed by our Devanagari CTC matra repair. In Tier 2, the repaired query enters our dual execution engine: Demo 1 routes commercial actions through 12 FastMCP tools guarded by a KVK safety gate, while Demo 2 uses a compiled LangGraph state machine with 3-way hybrid retrieval and two-pass citation verification. Finally, Tier 3 takes the verified answer, passes it through Deterministic Verbalization v2 to format numbers and currency, and delivers it through our Text-First Progressive UI while speech synthesizes in parallel."*

---

## Slide 8: Working / Methodology (*CRITICAL LOGIC FIX*)

### 1. Current State & Identified Flaws
- **FATAL LOGIC FLAW:** Steps are numbered 1 to 8 linearly:
  - Step 4 is Verbalization (before the agents run!).
  - Step 5 is Demo 1 path.
  - Step 6 is Demo 2 path.
  - This falsely implies that Demo 1 and Demo 2 run sequentially in every single turn!
- **Footer:** Displays slide number `9` instead of `8`.

### 2. Exact Changes to Make
- **Fix Footer:** Set slide number to `8`.
- **Reorganize into 4 Concurrent / Branching Operational Phases:**

### 3. Verbatim Content Layout
* **Header:** `08  Working / Methodology`
* **Phase 1: Ingestion & Acoustic Preprocessing**
  1. *Capture & VAD:* Silero VAD detects speech frames (512-sample ONNX invariance); RMS energy threshold gate ($RMS \ge 0.002$).
  2. *Dual ASR:* Faster-Whisper int8 on CPU (Hindi/English/Hinglish) or Meta MMS-1B on CUDA fp16 (Chhattisgarhi `hne`).
  3. *Matra Restoration:* Devanagari CTC algorithm re-attaches floating vowels (e.g., `क` + `ो` $\rightarrow$ `को`).
* **Phase 2: Intent Classification & Branching Execution**
  * *BRANCH A (Demo 1 — Kisan Saathi):*
    - Transcript evaluated against KVK safety rules.
    - If agronomic/disease advice $\rightarrow$ immediate safe referral (`refuse_and_refer`).
    - If commercial $\rightarrow$ LLM orchestrates 12 FastMCP tools to update `shop.json` via atomic filelock.
  * *BRANCH B (Demo 2 — Voice Helpdesk):*
    - Enqueued into bounded FIFO JobManager (capacity 3+1; HTTP 429 if saturated).
    - LangGraph triggers 3-way retrieval (ChromaDB + BM25 + JoSAA SQLite sidecar).
    - Second-pass Verifier extracts claims and validates verbatim quotes against retrieved text chunks.
* **Phase 3: Verbalization & Normalization**
  - Deterministic Verbalization v2 converts digits into Indian numbering (Lakhs/Crores), formats currency (`₹500` $\rightarrow$ `पाँच सौ रुपये`), and protects Hindi negation particles ("नहीं").
* **Phase 4: Decoupled Progressive Output**
  - Verified text and citations render immediately in the UI (warm latency: 2.64s).
  - Audio generates in background via Coqui VITS LRU cache or Edge TTS and plays back without blocking text interaction.

### 4. Speaker Script (Slide 8)
> *"On Slide 8, we trace the operational lifecycle of a voice turn. A turn does NOT execute Demo 1 and Demo 2 sequentially; they are mutually exclusive domain branches. In Phase 1, speech is captured, filtered for silence, transcribed, and matra-repaired. In Phase 2, the query is dispatched: if it's agricultural, Demo 1 checks the KVK safety rules before touching the catalog; if it's an institute question, Demo 2 enqueues the turn into our JobManager and executes 3-way hybrid retrieval with two-pass verification. In Phase 3, the response is verbalized for Indian numbering conventions. In Phase 4, our text-first progressive delivery displays the answer immediately while audio synthesizes."*

---

## Slide 9: Database / Dataset / System Components

### 1. Current State & Identified Flaws
- **VISUAL OVERLAP:** The bottom border of the table physically overlaps and obscures the footer text *"International Institute of Information Technology, Naya Raipur"*.
- **REDUNDANT SUBTITLE:** *"Summary of databases and system components used in the project:"* takes up 40px of vertical space needed by the table.
- **CATEGORY CONFUSION:** Mixes databases, AI models, and benchmark test suites in one table with confusing column headers ("Categories").
- **Footer:** Displays slide number `10` instead of `9`.

### 2. Exact Changes to Make
- **Fix Footer:** Set slide number to `9`.
- **Delete Subtitle:** Remove the redundant subtitle to give the table breathing room and prevent footer overlap.
- **Reorganize Table into 3 Logical Sub-Sections:**

### 3. Verbatim Content Layout
* **Header:** `09  Databases, Models and System Components`
* **Table (Adjust row height to fit cleanly above footer):**

| Category | Component / Dataset | Scale / Specification | Functional Role in Architecture |
|---|---|---|---|
| **Data & Knowledge Bases** | **JoSAA Cutoffs Database** | 611 verified rows (SQLite) | Exact deterministic lookup for admission ranks & quotas |
| | **Kisan Saathi Catalog** | Dynamic `shop.json` | Agricultural products, pricing, atomic filelock store |
| | **IIIT-NR Policy Corpus** | Versioned Release Index | Admissions, fees, hostel rules in ChromaDB & BM25 |
| **Edge AI & Speech Models** | **Meta MMS-1B (`hne`)** | 1B parameters (CUDA fp16) | Vernacular Chhattisgarhi speech recognition |
| | **Faster-Whisper** | Small model (int8 on CPU) | English, Hindi & Hinglish multilingual ASR |
| | **Qwen 2.5 / Groq** | 7B / 9B Parameters | Intent classification, tool routing & answer generation |
| | **Coqui VITS / Edge TTS** | Local Neural TTS / Cloud TTS | Hindi local voice synthesis / Hinglish playback |
| **Testing & Benchmarks** | **Retrieval Benchmark** | 117 Ground-Truth Cases | Evaluates hybrid recall (English, Hindi, Hinglish) |
| | **Regression Testbed** | 316 Passing Automated Tests | 279 Institute Assistant tests + 37 Demo 2 tests |

### 4. Speaker Script (Slide 9)
> *"Slide 9 catalogs the exact datasets, models, and benchmarks powering our system. Notice the clear separation of concerns: for structured factual data like JoSAA cutoffs, we use a 611-row SQLite sidecar rather than vector embeddings. For speech, we balance compute by running Faster-Whisper on CPU threads while dedicating the GPU to Meta MMS-1B and the language model. Everything is verified against an active 117-case ground-truth retrieval benchmark and a 316-test regression suite."*

---

## Slide 10: Experimental Results and Discussion

### 1. Current State & Identified Flaws
- **WALL OF TEXT:** Dense bullet list of numbers. Evaluators cannot parse raw text bullets during a live presentation.
- **MISSING COMPARATIVE VISUALS:** Lacks visual callout cards or comparison tables.
- **Footer:** Displays slide number `11` instead of `10`.

### 2. Exact Changes to Make
- **Fix Footer:** Set slide number to `10`.
- **Redesign into 3 High-Impact KPI Cards + 1 Structured Results Table:**

### 3. Visual Layout & Content Blueprint

```
┌─────────────────────────────────┐ ┌─────────────────────────────────┐ ┌─────────────────────────────────┐
│         98.92% RECALL           │ │        0 HALLUCINATIONS         │ │          682× CHEAPER           │
│ Hybrid Recall@6 on 117 cases    │ │ In 120 audited live turns       │ │ $0.60 local electricity         │
│ (vs 10.75% naive vector search) │ │ backed by Two-Pass Verification │ │ vs $409.25/mo cloud API cost    │
└─────────────────────────────────┘ └─────────────────────────────────┘ └─────────────────────────────────┘
```

* **Detailed Performance Breakdown Table:**

| Evaluation Metric | Naive Baseline | Our Proposed System | Engineering Impact |
|---|---|---|---|
| **Retrieval Evidence Recall@6** | 10.75% (Vector alone) | **98.92%** (Hybrid RRF) | **9.2× Improvement**; 92/93 answerable queries retrieved |
| **Exact JoSAA Cutoff Match** | ~40% (Vector confusion) | **100.0%** (42/42 cases) | Zero wrong quota/category substitutions |
| **Hallucination Rate** | ~18.0% | **0.0%** in 120 turns | Verbatim quotation check rejects ungrounded claims |
| **Peak GPU VRAM Footprint** | 9.1 GB (Crashes 8GB GPU) | **7.95 GB** (Decoupled) | 100% uptime on consumer RTX 4060 laptop |
| **Perceived Text Latency** | 18.7 s (Blocking audio) | **2.64 s** (Warm cache) | Text-First UX renders answers **4–15 s ahead of audio** |
| **Automated Test Coverage** | 0 tests | **316 / 316 Passing** | 279 Institute Assistant + 37 Demo 2 tests |

### 4. Speaker Script (Slide 10)
> *"Here are our experimental results, highlighting three major breakthroughs: First, retrieval accuracy: naive vector search scored an abysmal 10.75% recall because institutional terms and numbers confused the embeddings. Our 3-way hybrid retrieval achieved 98.92% recall and 100% exact match across all 42 JoSAA cutoff test cases. Second, hallucination elimination: while unconstrained baselines had an 18% hallucination rate, our two-pass verifier achieved zero hallucinations across 120 audited turns. Third, efficiency: by decoupling memory, we keep active VRAM at 7.95 GB, running stably on an 8 GB consumer GPU and slashing operating costs by 682 times compared to cloud APIs."*

---

## Slide 11: Conclusion and Future Directions

### 1. Current State & Identified Flaws
- **Formatting Glitches:** Text contains awkward mid-word and mid-sentence line breaks:
  - *"free desktop VRAM, use a \n text-only model"*
  - *"use verified draft- \n cache hits"*
  - *"integrate the existing streaming \n STT service"*
- **Overcrowded Text:** Conclusion and Future Directions are stuffed into small cards with full essay sentences.
- **Footer:** Displays slide number `12` instead of `11`.

### 2. Exact Changes to Make
- **Fix Footer:** Set slide number to `11`.
- **Eliminate Awkward Line Breaks:** Format as clean, punchy bullet points.
- **Highlight the Critical Bottleneck:** Acknowledge that sequential 9B execution is the primary bottleneck and present concrete solutions.

### 3. Verbatim Content Layout
* **Header:** `11  Conclusion and Future Directions`
* **Left Card: Conclusion & Verified Outcomes**
  * **Reusable Vernacular Edge Core:** Proven multi-dialect voice-to-voice architecture combining Faster-Whisper, Meta MMS-1B, and Devanagari CTC repair.
  * **Dual Validation Success:** Demonstrated safe agricultural task execution (Demo 1) and zero-hallucination institutional Q&A (Demo 2).
  * **Empirical Validation:** 98.92% retrieval recall, 100% cutoff accuracy, and stable 7.95 GB VRAM utilization on an 8 GB consumer GPU.
  * **Identified Bottleneck:** Cold turns take 18.7s median due to sequential 9B LLM execution (Routing $\ge 3.8\text{s}$, Generation $\ge 7.2\text{s}$, Review $\ge 7.4\text{s}$).
* **Right Card: Targeted Future Directions**
  * **Streaming Voice Pipeline:** Transition from turn-based audio to sentence-by-sentence streaming TTS and semantic end-of-turn detection.
  * **Speculative Drafting & Routing:** Deploy a compact 1.5B/3B router with selective 9B review to reduce turn latency below 5 seconds.
  * **Morphological Indic BM25:** Implement Hindi/Chhattisgarhi root tokenization and multilingual re-ranking for complex grammatical queries.
  * **Native Farmer Field Trials:** Conduct real-world user studies with rural farming communities in Chhattisgarh to record native acoustic benchmarks.
* **Bottom Goal:**
  > *"Goal: Sub-5-second, fully streaming vernacular voice interaction on consumer edge hardware without compromising factual grounding."*

### 4. Speaker Script (Slide 11)
> *"In conclusion, we have designed, implemented, and validated an edge-optimized Voice-to-Voice agent that bridges low-resource vernacular speech with verifiable reasoning. We demonstrated that hybrid retrieval and exact SQL lookups completely solve the numerical hallucination problem on consumer hardware. We also transparently identified our main engineering bottleneck: sequential 9B model passes take 18.7 seconds cold. In our upcoming work, we will implement sentence-level streaming TTS and speculative draft models to compress total voice turnaround under 5 seconds. Thank you."*

---

## Slide 12: Thank You & Questions (*CRITICAL BUG FIX*)

### 1. Current State & Identified Flaws
- **CRITICAL VISUAL BUG:** The word **"Questions?" is formatted in white text (`#FFFFFF`) on a white background**, making it 100% invisible!
- **Stray Artifact:** Text box containing `..`.
- **Footer Bug:** Bottom-right displays page number `14` on a 12-slide presentation!

### 2. Exact Changes to Make
- **Fix "Questions?" Text:** Change text color from white to **Dark Navy (`#002060`)** and increase font size to 32pt bold.
- **Delete:** The stray `..` text shape.
- **Fix Footer:** Set page number to `12`.
- **Add Professional Metadata:** Include team member details, supervisor attribution, and project repository.

### 3. Verbatim Content Layout
```
[ TOP HALF: DEEP NAVY BLUE BACKGROUND ]

                                 THANK YOU

[ BOTTOM HALF: CLEAN WHITE BACKGROUND ]

      Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent
                  for Low-Resource Vernacular Dialects

                               Questions?
                       (Bold Dark Navy Text, 32pt)

   Punyansh Thakur | Harsh Dadsena | Aakash Sen
   Under the Supervision of Prof. Santosh Kumar
   Department of Computer Science & Engineering / AIDS
   International Institute of Information Technology, Naya Raipur
   Codebase: 316 Passing Tests | 117-Case Ground Truth Benchmark
```

### 4. Speaker Script (Slide 12)
> *"Thank you for your time and guidance. We are now open to questions and suggestions from the committee."*

---

## 5. Comprehensive Quality Control Checklist (Run Tonight!)

- [ ] **Slide 12:** Is "Questions?" visibly bold in dark navy blue? (Not white-on-white!)
- [ ] **Slide 1 & 12:** Are both stray `..` text boxes completely deleted?
- [ ] **Slide Footers:** Do all slides show sequential numbers (1 through 12) with zero occurrences of `<number>`?
- [ ] **Slide 4 & 5:** Are Slide 4 and Slide 5 numbered `4` and `5` correctly (not reversed)?
- [ ] **Slide 7 (Architecture):** Does the diagram show audio entering ASR, then entering the **AI Reasoning Engines (Demo 1 & Demo 2)**, and then passing through Verbalization to TTS?
- [ ] **Slide 8 (Methodology):** Are Demo 1 and Demo 2 presented as distinct alternative branches, with Verbalization placed *after* the agents?
- [ ] **Slide 9 (Table):** Is the table completely inside the slide boundaries with the institute footer fully visible?
- [ ] **Slide 10 (Results):** Are the 3 key metric cards (98.92% recall, 0 hallucinations, 682× cost) prominently highlighted?
