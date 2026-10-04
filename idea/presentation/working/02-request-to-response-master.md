# Request-to-Response Master Architecture & Execution Flow Guide

**Project Title:** Architecture of an Edge-Optimized, Low-Latency Voice-to-Voice Conversational Agent for Low-Resource Vernacular Dialects  
**Context:** Central Architectural Roadmap for All 4 Operational Execution Flows  
**Location:** `idea/presentation/working/02-request-to-response-master.md`

---

## 1. The Four Operational Execution Flows

The repository implements four distinct end-to-end request-to-response execution flows:

| Flow # | System Component | Primary Goal & Scope | Latency Profile | Audio In / Out Protocols |
|---|---|---|---|---|
| **Flow 1** | [STT Microservice](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/STT/stt-service) | Real-time streaming ASR with Silero VAD endpointing & barge-in | ~100–300 ms per chunk | 16 kHz PCM16 in $\to$ JSON `STTEvent` out |
| **Flow 2** | [Demo 1: Kisan Saathi](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo) | Turn-based agricultural voice shopping with FastMCP & atomic JSON | 3.2–4.5 s end-to-end | Mic PCM16 in $\to$ 22.05 kHz VITS WAV out |
| **Flow 3** | [Demo 2: Institute Helpdesk](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/demo2) | Asynchronous academic RAG with bounded workers & two-pass verification | 18.68s cold / 2.64s warm (Text) | Mic/WAV/FLAC in $\to$ VITS / Edge audio out |
| **Flow 4** | [Voice Orchestrator](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/voice-orchestrator) | PyAudio live microphone streaming client to LangGraph state machine | Streaming pipeline | Mic stream $\to$ Terminal text / TTS hook |

---

## 2. Hard Audio Contract Matrix

All audio pipelines across the repository strictly adhere to the following binary contract:

| Audio Parameter | Input Contract (ASR / STT) | Output Contract (TTS / VITS) | Telephony Path (Twilio) |
|---|---|---|---|
| **Sampling Rate** | **16,000 Hz** (16 kHz) | **22,050 Hz** (22.05 kHz) | 8,000 Hz $\to$ Resampled to 16,000 Hz |
| **Channel Count** | Mono (1 Channel) | Mono (1 Channel) | Mono (1 Channel) |
| **Bit Depth & Format** | 16-bit Signed PCM Little-Endian | 16-bit Signed PCM WAV | 8-bit G.711 $\mu$-law |
| **Header Specification** | **Raw PCM (No RIFF/WAV Header)** | Standard RIFF/WAV Header | Base64-encoded raw payload |
| **Packet Size** | 20 ms to 100 ms (typically 40 ms = 640 samples) | Sentence-level WAV buffer | 20 ms (160 bytes $\mu$-law) |
| **VAD Frame Invariant** | Exactly **512 samples** per ONNX frame | N/A | Resampled to 16 kHz $\implies$ 512 samples |

---

## 3. Flow 1: Streaming Real-Time STT Microservice

