# Institute Assistant & Voice Orchestrator Deep-Dive: LangGraph RAG Engine

**Location:** [`code/Institute-voice-agent/`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent)  
**Primary Tech Stack:** LangGraph, LangChain, ChromaDB (`intfloat/multilingual-e5-base`), BM25, Ollama (`qwen3.5:9b`), SQLite Checkpointing, `sounddevice`, WebSockets.

---

## 1. Module Overview & Operational Thesis

The `Institute-voice-agent` directory houses two tightly integrated subsystems:
1. **`institute-assistant/`**: A production-grade Retrieval-Augmented Generation (RAG) conversational agent compiled as a **LangGraph state graph**. It resolves complex institutional inquiries regarding cutoffs, seat allocations, reservations, fees, and procedures.
2. **`voice-orchestrator/`**: A lightweight, real-time audio bridge that captures streaming microphone input, dispatches it to the STT microservice over WebSockets, and feeds finalized transcripts into the LangGraph state machine.

```mermaid
flowchart TD
    subgraph Voice Bridge (voice-orchestrator)
        Mic["Microphone\n(sounddevice 16kHz)"] --> AudioQ["Audio Queue\n(40ms Chunks)"]
        AudioQ --> WSClient["WebSocket Client"]
        WSClient --> STT["stt-service:8000\n(FastAPI Server)"]
        STT -->|Final Transcript| Orch["orchestrator.py"]
    end

    subgraph LangGraph State Machine (institute-assistant)
        Orch --> START((START))
        START --> Classify["classify_intent_node\n(Admission/Cutoff/Fees/General)"]
        
        Classify -->|knowledge| Retrieve["retrieve_node\n(Hybrid E5 Dense + BM25 Sparse RRF)"]
        Classify -->|handoff| Escalate["escalate_node\n(Human Admin Ticket)"]
        Classify -->|reminder| Reminder["handle_reminder_node\n(Date / Notification Tracking)"]
        
        Retrieve --> Generate["generate_answer_node\n(Ollama Qwen3.5 9B / Groq)"]
        Generate --> Finalize["finalize_turn_node\n(Citation Verification)"]
        Escalate --> Finalize
        Reminder --> Finalize
        Finalize --> END((END))
    end

    Finalize --> Checkpoint[("agent_memory.sqlite\n(SqliteSaver)")]
    Finalize --> Spoken["TTS Plug Point\n(Coqui VITS WAV Output)"]
```

---

## 2. LangGraph State Machine Architecture (`assistant/graph.py`)

The conversational logic is compiled via LangGraph's [`StateGraph`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/institute-assistant/assistant/graph.py#L17) around a central typed state: [`AssistantState`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/institute-assistant/assistant/state.py).

### 2.1 State Graph Nodes & Flow
1. **`classify_intent_node`**:
   - Analyzes incoming messages and classifies them into: `knowledge` (questions about the institute), `handoff` (requests for human officer contact), `reminder` (scheduling alerts for application deadlines), or `end`.
