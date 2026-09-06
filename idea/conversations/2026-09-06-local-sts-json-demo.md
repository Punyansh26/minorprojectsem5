# Local STS and JSON demo integration — 2026-09-06

The user requested use of the existing .env key, STT/TTS and Speech2Speech.ipynb
components in code/demo, repair of app actions, and JSON storage instead of a DB.
This supersedes the demo's earlier API-speech/SQLite decision.

Implemented:

- Groq key loads from demo/.env on the server without re-entry or display.
- Live diagnosis: llama-3.3-70b-versatile returned HTTP 404; the same key could
  list available models. Config/default/example now use openai/gpt-oss-120b,
  which was available and successfully executed real shopping tool calls.
- Typed text is submitted as a Streamlit form. The old Send button could stay
  disabled because its enablement depended on the previous server-side text.
- Local completed-recording recognition reuses STT/stt-service/src/asr.py's
  get_engine singleton and fast=False decoding, with the existing hne/MMS config.
  This deliberately uses the existing engine directly; it does not reproduce
  the notebook's streaming WebSocket/VAD/partial-caption loop.
- TTS reuses the notebook's VITS Synthesizer/checkpoint/config/length_scale path.
  Models are loaded lazily and inference serialized across browser sessions.
  TTS defaults to CPU to leave GPU memory for MMS. Output is in-memory PCM16 WAV.
- The checkpoint lacks Latin digits and the rupee character. A speech-text
  adapter expands prices/quantities into Hindi number words, strips screen-only
  product IDs, and leaves visible grounded responses unchanged.
- JSON stores carts, stock, previews, orders, and idempotency records. Separate
  file locks plus fsync/atomic replacement protect cross-process MCP changes.
  Old SQLite files remain untouched and unused. Default state: demo/data/shop.json.
- Exact cart/checkout commands bypass Groq routing but still use actual MCP.
  Successful cart mutations stop without a redundant model reply request.
  Provider errors distinguish missing models, authentication, quotas, and connection.
- Existing in-progress browser driver edits were preserved; only JSON/configuration
  compatibility references were adjusted.

Verification (minor environment, outside sandbox where required):

- Baseline: 36 tests passed. Final: 45 tests passed in 9.32 s.
- python -m pip check: no broken requirements; no speech-stack package changes.
- Actual MCP smoke: 12 discovered tools, schema rejection, cart replay, stock,
  session isolation, confirmation capability, and checkout passed.
- Live smoke passed: synthetic VITS -> MMS hne -> Groq/MCP resolve_product and
  check_price -> local VITS WAV reply. One run measured input TTS 5140.1 ms,
  ASR 5886.3 ms, routing/tool turn 2791.2 ms, reply TTS 1022.9 ms, reply 286796 bytes.
  These are one-run integration timings, not a performance benchmark.
- Live text add request performed resolve_product -> add_to_cart and produced
  two paddy packs / 90000 paise. Rapid subsequent requests hit provider quotas;
  errors preserve cart state and report the rate limit explicitly.
- Real Chromium: search, add twice, 900-rupee total, preview, confirmation, order
  creation and cleared cart all passed against temporary JSON state.
- Real Chromium on localhost:8501 verified automatic key loading and typed form
  submission returning a 450-rupee price response. Final browser verification
  also enabled Spoken replies and confirmed the local WAV loaded in the audio
  player (readyState >= 2), two chat messages, and zero warnings. The harness
  excludes the normal MCP Connected success banner from warnings.
- Local microphone normalization and recording deduplication are covered in the
  Streamlit harness. Physical microphone permission/capture, audible playback,
  and native-speaker recognition/voice quality remain manual checks.

Run from code/demo in conda minor:

    python -m streamlit run app.py --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none

The updated app was left running on localhost:8501. Enable Spoken replies and
select Hindi or Chhattisgarhi to hear the local VITS output. English is text-only
for reply synthesis. The configured STT language is shown independently.
No notebook or separate STT server is needed. Routing still requires internet.