The standalone FastAPI microservice (`code/STT/stt-service/`) accepts streaming binary PCM audio over WebSockets and emits structured JSON events.

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / Browser Mic / Twilio
    participant Server as FastAPI WebSocket (server.py)
    participant Session as SttSession (session.py)
    participant VAD as SpeechDetector (vad.py)
    participant ASR as ASREngine (asr.py)
    participant Orch as Downstream Consumer / Agent

    Note over User,Server: Binary frames: 16kHz Mono 16-bit PCM
    User->>Server: Connect ws://host:8000/ws/stt/{session_id}?api_key=...
    Server->>Server: Check API key & Semaphore capacity
    alt Over Capacity or Bad Auth
        Server-->>User: JSON STTEvent(SESSION_REJECTED) & Close 4503
    else Accepted
        Server->>Session: session.start()
        Session-->>Server: STTEvent(SESSION_STARTED)
        Server-->>User: JSON text frame: SESSION_STARTED
    end

    loop While Audio Streaming
        User->>Server: Binary chunk (pcm16_bytes, 20-100ms)
        Server->>Session: process_chunk(pcm16_bytes)
        Session->>VAD: process_chunk(float32_pcm)
        Note over VAD: Splits chunk into 512-sample frames (Silero ONNX)<br/>Maintains internal residual FIFO buffer

        alt Speech Detected (Silence -> Speaking)
            VAD-->>Session: Speech Start Event
            Session-->>Server: STTEvent(SPEECH_STARTED, interrupt=True)
            Server-->>User: JSON: SPEECH_STARTED (Barge-in signal)
            Server-->>Orch: Barge-in signal (Stop active TTS playback immediately)
        end

        alt While Speaking (Periodic Interval: 700ms)
            Session->>Session: Slice trailing 6000ms (PARTIAL_WINDOW_MS)
            Session->>ASR: loop.run_in_executor(transcribe(slice, fast=True))
            Note over ASR: FasterWhisper beam=1 greedy decoding (O(1) latency)
            ASR-->>Session: Transcript(text, confidence)
            Session-->>Server: STTEvent(PARTIAL, text, confidence)
            Server-->>User: JSON: PARTIAL (Live caption update)
        end

        alt Speech Ends (Silence >= 600ms or buffer >= 20,000ms)
            VAD-->>Session: Speech End Event
            Session->>ASR: loop.run_in_executor(transcribe(full_buffer, fast=False))
            Note over ASR: MMS Devanagari CTC + clean_mms_devanagari OR Whisper beam=5
            ASR-->>Session: Transcript(text, confidence, no_speech_prob)
            alt Hallucination Check (no_speech_prob < 0.60)
                Session-->>Server: STTEvent(FINAL, text, confidence, utterance_id)
                Server-->>User: JSON: FINAL transcript
                Server-->>Orch: Consume FINAL transcript -> Trigger LLM Turn
            end
            Session->>VAD: reset() internal state
        end
    end

    User->>Server: Disconnect or {"action": "stop"}
    Server->>Session: flush()
    Server-->>User: STTEvent(SESSION_ENDED)
```

---

## 4. Flow 2: Turn-Based Voice Shopping Assistant (Demo 1)

Demo 1 (`code/demo/`) executes commercial agricultural transactions over process-isolated FastMCP tools and atomic JSON storage.

```mermaid
sequenceDiagram
    autonumber
    actor Farmer as Farmer / Voice Input
    participant UI as Streamlit UI (app.py)
    participant Voice as voice.py & local_speech.py
    participant Asst as assistant.py (Intent & Safety)
    participant Safe as KVK Safety Filter
    participant MCP as FastMCP Server (mcp_server.py)
    participant Store as shop.py (shop.json)
    participant VITS as Coqui VITS (CPU)

    Farmer->>UI: Speaks in Chhattisgarhi & clicks Stop
    UI->>UI: Compute SHA-256 of audio -> Claim token (_claim_recording)
    UI->>Voice: Downmix to mono, resample to 16kHz PCM16
    Voice->>Voice: Transcribe via Meta MMS-1B (hne fp16) + CTC matra repair
    Voice-->>UI: Chhattisgarhi Transcript: "धान बीज के दो पैकेट टोकरी म डालव"

    UI->>Asst: run_turn(user_text, cart_state)
    
    alt Shortcut Command ("टोकरी दिखाओ" / "show cart")
        Asst->>Store: view_cart(session_id) [0ms LLM compute]
    else Chemical / Disease Query ("रोग", "कीटनाशक", "spray", "dose")
        Asst->>Safe: Intercept with SAFETY_PATTERN regex
        Safe-->>UI: Pre-approved KVK Referral Template [Zero Toxic Hallucination]
    else Commercial Action
        Asst->>Asst: Call Groq / Ollama with 12 FastMCP tool schemas
        Asst->>MCP: invoke_tool("add_to_cart", {product_id: "PADDY-01", quantity: 2})
        Note over MCP,Store: Isolated stdio JSON-RPC Subprocess<br/>Acquires shop.json.lock via filelock<br/>Computes total in integer paise (₹900 = 90000 paise)<br/>Atomic write to tempfile + fsync + os.replace
        Store-->>MCP: {status: "success", cart_paise: 90000}
        MCP-->>Asst: Tool Result
    end

    Asst-->>UI: Grounded Chhattisgarhi Text: "धान बीज के 2 पैकेट टोकरी म डल गे हे।"
    
    opt Spoken Replies Enabled
        UI->>Voice: prepare_speech_text() -> "₹900" becomes "नौ सौ रुपये"
        UI->>VITS: Synthesize on CPU (length_scale=1.0)
        VITS-->>UI: 22,050 Hz WAV buffer
        UI-->>Farmer: Audio playback + cart update
    end
