# Verification — 2026-09-18

Environment: existing Conda `minor`, Python 3.11. Shared Torch, Transformers and Coqui
versions were preserved. The missing Faster Whisper `small` model was downloaded.

## Automated checks

- **13 demo tests passed**: resampling, silence, malformed/short/long recordings, numeric
  speech-rendering guard, independent conversations, duplicate-turn suppression, consumed
  recording failures, audio-only retry, online voice routing/timeout, automatic CPU fallback
  at model load and inference, and Streamlit text interaction/reset/source display.
- **52 existing agent regression tests passed**, with 33 pre-existing Chroma/Pydantic
  deprecation warnings.

## Real component checks

- Female VITS: valid 22050 Hz WAV, about 3.65 seconds for the fixed greeting.
- Male VITS: valid 22050 Hz WAV, about 4.51 seconds for the fixed greeting.
- Whisper Hindi: produced a nonempty Devanagari transcript from local VITS audio.
- Original MMS `hne`: loaded the cached model on GPU and produced a nonempty transcript.
- English Edge voice: generated 21024 bytes of MP3; Whisper transcribed the generated
  English sentence correctly in this sample.
- Hinglish rendering and Edge voice: generated 26064 bytes of MP3; Whisper returned a
  Devanagari transcript. Some recognition errors occurred in Hindi/Hinglish/MMS samples;
  these checks establish connectivity, not language accuracy or human-listening quality.
- Live agent: the fixed B.Tech admissions question returned `answered` with two sources.
  Its claim about JEE-based merit was checked against the original FAQ page 2 and annual
  report page 21. This is a single sample, not a broad factual-quality evaluation.
- Full Hindi pipeline: VITS question audio -> Whisper -> grounded agent -> pronunciation
  rendering -> VITS response; produced a 358988-byte WAV and two source references.
- Desktop (1440×1050) and mobile (390×844) were rendered in headless Chromium and visually
  inspected. Neither viewport had horizontal overflow. The microphone widget was visible;
  a physical microphone/browser permission interaction was not tested.

## Runtime findings

Torch detects the GPU, but CTranslate2 cannot load `libcublas.so.12` on this machine.
`DEMO2_STT_DEVICE=auto` correctly falls back to CPU/int8 for Whisper while MMS can use
Torch CUDA. Existing model dependencies were not changed.

Sandbox restrictions initially blocked provider calls, model downloads, GPU access, and
local listening sockets. These checks were repeated successfully with approved access.
Provider availability, quotas and first model-load latency still affect actual demo use.