2. **`retrieve_node`**:
   - Dispatches the query to the hybrid search engine and attaches a list of [`RetrievedChunk`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/institute-assistant/assistant/retrieval.py#L16) objects to `state["context"]`.
3. **`generate_answer_node`**:
   - Synthesizes the final answer using strictly grounded context. Injects candidate citations into the prompt context.
4. **`escalate_node`**:
   - Generates an administrative ticket in `tickets.sqlite` when inquiries exceed public policy bounds.
5. **`finalize_turn_node`**:
   - Validates that every citation in the generated text corresponds to an actual retrieved chunk. Strips ungrounded claims.
6. **Persistence Checkpointer (`SqliteSaver`)**:
   - Saves multi-turn conversational history in `agent_memory.sqlite` keyed by `thread_id` (Student ID), enabling contextual follow-up questions.

---

## 3. Hybrid Retrieval Engine (`assistant/retrieval.py`)

A critical research vulnerability in standard RAG systems is semantic drift on technical acronyms and exact numeric tabular cutoffs. The retrieval engine solves this with a **three-tier hybrid search architecture**:

```mermaid
flowchart LR
    Query["User Question"] --> Dense["Dense Semantic Search\n(Multilingual E5 Base)"]
    Query --> Sparse["Sparse Lexical Search\n(Rank BM25)"]
    Query --> Tabular["Tabular Cutoff Matcher\n(JoSAA Relational Rows)"]

    Dense --> RRF["Reciprocal Rank Fusion\n(RRF Score Combination)"]
    Sparse --> RRF
    Tabular --> FinalChunks["Top-K Verified Evidence Chunks"]
    RRF --> FinalChunks
```

### 3.1 Components:
1. **Dense Semantic Embeddings**:
   - Model: `intfloat/multilingual-e5-base` (768-dimensional vectors).
   - Chunking: 350 tokens with 50-token overlap, indexed in ChromaDB (`chroma_index/`).
2. **Sparse Lexical Search (BM25)**:
   - Preserves exact keyword hits on technical codes (e.g. `OBC-NCL`, `GEN-EWS`, `DSAI`, `NTPC quota`).
3. **Reciprocal Rank Fusion (RRF)**:
   Combines dense and lexical ranks:
   $$\text{RRF}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{60 + \text{rank}_m(d)}$$
4. **Exact JoSAA Cutoff Matcher**:
   - When a query contains admission cutoff keywords, the engine queries structured relational tables to retrieve opening/closing ranks without passing through lossy text chunking.
5. **Atomic Release Pointer (`kb_state/releases/active.json`)**:
   - The knowledge base uses versioned releases managed by [`kb_pipeline.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/institute-assistant/kb_pipeline.py).
   - Document build dates are separated from administrative policy review dates. The active pointer switches atomically without re-indexing live databases.

---

## 4. LLM Reasoning Layer (`assistant/llm.py`)

- **Default Provider**: Local **Ollama** running `qwen3.5:9b`.
- **Cloud Fallback**: **Groq API** (`llama-3.3-70b-versatile` or `openai/gpt-oss-120b`).
- **Prompt Grounding**: The system prompt enforces strict citation attribution:
  ```text
  You are the official IIIT-NR admission helpdesk assistant.
  Answer using ONLY the provided verified context.
  If the context does not contain the answer, state: "मुझे इस विषय पर आधिकारिक दस्तावेज़ों में जानकारी नहीं मिली।"
  Never speculate on future seat allotments.
  ```

---

## 5. Voice Orchestrator (`voice-orchestrator/orchestrator.py`)

[`orchestrator.py`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/voice-orchestrator/orchestrator.py) is a thin streaming bridge connecting local audio hardware to remote microservices.

### Step-by-Step Execution Loop:
1. **Microphone Capture**:
   Uses `sounddevice.RawInputStream` capturing 16 kHz 16-bit mono PCM in 40 ms blocks (640 samples = 1,280 bytes).
2. **Producer/Consumer Audio Queue**:
   `_mic_callback` enqueues chunks into thread-safe `_audio_q`. An async worker coroutine (`_send_mic_audio`) pops chunks and pushes them as binary frames over WebSockets to `ws://localhost:8000/ws/stt/{student_id}`.
3. **Event Demultiplexing**:
   - On `"partial"`: Terminal prints live captions using `\r` carriage returns for immediate user feedback.
   - On `"speech_started"`: Flags barge-in to stop speaker audio.
   - On `"final"`: Extracts question string and invokes LangGraph:
     ```python
     result = graph.invoke(
         {
             "messages": [HumanMessage(content=question)],
             "student_id": student_id,
             "student_email": student_email,
             "student_category": category,
         },
         config={"configurable": {"thread_id": student_id}}
     )
     reply = result["messages"][-1].content
     ```
4. **TTS Plug Point ([`orchestrator.py#L103`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Institute-voice-agent/voice-orchestrator/orchestrator.py#L103))**:
   The response string is positioned directly at the Coqui VITS synthesizer plug-point to play synthesized audio back to the user.

---

## 6. Architecture Decisions & Rationale (Viva Defense)

| Design Choice | Alternative Considered | Engineering Rationale |
|---|---|---|
| **LangGraph State Graph** | Linear LangChain chain (`LLMChain`) | Conversational turns require conditional branching (e.g. deciding between knowledge retrieval, human officer escalation, and reminder handling). LangGraph provides explicit state persistence and branching semantics. |
| **Hybrid RRF Retrieval** | Dense Vector Search Only | Vector embeddings struggle with precise acronyms (e.g. distinguishing `CSAB Round 2` from `JoSAA Round 2` or `OBC` from `OBC-NCL`). Combining BM25 with dense E5 embeddings ensures both semantic generalization and keyword precision. |
| **Atomic Knowledge Releases** | Direct vector database upserts | Prevents vector store corruption during live re-indexing. Allows immediate one-click rollbacks if newly ingested documents contain policy errors. |
| **Thin Voice Orchestrator** | Embedding STT/TTS models directly in the RAG repo | Separates acoustic microservice deployment from domain business logic. The STT service can run on an external GPU worker while the LangGraph agent runs locally. |

---

## Next: `09-web-client-spec.md` $\to$ Modern browser client specification & audio protocols