```

---

## 5. Flow 3: Asynchronous Academic Voice Helpdesk (Demo 2)

Demo 2 (`code/demo2/`) delivers verified academic counseling facts using bounded worker queues, 3-way hybrid retrieval, and mandatory two-pass grounding verification.

```mermaid
sequenceDiagram
    autonumber
    actor Student as Student / Parent
    participant UI as Streamlit UI (@st.fragment)
    participant JM as JobManager (jobs.py queue)
    participant Speech as speech.py (Whisper / MMS)
    participant LangGraph as LangGraph Agent (nodes.py)
    participant HybridKB as 3-Way Store (E5 + BM25 + SQLite)
    participant LLM as Ollama Reasoner (Qwen 3.5:9B)
    participant Verb as verbalization.py (v2)
    participant VITS as Coqui VITS LRU Cache

    Student->>UI: Speaks query into browser mic & clicks Stop
    UI->>JM: submit(job: audio_bytes, language, voice)
    Note over JM: Check admission queue bounds (Max 3 Queued)<br/>Verify audio (0.3s - 30s, <=12MB)
    JM-->>UI: Job Accepted (Snapshot polling begins via @st.fragment)

    Note over JM: Dedicated Reasoning Worker (demo-reasoning thread)
    JM->>Speech: decode_audio() & check RMS silence
    Speech-->>JM: Recognized text transcript

    JM->>LangGraph: ask(question, history, thread_id)
    LangGraph->>LangGraph: classify_intent_node()
    
    alt Regex Shortcut Match (Greeting / Thanks / Cancel)
        LangGraph-->>JM: Immediate static reply (0ms, 0 tokens)
    else Numerical Cutoff Query
        LangGraph->>HybridKB: Query JoSAA Relational Sidecar (facts.sqlite)
        HybridKB-->>LangGraph: Exact parameterized SQL rows (100% precision)
    else Policy / Fee / Scholarship Query
        LangGraph->>HybridKB: Reciprocal Rank Fusion (mE5 dense + BM25 sparse)
        HybridKB-->>LangGraph: Top-6 verified parent evidence chunks
    end

    LangGraph->>LLM: generate_answer_node(evidence + prompt)
    LLM-->>LangGraph: JSON candidate draft with candidate quotes
    LangGraph->>LLM: critical_review_node(draft + source_chunks)
    Note over LangGraph,LLM: Verify verbatim substring in source<br/>Reject ungrounded claims -> Honest abstention
    LangGraph-->>JM: Verified answer_text + [Page X] citations

    Note over JM,UI: PHASE 1: TEXT-FIRST UX COMPLETION (F05)<br/>UI renders verified text & citations immediately!
    JM-->>UI: Display verified answer text & sources

    opt Spoken Replies Enabled
        Note over JM: Enqueued to background speech pool (demo-speech thread)
        JM->>Verb: normalize(answer_text, language)
        Note over Verb: Currency: ₹90,000 -> नब्बे हजार रुपये<br/>Negation Guard: non-refundable -> गैर-वापसी योग्य
        Verb-->>VITS: Clean Devanagari text
        VITS->>VITS: Synthesize 22.05 kHz WAV from host CPU RAM
        VITS-->>JM: WAV byte payload
        JM-->>UI: Attach audio player & trigger browser playback
    end
