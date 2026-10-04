# Notebook Test Bench Deep-Dive: End-to-End Speech-to-Speech Verification

**Location:** [`code/Speech2Speech.ipynb`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Speech2Speech.ipynb)  
**Primary Tech Stack:** Jupyter Notebook, `websockets`, `sounddevice`, `IPython.display`, Coqui TTS, `subprocess`  
**Purpose:** Laboratory Test Bench for Pure Acoustic Pipeline Verification  
**Location:** `idea/presentation/working/05-notebook-bench.md`

---

## 1. Operational Role of the Laboratory Bench

The [`Speech2Speech.ipynb`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Speech2Speech.ipynb) notebook serves as the **isolated laboratory verification bench** for our voice architecture.

In research systems, debugging a cascaded pipeline across web UI, LLM reasoning, database transactions, and audio drivers simultaneously makes it impossible to isolate failure causes. This notebook isolates the **pure acoustic layer**:
$$\text{Microphone / WAV} \xrightarrow[\text{WebSocket}]{\text{16 kHz PCM16}} \text{STT Microservice} \xrightarrow{\text{Final Text}} \text{Deterministic Logic} \xrightarrow{\text{Devanagari}} \text{Coqui VITS} \xrightarrow{\text{22.05 kHz WAV}} \text{Speaker}$$

It proves that real-time streaming speech recognition, VAD turn-taking, and neural TTS work end-to-end completely offline on local hardware, without external API keys or cloud dependencies.

```mermaid
flowchart TD
    subgraph Capture ["1. Acoustic Ingestion"]
        A1["Microphone Capture\n(sounddevice 16 kHz int16)"] --> B["PCM16 Buffer"]
        A2["Reference WAV File\n(load_wav_as_pcm16)"] --> B
    end

    subgraph Streaming_STT ["2. Streaming ASR Service"]
        B -->|40ms Chunks (1,280 bytes)| WS["WebSocket Client\n(ws://127.0.0.1:8000/ws/stt)"]
        WS --> STT["stt-service Subprocess\n(Silero VAD + MMS-1B / Whisper)"]
        STT -->|Final Transcript| Recog["Recognized Text"]
    end

    subgraph Dialogue ["3. Isolated Dialogue Logic"]
        Recog --> Resp["Deterministic Logic\n(make_response)"]
        Resp --> Reply["Chhattisgarhi Reply Text"]
    end

    subgraph Synthesis ["4. Neural Synthesis"]
        Reply --> TTS["Coqui VITS Synthesizer\n(Female / Male Checkpoint)"]
        TTS --> AudioOut["22,050 Hz Audio Player\n(IPython.display.Audio)"]
    end
```

---

## 2. Cell-by-Cell Functional Breakdown

### Cell 1–3: Initialization & Repository Anchoring
- Enforces execution from the repository root: verifies existence of `STT/stt-service` and `TTS/chattisgarhi-tts-models`.
- Establishes global paths: `STT_ROOT`, `TTS_ROOT`, and artifact output directory `code/speech2speech_outputs/`.
- Sets fixed protocol constants: `SAMPLE_RATE = 16000`, `CHUNK_MS = 40` (640 samples per chunk = 1,280 bytes).

### Cell 4–5: Service Health Polling & Autonomous Process Spawning
- **Function:** `stt_health() -> dict | None`: Queries `http://127.0.0.1:8000/health` with a 1-second timeout.
- **Autonomous Lifecycle:** If the health check fails, the notebook automatically launches `STT/stt-service/run.py` as a background OS process via `subprocess.Popen([sys.executable, 'run.py'], cwd=STT_ROOT)`.
- It polls `stt_health()` every second with a 300-second deadline, allowing the 1-billion parameter Meta MMS model sufficient time to load weights into memory before continuing.

### Cell 6–7: TTS Model In-Memory Warmup
- Instantiates `Synthesizer`:
  ```python
  tts_female = Synthesizer(
      tts_checkpoint=str(TTS_ROOT / "Female" / "best_model.pth"),
      tts_config_path=str(TTS_ROOT / "Female" / "config.json"),
      use_cuda=False,  # CPU execution leaves GPU VRAM for MMS ASR
  )
  ```
- Pre-compiles the model graph by synthesizing a short test phrase, eliminating cold-start latency during live interaction.

### Cell 8–9: Audio Ingestion Utilities
1. **`load_wav_as_pcm16(path: Path) -> bytes`**:
   - Opens audio via standard `wave` module.
   - Enforces the protocol invariants: asserts 16,000 Hz sample rate, 1 channel (mono), and 2 bytes per sample (16-bit).
   - Strips the RIFF/WAV header to output raw PCM bytes.
2. **`record_from_microphone(seconds: float) -> bytes`**:
   - Uses `sounddevice.rec()` to capture live input at 16 kHz int16.
   - Converts the NumPy array directly into raw byte buffers.

### Cell 10–11: Streaming WebSocket Client Simulator (`transcribe_pcm16`)
Simulates a real-time streaming audio client:
```python
async def transcribe_pcm16(pcm16_bytes: bytes, stt_ws_url: str) -> str:
    chunk_size = int(SAMPLE_RATE * (CHUNK_MS / 1000) * 2)  # 1280 bytes
    async with websockets.connect(f"{stt_ws_url}/{uuid.uuid4()}") as ws:
        # Pushes 40ms audio chunks with asyncio.sleep(0.04) to mimic real-time cadence
        for i in range(0, len(pcm16_bytes), chunk_size):
            await ws.send(pcm16_bytes[i : i + chunk_size])
            await asyncio.sleep(0.04)
        await ws.send(json.dumps({"action": "stop"}))
        ...
```
- Listens for WebSocket events concurrently:
  - Prints live `partial` events as captions.
  - Returns upon receiving the `final` event.

### Cell 12: Deterministic Dialogue Adapter (`make_response`)
To isolate speech pipeline performance from LLM reasoning unpredictability, the notebook employs a rule-based Chhattisgarhi responder:
```python
def make_response(user_text: str) -> str:
    if "धान" in user_text:
        return "धान के बीज हमर करा उपलब्ध हे, दू सौ पचास रुपिया पैकेट।"
    if "खाद" in user_text:
        return "यूरिया अउ डीएपी खाद गोदाम म हे।"
    return "हमर कृषि सेवा म आप मन के स्वागत हे, बताव का मदद चाही?"
```

---

## 3. Architecture Decisions & Rationale (Viva Defense)

| Design Choice | Alternative Considered | Technical Rationale for Choice |
|---|---|---|
| **Isolated Test Bench** | Direct full-stack UI testing | Cascaded error analysis: allows measuring ASR Word Error Rate (WER) and TTS latency independently of LLM reasoning latency or database locks. |
| **Deterministic Responses in Bench** | Autoregressive LLM in bench | LLM generation adds non-deterministic latency ($10\text{--}20\text{ s}$). Rule-based replies ensure bench benchmarks purely reflect acoustic performance. |
| **Automated Subprocess Spawning** | Manual background terminal setup | Zero-friction reproducibility: examiners can open the notebook and click "Run All" without manually configuring external daemon processes. |
