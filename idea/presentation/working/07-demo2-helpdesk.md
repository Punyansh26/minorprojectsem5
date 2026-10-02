# Demo 2 Deep-Dive: IIIT-NR Voice Helpdesk & Asynchronous Job Architecture

**Location:** [`code/demo2/`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2)  
**Primary Tech Stack:** Streamlit (`@st.fragment`), Bounded Thread Workers, Ollama (`qwen3.5:9b`), SQLite with 24-Hour Retention, Silero/Whisper/MMS, Coqui VITS, Microsoft Edge TTS, Regex Verbalization v2.

---

## 1. Module Overview & Operational Thesis

Demo 2 is an academic voice helpdesk for IIIT-NR (International Institute of Information Technology, Naya Raipur). It answers prospective students' and parents' queries regarding JoSAA/CSAB cutoffs, seat matrices, reservation quotas, fee structures, scholarships, and campus facilities.

### Operational Reality on Consumer Hardware:
Running a 9-billion parameter reasoning model locally on an **8 GB NVIDIA RTX 4060 laptop GPU** alongside acoustic models imposes severe physical constraints. A single local LLM reasoning turn takes **20 to 50 seconds**. Uncontrolled incoming requests would instantly crash the GPU with CUDA Out-Of-Memory (OOM) errors.

Demo 2 resolves this through an **asynchronous bounded worker queue**, **text-first progressive rendering**, and **deterministic pronunciation normalization**.

```mermaid
flowchart TD
    User["Student / Parent"] --> UI["Streamlit UI (app.py)"]
    UI -->|Submit Job| JM["JobManager Queue (jobs.py)\n[Cap: 1 Active + Max 3 Queued]"]
    
    subgraph Reasoning Worker (demo-reasoning)
        JM --> Dec["speech.py::decode_audio\n(RMS Silence Gate)"]
        Dec --> ASR["speech.py::transcribe\n(Whisper / MMS-hne)"]
        ASR --> Bridge["agent_bridge.py\n(LangGraph AssistantState)"]
        Bridge --> RAG["Hybrid E5 + BM25 + JoSAA Cutoff Engine"]
        RAG --> LLM["Ollama Qwen3.5 9B / Groq"]
        LLM --> StoreText["storage.py::Store.complete\n(Saves Text & Citations)"]
    end

    StoreText -->|Immediate Wakeup| Frag["st.fragment UI\n(TEXT-FIRST DISPLAY)"]
    
    subgraph Speech Pool (demo-speech)
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
- `SPEECH_DEADLINE_S = 120`: Watchdog timeout for neural synthesis.
- `RETENTION_HOURS = 24`: Mandatory privacy cleanup window.

---

### 2.2 `jobs.py` — Concurrency Gate & Bounded Worker Lifecycle

[`jobs.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/jobs.py) isolates shared hardware models from volatile browser sessions.

#### Architecture of `JobManager`:
1. **Thread Separation**:
   - `demo-reasoning`: A single dedicated OS thread (`self.worker`) processing LLM reasoning sequentially.
   - `demo-speech`: A bounded `ThreadPoolExecutor(max_workers=1)` handling TTS synthesis.
2. **Admission Control (`submit()`)**:
   - Checks if the user's conversational session is already processing a query (`conversation_busy`).
   - Checks global queue depth:
     $$\text{Active Jobs} + \text{Queued Jobs} \ge \text{QUEUE\_CAPACITY} + 1 \implies \text{Raise ValueError("busy")}$$
3. **Decoupled Text-First Completion**:
   In `_run()`, as soon as `agent_bridge.ask()` produces the text response and citations, `store.complete()` writes the record to SQLite. The Streamlit UI immediately renders the text, cutting the user's perceived wait time by up to 50% while `demo-speech` generates the audio in the background.
4. **Cancellation Suppression**:
   If a user clicks "Cancel" or closes their tab, `job.cancelled.set()` triggers. The reasoning thread detects this between stages and aborts downstream TTS synthesis, immediately freeing compute resources.

---

### 2.3 `storage.py` — SQLite State, Auditing & 24h Privacy Purging

[`storage.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/storage.py) implements the relational store backed by `data/store.sqlite`.

#### Relational Tables:
- `sessions`: Session ID, creation timestamp, active language.
- `turns`: Sequential turn tracking (`pending` $\to$ `complete` $\to$ `failed`).
- `requests`: Fingerprint hash, prompt text, recording audio blob.
- `completions`: LLM generated answer, verified source citations, evaluation score.
- `audio`: Synthesized 22.05 kHz WAV / MP3 audio byte arrays.

#### The 24-Hour Retention Invariant (`maintain()`):
In compliance with student privacy guidelines:
$$\text{DELETE FROM turns WHERE strftime('\%s', 'now') - strftime('\%s', created\_at) } > 86400$$
The background maintenance thread runs periodically to purge user recordings, transcripts, and audio files older than 24 hours.

---

### 2.4 `speech.py` — Multilingual Ingress & Dual-Engine Speech Synthesis

[`speech.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/speech.py) manages speech I/O:

