# Farmer MCP demo continuation — 5 September 2026

## Scope recovered from the workspace

`code/demo/AGENTS.md` records authorization for a separate Streamlit/Groq/MCP
shopping prototype. Its implementation, fixtures, local skills, and tests were
already present. The README and smoke script referenced by those skills were
missing. This continuation completed those artifacts and verified the demo in
the existing `minor` Conda environment.

## Changes

- Added `code/demo/README.md`: setup, configuration, presentation walkthrough,
  real MCP architecture, verification commands, state behavior, and limitations.
- Added `code/demo/smoke_demo.py`: temporary-database protocol check with actual
  discovery, schema rejection, cart writes/replay, session isolation, ambiguity,
  unavailable stock, unverified-rate rejection, and confirmed checkout/replay.
  Optional `--live` checks a synthetic Hindi speech → Groq → MCP → speech path.
- Fixed app startup: Streamlit 1.49.1 does not accept the supplied `sample_rate`
  argument on `st.audio_input`.
- Inspected the installed Streamlit frontend and found that WAV conversion uses
  the browser AudioContext's sample rate. Added `prepare_recording` to downmix
  mono/stereo PCM16 microphone input and resample it to mono 16 kHz before the
  existing transcription validator. Uploaded WAV files retain strict validation.
  Declared the existing NumPy/SciPy dependencies and added audio regressions.

## Measured verification

Environment: `/home/rtx/miniconda3/envs/minor/bin/python`, Python 3.11.15;
Streamlit 1.49.1, MCP 1.12.4, Groq 0.37.1, Edge TTS 7.2.8, NumPy 1.26.4.

Commands run from `code/demo`:

| Check | Result |
| --- | --- |
| `python -m pytest -q` after all fixes | **34 passed in 5.72 seconds** |
| `python smoke_demo.py` | **Passed**, 12 discovered tools, MCP protocol `2025-06-18`, 12 recorded calls, ₹900.00 confirmed simulated cart; 882.8 ms for this run |
| `python -m pip check` after dependency declaration | **No broken requirements found** |
| Root and code-submodule `git diff --check` | Passed for tracked changes |
| Live-check function without a key | Reported skipped: `GROQ_API_KEY is not configured` |

The sandbox initially caused MCP initialization to time out after 20 seconds.
The same transport test passed outside the sandbox in 0.78 seconds. Full MCP/UI
verification subsequently ran outside the sandbox with approval. The full suite
then exposed the real Streamlit startup incompatibility, which was fixed before
the successful final run. The upstream Pydantic settings warning about FastMCP's
`lifespan` annotation remains nonfatal; shared packages were not upgraded.

The Streamlit application harness exercised catalogue → add → preview → confirm
using real MCP subprocess calls. The audio regressions check 44.1 kHz mono,
48 kHz stereo, and 16 kHz mono conversion, preserving duration and a 440 Hz
synthetic tone, plus malformed/silent/truncated/overlong input rejection.

## Outstanding external validation

No Groq key was configured, so live Groq routing/transcription and Edge TTS were
not verified. The optional live smoke implementation is present but its provider
path remains untested. No actual microphone permission, browser playback, or
native-speaker Chhattisgarhi quality check was performed. These measurements do
not establish speech accuracy, native Chhattisgarhi support, or research S2S
latency. The demo still uses Hindi fallback, draft templates, synthetic catalogue
facts, simulated orders, and an unvalidated conservative safety guard.

All changes remain local; no commits, pushes, or deployments were performed.
