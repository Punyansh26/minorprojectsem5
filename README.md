# Minor Project - Semester 5

**Chhattisgarhi Voice Shopping Assistant**

A voice-enabled agricultural shopping assistant that understands Chhattisgarhi language using Speech-to-Text (STT) and Text-to-Speech (TTS) pipelines.

## Current institute helpdesk demo

[Demo 2](code/demo2/README.md) is the institute helpdesk built on the shared speech
components. It defaults to **Qwen3.5 9B through local Ollama**, with Groq available by
explicit sidebar selection. English, Hindi and Hinglish questions are supported;
Chhattisgarhi remains experimental. Hindi speech is local after setup, while
English/Hinglish speech uses online Edge TTS.

On the configured machine, start it from the repository root:

```bash
cd code/demo2
bash run.sh
```

Open `http://localhost:8501`. For a fresh installation, follow the
[local model setup](code/Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md).
The [validation record](code/demo2/VALIDATION.md) covers 159 passing automated tests,
live multilingual checks and the Hindi voice pipeline. Local answers commonly took
20–50 seconds on the tested 8 GB RTX 4060; this is not a guarantee of cloud-model speed.

---

## 📂 Repository Structure

```
Minor/
├── app/       # Web client application layer
├── code/      # STS-Pipeline (ASR, FasterWhisper, MMS, TTS, WebSockets)
└── idea/      # Project proposal, agent definitions, work plan, and features
```

---

## 🔀 Branch Guide

This repository maintains dedicated branches for each component:

| Branch | Description | Direct Link |
|--------|-------------|-------------|
| `main` | Structured overview containing `app/`, `idea/`, and `code/` submodule | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/main) |
| `code` | Complete STT/TTS pipeline codebase (`STS-Pipeline`) | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/code) |
| `chattisgarhi-tts-models` | Chhattisgarhi TTS models (checkpoint and tests) | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/chattisgarhi-tts-models) |
| `idea` | Project proposals, architecture specifications, and work plans | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/idea) |
| `app` | Web application client specifications and frontend components | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/app) |

---

## 🚀 Getting Started

### Clone with all submodules:
```bash
git clone --recurse-submodules https://github.com/Punyansh26/minorprojectsem5.git
```

### Or clone a specific branch directly:
```bash
# Clone the STS Pipeline code
git clone -b code https://github.com/Punyansh26/minorprojectsem5.git

# Clone the documentation and proposal
git clone -b idea https://github.com/Punyansh26/minorprojectsem5.git
```

---

## 👥 Author

- **Punyansh26** — [GitHub Profile](https://github.com/Punyansh26) (punyansh2005@gmail.com)
