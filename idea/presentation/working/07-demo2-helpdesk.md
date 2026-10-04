# Demo 2 Deep-Dive: IIIT-NR Voice Helpdesk & Asynchronous Job Architecture

**Location:** [`code/demo2/`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2)  
**Primary Tech Stack:** Streamlit (`@st.fragment`), Bounded Thread Workers, Ollama (`qwen3.5:9b`), SQLite with 24-Hour Retention, Silero/Whisper/MMS, Coqui VITS, Microsoft Edge TTS, Regex Verbalization v2  
**Target Domain:** Institutional Counseling, JoSAA/CSAB Cutoffs, Fee Structures & Policies  
**Location:** `idea/presentation/working/07-demo2-helpdesk.md`

---

## 1. Module Overview & Operational Thesis

Demo 2 is an academic voice helpdesk for IIIT-NR (International Institute of Information Technology, Naya Raipur). It answers prospective students' and parents' queries regarding JoSAA/CSAB cutoffs, seat matrices, reservation quotas, fee structures, scholarships, and campus facilities.

### Operational Reality on Consumer Hardware:
Running a 9-billion parameter reasoning model locally on an **8 GB NVIDIA RTX 4060 laptop GPU** alongside acoustic models imposes severe physical constraints. A single local LLM reasoning turn takes **15 to 20 seconds**. Uncontrolled incoming requests would instantly crash the GPU with CUDA Out-Of-Memory (OOM) errors.

Demo 2 resolves this through an **asynchronous bounded worker queue**, **text-first progressive rendering**, and **deterministic pronunciation normalization**.

```mermaid
flowchart TD
    User["Student / Parent"] --> UI["Streamlit UI (app.py)"]
    UI -->|Submit Job| JM["JobManager Queue (jobs.py)\n[Cap: 1 Active + Max 3 Queued]"]
    
    subgraph Reasoning Worker (demo-reasoning thread)
        JM --> Dec["speech.py::decode_audio\n(RMS Silence Gate)"]
        Dec --> ASR["speech.py::transcribe\n(Whisper / MMS-hne)"]
        ASR --> Bridge["agent_bridge.py\n(LangGraph AssistantState)"]
        Bridge --> RAG["3-Way Hybrid E5 + BM25 + JoSAA SQL Sidecar"]
        RAG --> LLM["Ollama Qwen 3.5:9B (Q4_K_M)"]
        LLM --> Review["Critical Grounding Review Pass\n(Verbatim Quote Verification)"]
        Review --> StoreText["storage.py::Store.complete\n(Saves Verified Text & Citations)"]
    end

    StoreText -->|Immediate Wakeup| Frag["st.fragment UI\n(TEXT-FIRST DISPLAY SAVES 4-15s)"]
    
    subgraph Speech Pool (demo-speech thread)
        StoreText --> Verb["verbalization.py\n(Regex Normalization v2)"]
        Verb --> TTS["speech.py::synthesize\n(VITS Local Hindi / Edge TTS English)"]
        TTS --> StoreAudio["storage.py::Store.attach_audio"]
    end

    StoreAudio --> UI
```

---

## 2. File-by-File Technical Deep Dive

### 2.1 `settings.py` — Central Tunables & Capacity Invariants

[`settings.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/settings.py) configures the runtime environment:
- `DEFAULT_MODEL_PROVIDER = "ollama"` (Falls back to `"groq"` only when explicitly selected).
- `OLLAMA_MODEL = "qwen3.5:9b"`: Primary local reasoning engine.
- `QUEUE_CAPACITY = 3`: Maximum number of waiting jobs before the system issues an immediate HTTP 429 (`busy`) rejection.
- `TURN_TIMEOUT_SECONDS = 120`: Watchdog timeout for reasoning turns.
- `QUEUE_TIMEOUT_SECONDS = 60`: Deadline for waiting in the FIFO queue.
- `EDGE_TIMEOUT_SECONDS = 45`: Watchdog for external TTS synthesis.
- `RETENTION_HOURS = 24`: Mandatory privacy cleanup window.

---

### 2.2 `jobs.py` — Concurrency Gate & Bounded Worker Lifecycle

[`jobs.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/jobs.py) isolates shared hardware models from volatile browser sessions.

#### Architecture of `JobManager`:
1. **Thread Separation:**
   - `demo-reasoning`: A single dedicated OS thread (`self.worker`) processing LLM reasoning sequentially.
   - `demo-speech`: A bounded `ThreadPoolExecutor(max_workers=1)` handling TTS synthesis.
2. **Admission Control (`submit()`):**
   - Checks if the user's conversational session is already processing a query (`conversation_busy`).
   - Checks global queue depth:
     $$\text{Active Jobs} + \text{Queued Jobs} \ge \text{QUEUE\_CAPACITY} + 1 \implies \text{Raise ValueError("busy")}$$
3. **Decoupled Text-First Completion (F05):**
   In `_run()`, as soon as `agent_bridge.ask()` produces the verified text response and citations, `store.complete()` writes the record to SQLite. The Streamlit UI immediately renders the text, cutting the user's perceived wait time by $4\text{--}15\text{ s}$ while `demo-speech` generates audio in the background.
4. **Cooperative Cancellation:**
   If a user clicks "New conversation" or closes their tab, `job.cancelled.set()` triggers. The reasoning thread detects this between stages and aborts downstream TTS synthesis, immediately freeing compute resources.

---

