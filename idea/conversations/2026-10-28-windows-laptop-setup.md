# Running Demo 2 on a Windows laptop — 26–28 October 2026

The user asked for the whole repository to be explained and then run on their own laptop.
This note records the setup, the Windows-specific fixes, the measurements, and what is still
open. No commits or pushes were made in this session; the two `lib/` commits came from a teammate.

## Machine and environment

- Windows 11, NVIDIA RTX 4050 Laptop GPU (6 GB VRAM), 15.6 GB RAM. No Ollama installed.
- New Conda env **`minor`** (Python 3.11.16, `C:\Users\ASUS\anaconda3\envs\minor`). The existing
  `minor1` env (Python 3.10, transformers 5.x) was left untouched.
- Pinned to the team's tested versions: torch 2.5.1+cpu, torchaudio 2.5.1, transformers 4.46.1,
  tokenizers 0.20.3, numpy 1.26.4, sentence-transformers 3.3.1, langgraph 0.2.62,
  langchain-core 0.3.29, chromadb 0.5.23, streamlit 1.49.1, fastapi 0.115.6, uvicorn 0.34.0,
  faster-whisper 1.2.1 (ctranslate2 4.8.4), edge-tts 7.2.8, TTS 0.22.0 (pandas 1.5.3),
  plus `code/demo2/compatibility-constraints.txt`. `pip check`: no broken requirements.
