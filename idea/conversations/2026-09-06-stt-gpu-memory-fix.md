# GPU transcription memory fix — 2026-09-06

The user reported local STT failure. A real-model reproduction in Streamlit
exposed CUDA out-of-memory during the original float32 MMS model transfer.
A CPU mitigation was verified, but the user explicitly requested GPU instead.
The final configuration keeps STT on CUDA; CPU is not the selected fix.

Changes:
- demo/.env and defaults select DEMO_STT_DEVICE=cuda and DEMO_STT_DTYPE=float16.
- The shared MMS implementation supports STT_MMS_DTYPE (research default float32).
  It creates reduced-precision weights before moving to CUDA, then uses matching
  floating input dtype, intact integer attention masks, eval, and inference mode.
- The demo requires CUDA when selected; it does not silently run STT on CPU.
- Memory failure messages identify VRAM contention and reduced-precision settings.
- The sidebar reports the selected device. TTS retains its existing CPU setting.
- A stale duplicate demo on port 8502 held roughly 1960 MiB of GPU memory; this
  specific verified project process was stopped for restart. The updated app
  was started on localhost:8501. No unrelated model processes were terminated.

Verification on the RTX 4060 Laptop GPU:
- 49 regression tests passed in 10.38 s, including actual MCP transport, precision
  selected before CUDA transfer, floating inputs and integer attention masks.
- Real synthetic short recording: CUDA/float16, 1849 MiB allocated, 1890 MiB peak.
- Real 45-second synthetic clip: CUDA/float16, 2277 MiB peak; inference completed.
- Real MMS transcription through Streamlit's microphone handler also passed on
  CUDA/float16 using synthesized VITS input, with no Groq call.

These are functional/memory checks, not a speech-accuracy benchmark. Recordings
were synthesized for verification; no participant audio or credentials were saved.
Refresh localhost:8501 and make a new recording after the restart.
