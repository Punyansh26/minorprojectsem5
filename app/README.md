# IIIT-NR Voice Helpdesk — संवाद AI (Demo 2 Web Application)

Product-grade web platform for the **IIIT Naya Raipur Voice Helpdesk (Demo 2)**, built with **Next.js 16 (App Router + TypeScript + Tailwind CSS)** and backed directly by the verified **Demo 2 FastAPI + LangGraph + Multi-Engine Speech Runtime** (`code/demo2/api_server.py`).

## Architecture & Integration

This web application integrates 100% of the Demo 2 Streamlit functionality (`code/demo2/app.py`) while elevating it into an institutional product with four integrated workspaces:

1. **🎙️ Voice & Chat Helpdesk (`/` — Helpdesk Tab)**
   - **Browser Web Audio 16 kHz Mono PCM WAV Recorder** (`lib/wavRecorder.ts`) with live 24-bar frequency equalizer, real-time RMS silence-gate indicator (`RMS ≥ 0.002`), and 0.3–30s duration enforcement, plus **WAV/FLAC Audio Upload**.
   - **Multi-Engine STT**: Local `Faster-Whisper` (`small`, int8 on CPU) for Hindi, English, and Hinglish; `Meta MMS-1B` (`hne` adapter) for experimental Chhattisgarhi.
   - **6-Node Compiled LangGraph StateGraph**: `classify_intent` → `retrieve` (3-Way Hybrid RAG: Dense `multilingual-e5-small` + Sparse `Rank-BM25` + Relational SQLite `facts.sqlite`) → `generate_answer` (Mandatory Two-Pass Grounding Verification) → `escalate` / `handle_reminder` → `finalize_turn`.
   - **Progressive Text-First Delivery**: Polls active turns every `0.5s` (`@st.fragment` parity) so verified answer text and verbatim source citations render immediately at $T_1$ while neural speech synthesis completes asynchronously in `demo-speech` at $T_2$.
   - **Dual-Engine Neural TTS & Audio-Only Retry**: Local CPU-resident **Coqui VITS** (`Female` & `Male`, 22.05 kHz WAV) for Hindi and opt-in **Microsoft Edge Neural TTS** (`Neerja`/`Prabhat`/`Swara`/`Madhur`, MP3) for English/Hinglish. Includes **Re-synthesize / Retry Audio** without re-entering the LLM graph or duplicating staff-review tickets.
2. **📊 JoSAA & CSAB Cutoff Explorer (611 Verified Rows)**
   - Multi-dimensional filtering across **Year** (2022–2026), **Authority** (JoSAA/CSAB), **Branch** (CSE, DSAI, ECE), **Quota**, **Category**, **Seat Pool**, and **Round**, with verbatim quote inspection and one-click *"Ask Agent"*.
3. **🏛️ Verified Knowledge Base & Pronunciation v2 Sandbox**
   - Browse the **722 structured institutional records** (`Fee Structure`, `Academic Calendar`, `Seat Matrix`, `Placements`, `Scholarships & PM-Vidyalaxmi`, `Faculty Directory`) and **122 SHA-256 bound official PDFs**.
   - Interactive **Deterministic Verbalization v2 (`domain-pronunciation-2`) & Hindi Negation Guard Sandbox** (`/api/py/verbalize`).
4. **⚙️ Runtime Status & Architecture Inspector**
   - Live inspection of the active KBB release (`20261014T005813186766Z`), `JobManager` admission queue (`capacity: 3`), `RagCache` hit-rate telemetry, SQLite store integrity (`conversations.sqlite`, `tickets.sqlite`, `rag_cache.sqlite`, `sessions.sqlite`), and environment/dependency versions.

## Quick Start

```bash
cd "/run/media/rtx/Files/Study/Semester 5/Minor/app/voiceagent"
bash start.sh
```

- **Web UI**: [http://localhost:3001](http://localhost:3001) (or run `npm run dev` — the Next.js API proxy at `app/api/py/[...path]/route.ts` automatically spawns the Demo 2 FastAPI backend on `http://127.0.0.1:8020` if it is not already running).
- **FastAPI Backend**: `http://127.0.0.1:8020/api/health`