- GPU runtime for Whisper only: nvidia-cublas-cu12 12.8.4.1 and nvidia-cudnn-cu12 9.10.2.21.
- Reasoning: **Groq `openai/gpt-oss-120b`** (user's choice). Free tier on this account:
  8,000 tokens/minute and 1,000 requests/day. `llama-3.3-70b-versatile` (the default in
  `institute-assistant/.env.example`) returns HTTP 404 "model does not exist" for this key.

## Problems found and fixed

| Problem | Cause | Fix |
| --- | --- | --- |
| Health check `runtime_integrity_error`: "Active release identity changed" | `core.autocrlf=true` converted the kbb serving JSON to CRLF, so content hashes no longer matched | Re-checked out `code/knowledgebaseenhanced/data/kbb/serving` with `git -c core.autocrlf=false checkout`. Git config unchanged; no diff remains |
| App could not start on Windows | `fcntl` is POSIX-only | `msvcrt` fallback in `code/demo2/storage.py` and `code/knowledgebaseenhanced/kbb/store.py` |
| Web app HTTP 500: cannot resolve `@/lib/types`, `@/lib/wavRecorder` | Root `.gitignore` line `lib/` also ignored `app/voiceagent/lib/` | Teammate committed `7e79084` (gitignore) and `1dc8899` (lib files) |
| Hindi speech unavailable | VITS checkpoints not in the checkout; Coqui TTS not installed | Teammate supplied both `best_model.pth` (≈950 MB each; Male arrived as `best_model (1).pth` and was renamed); installed TTS 0.22.0 |
| Whisper `cuda` failed: `cublas64_12.dll is not found` | No CUDA runtime DLLs; app also asked CPU-only torch whether CUDA exists | Installed cuBLAS/cuDNN (cuDNN must match the `cudnn64_9.dll` loader bundled with ctranslate2 4.8.4, version 9.10.2.21). `speech.py` now asks CTranslate2 for CUDA devices and registers the pip NVIDIA DLL folders on Windows |
| Hindi question answered "busy" twice | Review call hit Groq's per-minute limit and the 45 s maximum wait was too short | `LLM_RATE_LIMIT_MAX_WAIT_SECONDS=60` in `code/demo2/.env` |

## Files changed or added

- Modified (uncommitted): `code/demo2/storage.py`, `code/knowledgebaseenhanced/kbb/store.py`
  (Windows locking), `code/demo2/speech.py` (Whisper GPU detection), `code/demo2/app.py`
  (Answer-model default follows `LLM_PROVIDER`), `app/voiceagent/app/page.tsx` (default from
  `NEXT_PUBLIC_DEFAULT_PROVIDER`).
- New: `code/demo2/run.cmd` (Streamlit), `app/voiceagent/start.cmd` (API + Next.js).
- Gitignored, local only: `code/demo2/.env` (Groq key, `LLM_PROVIDER=groq`,
  `DEMO2_STT_DEVICE=auto`, 60 s rate-limit wait), `app/voiceagent/.env.local`,
  `app/voiceagent/node_modules`, `code/demo2/data/` (Streamlit) and `code/demo2/data/web/`
  (API server; separate because Streamlit holds the runtime lock on `data/`).
- At the user's request, unrelated local edits to 10 tracked files (`README.md`,
  `app/voiceagent/AGENTS.md`, `code/TTS/chattisgarhi-tts-models/README.md`,
  `code/demo2/{README,OPERATIONS,VALIDATION}.md` and four older `idea/conversations/` notes)
  were reverted with `git checkout`. Backup: `minorproject-reverted-changes-2026-10-28.patch`
  and `minorproject-reverted-files-2026-10-28\` on the user's Desktop.

## Running

| Service | URL | Start |
| --- | --- | --- |
| Next.js web app | http://127.0.0.1:3001 | `app/voiceagent/start.cmd` |
| Demo 2 FastAPI backend | http://127.0.0.1:8020 | started by `start.cmd` |
| Streamlit helpdesk | http://127.0.0.1:8501 | `code/demo2/run.cmd` |

All bind to 127.0.0.1 and have no login.

## Measurements (this laptop, one sample each unless stated)

- English "application fee for B.Tech": answered ₹500 non-refundable, `B TECH_2026.pdf` p10, 27.1 s.
- Hindi "हॉस्टल में कौन-कौन सी सुविधाएं हैं?": answered from `B TECH_2026.pdf` p3–4 in 44.0 s.
  Tokens: routing 1,388+205, generation 4,705+911, one 429, review 4,652+1,195 → 13,056 total.
  With `MAX_CONTEXT_CHARS=7000`: 11,512 tokens, 29.4 s, the review still hit 429.
- Groq stage times from saved web-app turns: no wait — routing 2.1 s, generation 3.0 s,
  review 2.0 s; with rate-limit waits — 1.2 s, 17.8 s, 38.5 s.
- Retrieval: 14–17 s on the first query after start (embedding model load), then 0.02–0.2 s.
- VITS on CPU: Female 5.14 s of audio in 28.9 s (includes first load); Male 6.84 s in 3.9 s.
  "₹500" verbalized as "पाँच सौ रुपये".
- Whisper `small`, 6.84 s Hindi clip, Demo 2's `speech.transcribe()` with the servers running:
  CPU first 24.5 s / warm 15.2 s; GPU first 6.4 s / warm 1.4 s. A standalone benchmark
  (no initial prompt, servers idle) gave CPU warm 3.2 s vs GPU warm 0.55 s; the gap between
  the two CPU figures was not investigated.
- Demo 2 tests (`pytest`, `test_invalid_recordings` deselected because its byte parameter
  exceeds Windows' 32,767-character environment-variable limit in `PYTEST_CURRENT_TEST`):
  188 passed, 2 skipped, 1 failed — `test_app_text_turn_rerun_and_reset` expects the default
  provider `ollama`, which `.env` now sets to `groq`.

## Findings not yet fixed

- **Groq rate limit dominates latency.** One answered turn needs ≈11–13k tokens against an
  8k/minute limit, so the review call usually waits up to ≈50 s. Options: paid Dev Tier,
  one question per minute, or running the review on `openai/gpt-oss-20b` (separate limit
  observed; untested for review quality).
- **Groq HTTP 400 on generation** (`BadRequestError`) once; it is not retried and shows the
  generic "busy" reply. The same question succeeded when rerun. Root cause not confirmed.
- **Retrieval is wording-sensitive.** The router rewrote "मेरे को इस कौलेज के फीज के बारे में
  जानना है" to "What are the fees at IIIT Naya Raipur?" (fee table on p11 not retrieved) and
  "मुझे कौलेज के प्रवेश के बारेवे जाना है" to "What are the admissions details at IIIT Naya
  Raipur?" (six faculty pages retrieved); both ended `insufficient`. "fee structure" and
  "admission process" retrieve the right pages. Likely contributors: small embedder with the
  reranker disabled, site boilerplate shared by ≈100 faculty pages, and vague queries not
  sent to clarification.
- **Local Hindi voice refuses answers containing Latin text** (IIIT, NTPC, Wi-Fi) by design.
  An Edge `hi-IN-SwaraNeural` fallback was offered, not implemented.
- VITS stays on CPU; moving it needs the CUDA torch build (≈2.4 GB) and a check that its
  bundled cuDNN does not conflict with the one used by CTranslate2.
