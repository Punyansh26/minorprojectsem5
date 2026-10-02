# Notebook Test Bench Deep-Dive: End-to-End Speech-to-Speech

**Location:** [`code/Speech2Speech.ipynb`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Speech2Speech.ipynb)  
**Primary Tech Stack:** Jupyter Notebook, `websockets`, `sounddevice`, `IPython.display`, Coqui TTS, `subprocess`.

---

## 1. Purpose of the Test Bench

The [`Speech2Speech.ipynb`](file:///run/media/rtx/Files/Study/Semester%205/Minor/code/Speech2Speech.ipynb) notebook serves as the **isolated laboratory verification bench** for the project. 

In research systems, debugging a cascaded pipeline across web UI, LLM reasoning, database transactions, and audio drivers simultaneously makes it impossible to isolate failure causes. This notebook isolates the **pure acoustic layer**:
$$\text{Microphone / WAV} \xrightarrow[\text{WebSocket}]{\text{16 kHz PCM16}} \text{STT Microservice} \xrightarrow{\text{Final Text}} \text{Domain Logic} \xrightarrow{\text{Devanagari}} \text{Coqui VITS} \xrightarrow{\text{22.05 kHz WAV}} \text{Speaker}$$

It proves that real-time streaming speech recognition, VAD turn-taking, and neural TTS work end-to-end completely offline on local hardware, without external API keys or cloud dependencies.

```mermaid
flowchart TD
    subgraph Capture
        A1["Microphone Capture\n(sounddevice 16kHz)"] --> B["PCM16 Buffer"]
        A2["Reference WAV File\n(load_wav_as_pcm16)"] --> B
    end

    subgraph Streaming STT
        B -->|40ms Chunks (1280 bytes)| WS["WebSocket Client\n(ws://127.0.0.1:8000/ws/stt)"]
        WS --> STT["stt-service Subprocess\n(Silero VAD + MMS / Whisper)"]
        STT -->|Final Transcript| Recog["Recognized Text"]
    end

    subgraph Dialogue
        Recog --> Resp["Deterministic Logic\n(make_response)"]
        Resp --> Reply["Chhattisgarhi Reply Text"]
    end

    subgraph Synthesis
        Reply --> TTS["Coqui VITS Synthesizer\n(Female / Male Checkpoint)"]
        TTS --> AudioOut["22,050 Hz Audio Player\n(IPython.display.Audio)"]
    end
```

---

## 2. Cell-by-Cell Functional Breakdown

### Cell 1–3: Initialization & Repository Anchor
- Enforces execution from the repository root: verifies existence of `STT/stt-service` and `TTS/chattisgarhi-tts-models`.
- Establishes global paths: `STT_ROOT`, `TTS_ROOT`, and artifact output directory `code/speech2speech_outputs/`.
- Sets fixed protocol constants: `SAMPLE_RATE = 16000`, `CHUNK_MS = 40` (640 samples per chunk).

### Cell 4–5: Service Health Polling & Autonomous Process Spawning
- **Function:** `stt_health() -> dict | None`: Queries `http://127.0.0.1:8000/health` with a 1-second timeout.
- **Autonomous Lifecycle**: If the health check fails, the notebook automatically launches `STT/stt-service/run.py` as a background OS process via `subprocess.Popen([sys.executable, 'run.py'], cwd=STT_ROOT)`.
- It polls `stt_health()` every second with a 300-second deadline, allowing the 1-billion parameter Meta MMS model sufficient time to load into memory before continuing.

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
        ...
```
- Listens for WebSocket events concurrently:
  - Prints live `partial` events as captions.
  - Returns upon receiving the `final` event.
  - Sends `{"action": "stop"}` to cleanly close the session.

### Cell 12: Deterministic Dialogue Adapter (`make_response`)
To isolate speech pipeline performance from LLM reasoning unpredictability, the notebook employs a rule-based Chhattisgarhi responder:
```python
def make_response(user_text: str) -> str:
    # Keyword routing to validated Chhattisgarhi phrases
    if "धान" in user_text:
        return "धान के बीज हमर करा उपलब्ध हे, दू सौ पचास रुपिया पैकेट।"
    if "खाद" in user_text:
        return "यूरिया अउ डीएपी खाद गोदाम म हे।"
    return "हमर कृषि सेवा म आप मन के स्वागत हे, बताव का मदद चाही?"
```

### Cell 13–15: Speech Synthesis & Interactive Playback
- **`synthesize_response(reply_text, voice='Female', length_scale=1.0)`**:
  - Dynamically sets `tts.tts_model.length_scale = length_scale`.
  - Generates 22,050 Hz float32 audio.
  - Writes artifact to `speech2speech_outputs/{timestamp}.wav`.
  - Renders an interactive `IPython.display.Audio` widget for immediate browser playback.

### Cell 16: Safe Shutdown (`stop_stt_service`)
- Checks if the STT subprocess was spawned by the notebook kernel. If so, sends `SIGTERM`, waits for clean process exit, and releases TCP port 8000 and GPU memory.

---

## 3. Engineering Insights & Verification Value

1. **Protocol Rigor**: Proved that feeding arbitrary-length audio as 40 ms frames through Silero VAD yields exact utterance boundary detection without clipping starting or ending syllables.
2. **Memory Decoupling**: Verified that running Meta MMS-1B on CUDA (2.2 GB VRAM) alongside Coqui VITS on CPU (0 MB VRAM) runs smoothly on a standard 8 GB RTX 4060 laptop without triggering CUDA Out-Of-Memory (OOM) exceptions.
3. **Reproducibility**: Serves as the baseline test whenever underlying packages (`transformers`, `torch`, `sounddevice`) are updated.

---

## Next: `06-demo-shopping.md` $\to$ Kisan Saathi agricultural shopping assistant