1. **RMS Silence Gate**:
   Computes root-mean-square audio energy:
   $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^N x_i^2}$$
   If $\text{RMS} < \text{threshold}$, the input is classified as ambient background noise. The job halts immediately without invoking the heavy LLM.
2. **ASR Dispatch**:
   - `Hindi`, `English`, `Hinglish` $\implies$ `FasterWhisper` (leveraging bilingual acoustic representations).
   - `Chhattisgarhi` $\implies$ Meta MMS-1B (`hne` adapter).
3. **Dual Synthesis Engine**:
   - **Local Path (Hindi)**: Local Coqui VITS model synthesizes audio on CPU at 22,050 Hz.
   - **Cloud/Hybrid Path (English/Hinglish)**: Subprocess call to Microsoft Edge TTS (`edge-tts --voice en-IN-NeerjaNeural`) to correctly articulate technical English jargon and acronyms.

---

### 2.5 `verbalization.py` — Deterministic Pronunciation Engine (v2)

[`verbalization.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/verbalization.py) is a specialized text normalization engine. 

Neural TTS models fail catastrophically when encountering domain abbreviations or numeric tabular data. `verbalization.py` applies deterministic regex-based text transformations **before** sending text to the vocoder:

#### 1. Academic & Regional Lexicon Expansion:
- `IIIT-NR` $\implies$ `आईआईआईटी नया रायपुर`
- `JoSAA` $\implies$ `जोसा`
- `CSAB` $\implies$ `सीसैब`
- `ECE` $\implies$ `ईसीई`
- `B.Tech` $\implies$ `बीटेक`

#### 2. Indian Cardinal Numbering (`cardinal()`):
Converts numeric values using the Indian numbering system:
- `15432` $\implies$ `पंद्रह हजार चार सौ बत्तीस`
- `₹1,25,000` $\implies$ `एक लाख पच्चीस हजार रुपये`

#### 3. Date Verbalization:
- `15/08/2026` $\implies$ `पंद्रह अगस्त दो हज़ार छब्बीस`

#### 4. Negation Preservation (`NEGATION`):
Protects critical negative constraints from phonetic distortion:
- `"non-refundable"` $\implies$ `"गैर-वापसी योग्य"`
- `"not eligible"` $\implies$ `"पात्र नहीं"`

---

### 2.6 `agent_bridge.py` & `app.py` — LangGraph Bridge & Streamlit Fragment

1. **[`agent_bridge.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/agent_bridge.py)**:
   - Imports `build_graph()` from `institute-assistant`.
   - Passes the query into the LangGraph state machine.
   - Parses the structured output into answer text and multi-page citation attribution.

2. **[`app.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2/app.py)**:
   - Leverages Streamlit's `@st.fragment(run_every="1s")`.
   - Instead of rerunning the entire page while waiting for the 30-second LLM response, only the conversation chat container polls the SQLite store, providing a responsive interface.
   - Renders expandable **"View Sources"** accordions showing exact quoted evidence, document dates, and page numbers.

---

## 3. Architecture Decisions & Rationale (Viva Defense)

| Design Choice | Alternative Considered | Engineering Rationale |
|---|---|---|
| **Bounded Worker Queue (1+1 Threads)** | Unbounded asynchronous concurrency (`asyncio.gather`) | A single 8 GB GPU cannot hold multiple concurrent 9B LLM inference batches in memory. Unbounded concurrency causes out-of-memory crashes. A bounded FIFO queue guarantees system stability under traffic spikes. |
| **Progressive Text-First Rendering** | Monolithic S2S (wait for audio before showing text) | Local LLM inference takes 20–30 s; TTS takes an additional 3–5 s. Showing text immediately upon LLM completion allows the user to read while audio synthesizes, reducing perceived latency. |
| **Deterministic Regex Verbalization** | LLM-based phonetic re-prompting | Asking an LLM to rewrite text phonetically introduces hallucinations and risks dropping crucial negation words (e.g. turning "fees are non-refundable" into "fees are refundable"). Regex substitution guarantees 100% semantic fidelity. |
| **SQLite with 24h Purge** | Ephemeral memory / Redis | SQLite provides ACID transaction guarantees without running external background services. The 24-hour cleanup policy ensures compliance with data protection and privacy policies. |

---

## Next: `08-institute-agent.md` $\to$ LangGraph RAG reasoning engine deep dive