```

---

## 6. Flow 4: Terminal Voice Orchestrator Client

The voice orchestrator (`code/Institute-voice-agent/voice-orchestrator/orchestrator.py`) is a lightweight streaming client connecting local audio devices to the backend STT service and LangGraph agent.

```mermaid
sequenceDiagram
    autonumber
    actor Speaker as User / Examiner
    participant Mic as sounddevice Loop (orchestrator.py)
    participant Q as Audio Queue (_audio_q)
    participant WS as STT WebSocket Client
    participant STT as STT Microservice (server.py:8000)
    participant Graph as LangGraph Engine (assistant/graph.py)
    participant TTS as Coqui VITS Synthesizer

    Speaker->>Mic: Speaks question into local microphone
    loop RawInputStream Callback (16kHz Mono int16)
        Mic->>Q: Put 40ms audio chunk (640 samples = 1,280 bytes)
    end

    loop Async Sender Task (_send_mic_audio)
        Q->>WS: Read chunk from queue
        WS->>STT: Binary WebSocket Frame (16kHz PCM16)
    end

    loop Async Receiver Loop (ws message stream)
        STT-->>WS: JSON STTEvent
        alt Event Type == "speech_started"
            Note over WS: Barge-in signal received!
            WS->>TTS: Stop active audio playback immediately
        else Event Type == "partial"
            WS->>Speaker: Terminal update: print live caption (...partial_text)
        else Event Type == "final"
            Note over WS: Complete question finalized
            WS->>Graph: invoke(question, student_id)
            Note over Graph: Classify -> Retrieve (E5+BM25) -> Generate (Qwen3.5/Groq) -> Finalize
            Graph-->>WS: result["messages"][-1].content (Answer text)
            WS->>Speaker: Terminal print: [ASSISTANT] Answer
            opt TTS Synthesis Hook
                WS->>TTS: Synthesizer.tts(text=reply, length_scale=1.0)
                TTS-->>Speaker: Play synthesized 22,050 Hz WAV audio to speakers
            end
        end
    end
```

---

## 7. Fault Tolerance & Exception Recovery Matrix

| Execution Point | Potential Failure Mode | Algorithmic / Architectural Recovery Strategy |
|---|---|---|
| **Audio Ingress** | Corrupt audio codec / zero-byte upload | Caught in `decode_audio()`; rejected before model invocation; user prompted to re-record. |
| **Silero VAD** | Arbitrary chunk sizes ($M \ne 512$) | Buffered in `_residual` FIFO; exact 512-sample evaluation prevents ONNX tensor shape crashes. |
| **Admission Queue** | Peak concurrent traffic $> \text{QUEUE\_CAPACITY}$ | JobManager raises immediate `ValueError("busy")`; UI returns graceful HTTP 429 overload cue. |
| **Ollama LLM** | Ollama daemon down or connection refused | UI exposes explicit Groq cloud fallback toggle; error message provides exact local startup command. |
| **Grounding Review** | Candidate draft quotes missing from context | Review node rejects claim (`"insufficient"`); system falls back to honest abstention & staff review ticket. |
| **FastMCP Tools** | Tool subprocess exception or syntax crash | Process boundary isolates crash; main web server remains responsive; returns structured error JSON. |
| **JSON Storage** | Abrupt power loss during file write | `shop.py` writes to `tempfile`, calls `os.fsync()`, and executes atomic `os.replace()`, preventing corrupt JSON. |
| **Neural Synthesis** | Missing Latin digits or `₹` in VITS vocab | `verbalization.py` converts currency and numbers to phonetic Devanagari words before reaching vocoder. |