### 2.3 `storage.py` — SQLite State, Auditing & 24h Privacy Purging

[`storage.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/storage.py) implements the relational store backed by `data/store.sqlite`.

#### Relational Tables:
- `sessions`: Session ID, creation timestamp, active language.
- `turns`: Sequential turn tracking (`pending` $\to$ `complete` $\to$ `failed`).
- `requests`: Fingerprint hash, prompt text, recording audio blob.
- `completions`: LLM generated answer, verified source citations, evaluation score.
- `audio`: Synthesized 22.05 kHz WAV / MP3 audio byte arrays.

#### Compaction & Retention Invariants (`maintain()`):
1. **Compaction:** `compact()` keeps only the newest 2 complete checkpoints after each successful turn, preventing unbounded database growth.
2. **24-Hour Privacy Purge:** All recordings, transcripts, and audio buffers older than 24 hours are permanently deleted:
   $$\text{DELETE FROM turns WHERE strftime('\%s', 'now') - strftime('\%s', created\_at) } > 86400$$
3. **Online Backup Drill:** Online SQLite backup API via `ops.py backup` and `ops.py restore`.

---

### 2.4 `speech.py` — Ingress Energy Gates & Dual TTS Engines

[`speech.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/speech.py) manages speech I/O:

1. **RMS Silence Energy Gate:**
   Computes root-mean-square audio energy:
   $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^N x_i^2}$$
   If $\text{RMS} < \text{threshold}$, the input is classified as ambient background noise. The job halts immediately without consuming LLM compute.
2. **ASR Dispatch:**
   - `Hindi`, `English`, `Hinglish` $\implies$ `FasterWhisper` (int8 CTranslate2 on CPU).
   - `Chhattisgarhi` $\implies$ Meta MMS-1B (`hne` adapter on CUDA `float16`).
3. **Dual Synthesis Engine:**
   - **Local Path (Hindi/Chhattisgarhi):** Resident Coqui VITS model in host RAM synthesizes audio on CPU at 22,050 Hz with zero voice-switch overhead.
   - **Cloud/Hybrid Path (English/Hinglish):** Subprocess call to Microsoft Edge TTS (`edge-tts --voice en-IN-NeerjaNeural`).

---

### 2.5 `verbalization.py` — Deterministic Pronunciation Engine (v2)

Neural TTS models fail catastrophically when encountering domain abbreviations, Latin digits, or percentages in Devanagari mode. `verbalization.py` (`domain-pronunciation-2`) applies deterministic regex-based text transformations:

1. **Academic & Regional Lexicon:**
   - `IIIT-NR` $\implies$ `आईआईआईटी नया रायपुर`
   - `JoSAA` $\implies$ `जोसा`
   - `CSAB` $\implies$ `सीसैब`
   - `ECE` $\implies$ `ईसीई`
2. **Indian Cardinal Numbering (`cardinal()`):**
   - `15432` $\implies$ `पंद्रह हजार चार सौ बत्तीस`
   - `₹1,25,000` $\implies$ `एक लाख पच्चीस हजार रुपये`
3. **Date Verbalization:**
   - `15/08/2026` $\implies$ `पंद्रह अगस्त दो हज़ार छब्बीस`
4. **Negation Guard (`NEGATION`):**
   Protects critical negative constraints from phonetic distortion:
   - `"non-refundable"` $\implies$ `"गैर-वापसी योग्य"`
   - `"excluding"` $\implies$ `"को छोड़कर"`
   - `"not eligible"` $\implies$ `"पात्र नहीं"`

---

### 2.6 `agent_bridge.py` & `app.py` — LangGraph Bridge & `@st.fragment`

1. **[`agent_bridge.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/agent_bridge.py)**:
   - Imports `build_graph()` from `institute-assistant`.
   - Passes the query into the LangGraph state machine.
   - Extracts verified answer text and multi-page citation attribution.

2. **[`app.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/app.py)**:
   - Leverages Streamlit's `@st.fragment(run_every=0.5)`.
   - Only the conversation chat container polls the SQLite store, providing a responsive interface while waiting for the LLM response.
   - Renders expandable **"View Sources"** accordions showing exact quoted evidence, document dates, and page numbers (`[Page 2]`, `[Page 4]`).

---

## 3. Architecture Decisions & Rationale (Viva Defense)

| Design Choice | Alternative Considered | Technical Rationale for Choice |
|---|---|---|
| **Bounded Worker Queue (1+1 Threads)** | Unbounded asynchronous concurrency (`asyncio.gather`) | A single 8 GB GPU cannot hold multiple concurrent 9B LLM inference batches in memory. Unbounded concurrency causes out-of-memory crashes. A bounded FIFO queue guarantees system stability under traffic spikes. |
| **Progressive Text-First Rendering** | Monolithic S2S (wait for audio before showing text) | Showing verified text immediately upon LLM completion allows the user to read while audio synthesizes, reducing perceived latency from 21.2s to 18.6s (cold) and 2.64s (warm). |
| **Deterministic Regex Verbalization** | LLM-based phonetic re-prompting | Asking an LLM to rewrite text phonetically introduces hallucinations and risks dropping crucial negation words (e.g. turning "fees are non-refundable" into "fees are refundable"). Regex substitution guarantees 100% semantic fidelity. |
| **SQLite with 24h Purge** | Ephemeral memory / Redis | SQLite provides ACID transaction guarantees without running external background services. The 24-hour cleanup policy ensures compliance with student data protection and privacy policies. |
