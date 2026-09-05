# Direct microphone conversation — 5 September 2026

The user requested a button-driven speaking experience with visible speech
transcripts and AI replies, without uploading audio files. This explicitly
replaces the earlier transcript-review-and-send interaction.

Implemented in `code/demo/app.py`:

- Talk opens with the browser microphone control and instructions to press,
  speak, and stop. Stopping automatically transcribes and submits the request.
- Removed the WAV uploader and separate Transcribe action. Typing remains in
  a secondary expander. The recorder explains that stopping sends audio to Groq;
  it is disabled until an API key is supplied.
- Speech and typed requests share the same submission function. Chat labels
  spoken transcripts as **You said** and assistant responses as **AI reply**.
  Recognized speech is displayed before the assistant call and retained if it
  fails. Optional spoken replies and explicit simulated checkout confirmation
  remain available.
- A recording's file identity is claimed before provider or tool calls. Reruns
  cannot repeat that recording's cart action; a new recording can intentionally
  repeat the same request. Starting a new session uses a new recorder widget key.

Verification: `python -m pytest -q` in Conda `minor`, from `code/demo`, passed
**36 tests in 7.50 seconds** outside the sandbox (required for the existing MCP
subprocess checks). New Streamlit harness tests supply microphone/provider
doubles, execute cart changes through real MCP, and verify automatic submission,
visible transcript/reply, rerun deduplication, a second recording, and transcript
retention after assistant failure. Existing audio conversion and checkout checks
also pass. No dependencies changed.

Actual browser microphone permissions, acoustic recognition quality, and live
Groq/Edge service calls were not tested. A Groq key is still needed for live use.
This is record/stop interaction, not streaming captions or automatic endpointing.
