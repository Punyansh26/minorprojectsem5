# References ledger

Every external claim in the FutureWork documents cites an ID from this ledger.
**Checked** records how the source was verified on 2026-10-05:
`fetched` = page or paper read directly; `snippet` = title/abstract/claims confirmed through
a search result only (numbers from `snippet` sources are quoted from the abstract or README
text shown, and should be re-read before reuse in a paper). Licence is that of the code or
weights where stated by the source; `?` = not stated or not checked.
Licences marked ⚠ are non-permissive (GPL/AGPL/non-commercial/RAIL) and need review before
any commercial deployment.

Internal repository evidence is cited by path, not by ID.

## Voice-agent latency and pipelines

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R01 | Building Enterprise Realtime Voice Agents from Scratch: A Technical Tutorial | 2026 | https://arxiv.org/abs/2603.05413 | — | ? | snippet |
| R02 | The Voice Agent Latency Playbook: Instrument, Diagnose, Fix (HF community blog) | 2026 | https://huggingface.co/blog/dvalle08/voice-agent-latency-playbook | linked Open Voice Agent | ? | fetched |
| R03 | Pipecat — open-source framework for realtime voice/multimodal agents | 2024– | — | https://github.com/pipecat-ai/pipecat | BSD-2 | snippet |
| R04 | Smart Turn v3 — audio end-of-turn model (Whisper-Tiny encoder + classifier, ONNX, CPU) | 2025– | https://github.com/pipecat-ai/smart-turn | https://huggingface.co/pipecat-ai/smart-turn-v3 | BSD-2 | snippet |
| R05 | LiveKit Agents — turn detector (audio + semantic EOT model) | 2025– | https://docs.livekit.io/agents/logic/turns/turn-detector/ | https://huggingface.co/livekit/turn-detector | ? (open weights, check model licence) | snippet |
| R06 | LiveKit Agents — turn handling / preemptive generation options | 2025– | https://docs.livekit.io/agents/logic/turns/tuning/ | https://github.com/livekit/agents | Apache-2.0 | snippet |
| R07 | voice-turn-detection — English/Hindi/Hinglish audio turn classifier | 2026 | — | https://huggingface.co/vedants254/voice-turn-detection | ? | snippet |
| R89 | Silero VAD | 2021– | — | https://github.com/snakers4/silero-vad | MIT | snippet |
| R92 | OpenTelemetry semantic conventions for GenAI; Langfuse (self-hostable tracing) | 2024– | https://opentelemetry.io/docs/specs/semconv/gen-ai/ | https://github.com/langfuse/langfuse | Apache-2.0 / MIT (core) | snippet |
| R94 | Dograh — Speech latency in voice AI (production averages, streaming STT floor) | 2026 | https://dograh.com/hub/blogs/speech-latency | https://github.com/dograh-hq/dograh | ? | snippet |

## Speech recognition

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R08 | WhisperLiveKit — real-time local STT (SimulStreaming / WhisperStreaming backends) | 2025– | — | https://github.com/QuentinFuxa/WhisperLiveKit | MIT (check backends) | snippet |
| R09 | SimulStreaming (AlignAtt simultaneous Whisper) | 2025 | https://github.com/ufal/SimulStreaming | same | ? | snippet |
| R10 | WhisperLive (Collabora) | 2023– | — | https://github.com/collabora/WhisperLive | MIT | snippet |
| R11 | faster-whisper (CTranslate2) | 2023– | — | https://github.com/SYSTRAN/faster-whisper | MIT | snippet |
| R12 | IndicConformer — ASR for 22 Indian languages (AI4Bharat) | 2024– | https://arxiv.org/abs/2403.01926 (IndicVoices) | https://github.com/AI4Bharat/IndicConformerASR | MIT (check weights) | snippet |
| R13 | Vistaar: Diverse Benchmarks and Training Sets for Indian Language ASR (IndicWhisper) | 2023 | https://arxiv.org/abs/2305.15386 | https://github.com/AI4Bharat/vistaar | MIT | snippet |
| R14 | Whisper-Hindi2Hinglish (Oriserve) | 2025 | — | https://github.com/OriserveAI/Whisper-Hindi2Hinglish | Apache-2.0 (check) | snippet |
| R15 | Canary-1B-v2 & Parakeet-TDT-0.6B-v3: multilingual ASR/AST | 2025 | https://arxiv.org/abs/2509.14128 | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 | CC-BY-4.0 | snippet |
| R16 | Scaling Speech Technology to 1,000+ Languages (MMS) | 2023 | https://arxiv.org/abs/2305.13516 | https://huggingface.co/facebook/mms-1b-all | CC-BY-NC-4.0 ⚠ | snippet |

## Streaming / speech-aware retrieval and dual-agent designs

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R17 | Stream RAG: Instant and Accurate Spoken Dialogue Systems with Streaming Tool Usage | 2025 | https://arxiv.org/abs/2510.02044 | — | — | snippet |
| R18 | When Does Streaming Tool Use Help? Tool-Intent Stabilization in Streaming RAG | 2026 | https://arxiv.org/abs/2606.20113 | — | — | snippet |
| R19 | VoiceAgentRAG: Solving the RAG Latency Bottleneck with Dual-Agent Architectures | 2026 | https://arxiv.org/abs/2603.02206 | open-source (per abstract) | ? | snippet |
| R20 | Thinking While Speaking: Inference-Time Knowledge Transfer for Conversational Voice Agents | 2025 | https://arxiv.org/abs/2511.07397 | — | — | snippet |
| R21 | MoshiRAG: Asynchronous Knowledge Retrieval for Full-Duplex Speech LMs | 2026 | https://arxiv.org/abs/2604.12928 | — | — | snippet |
| R22 | VoxRAG: Toward Transcription-Free RAG in Spoken QA | 2025 | https://arxiv.org/abs/2505.17326 | — | — | snippet |
| R23 | WavRAG: Audio-Integrated RAG for Spoken Dialogue Models | 2025 | https://arxiv.org/abs/2502.14727 | — | — | snippet |
| R24 | Toward Low-Latency End-to-End Voice Agents for Telecommunications | 2025 | https://arxiv.org/abs/2508.04721 | — | — | snippet |

## Verification, routing and caching

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R25 | MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents (EMNLP 2024) | 2024 | https://arxiv.org/abs/2404.10774 | https://github.com/Liyan06/MiniCheck | MIT (Bespoke-7B: check) | snippet |
| R26 | LettuceDetect / TinyLettuce: span-level hallucination detection for RAG | 2025 | https://arxiv.org/abs/2502.17125 | https://github.com/KRLabsOrg/LettuceDetect | MIT | snippet |
| R27 | HHEM-2.1-Open (Vectara hallucination evaluation model) | 2024 | — | https://huggingface.co/vectara/hallucination_evaluation_model | Apache-2.0 | snippet |
| R28 | rag-rack blog: verified RAG with HHEM + MiniCheck ensemble | 2026 | https://github.com/firish/rag-rack/blob/main/blog/03_verified_rag.md | same | ? | snippet |
| R29 | Laya — non-autoregressive "System 1" typed-decision model | 2026 | https://github.com/NandhaKishorM/laya | https://huggingface.co/convaiinnovations/laya | ? | snippet |
| R30 | Independent reproduction and calibration study of Laya Typed-Decisions | 2026 | https://arxiv.org/abs/2609.33843 | — | — | snippet |
| R31 | FrugalGPT: How to Use LLMs While Reducing Cost and Improving Performance | 2023 | https://arxiv.org/abs/2305.05176 | https://github.com/stanford-futuredata/FrugalGPT | Apache-2.0 | snippet |
| R32 | RouteLLM: Learning to Route LLMs with Preference Data | 2024 | https://arxiv.org/abs/2406.18665 | https://github.com/lm-sys/RouteLLM | Apache-2.0 | snippet |
| R33 | Adaptive-RAG: Adapting Retrieval-Augmented LLMs through Question Complexity | 2024 | https://arxiv.org/abs/2403.14403 | https://github.com/starsuzi/Adaptive-RAG | ? | snippet |
| R53 | Speculative RAG: Enhancing RAG through Drafting | 2024 | https://arxiv.org/abs/2407.08223 | — | — | snippet |
| R57 | vCache: Verified Semantic Prompt Caching | 2025 | https://arxiv.org/abs/2502.03771 | https://github.com/vcache-project/vCache | ? | snippet |
| R58 | Krites: Asynchronous Verified Semantic Caching for Tiered LLM Architectures | 2026 | https://arxiv.org/abs/2602.13165 | — | — | snippet |
| R59 | Category-Aware Semantic Caching for Heterogeneous LLM Workloads | 2025 | https://arxiv.org/abs/2510.26835 | — | — | snippet |
| R60 | Defending LLM Semantic Caches Against Poisoning | 2026 | https://arxiv.org/abs/2609.35908 | — | — | snippet |

## Retrieval and embeddings

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R34 | Qwen3 Embedding: Advancing Text Embedding and Reranking (0.6B/4B/8B) | 2025 | https://arxiv.org/abs/2506.05176 | https://github.com/QwenLM/Qwen3-Embedding | Apache-2.0 | snippet |
| R35 | EmbeddingGemma: Powerful and Lightweight Text Representations (308M, MRL 768→128) | 2025 | https://arxiv.org/abs/2509.20354 | https://huggingface.co/google/embeddinggemma-300m | Gemma terms ⚠ | snippet |
| R36 | BGE M3-Embedding (dense + sparse + multi-vector, 100+ languages) | 2024 | https://arxiv.org/abs/2402.03216 | https://github.com/FlagOpen/FlagEmbedding | MIT | snippet |
| R37 | Multilingual E5 Text Embeddings: A Technical Report | 2024 | https://arxiv.org/abs/2402.05672 | https://huggingface.co/intfloat/multilingual-e5-small | MIT | snippet |
| R38 | Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models | 2024 | https://arxiv.org/abs/2409.04701 | https://github.com/jina-ai/late-chunking | Apache-2.0 | snippet |
| R39 | Anthropic — Introducing Contextual Retrieval | 2024 | https://www.anthropic.com/news/contextual-retrieval | cookbook | — | snippet (numbers also in `code/knowledgebaseenhanced/Knowledge Base Building.md`) |
| R40 | Reconstructing Context: Evaluating Advanced Chunking Strategies (late chunking vs contextual retrieval) | 2025 | https://arxiv.org/abs/2504.19754 | — | — | snippet |
| R41 | Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods (Cormack et al., SIGIR) | 2009 | https://doi.org/10.1145/1571941.1572114 | — | — | known |

## LLM inference and serving

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R42 | Bringing K/V context quantisation to Ollama (OLLAMA_KV_CACHE_TYPE, needs flash attention) | 2024 | https://smcleod.net/2024/12/bringing-k/v-context-quantisation-to-ollama/ | https://github.com/ollama/ollama | MIT | snippet |
| R43 | llama.cpp discussion #25357 — MTP head quantization sweep and KV-budget recipe on 8 GB laptop GPU | 2026 | https://github.com/ggml-org/llama.cpp/discussions/25357 | https://github.com/ggml-org/llama.cpp | MIT | snippet |
| R44 | An Empirical Anatomy of Speculative Decoding on Consumer Hardware | 2026 | https://arxiv.org/abs/2607.17283 | — | — | snippet |
| R45 | llama.cpp issue #20643 — Qwen3.5 re-processes full prompt after mid-prompt edit | 2026 | https://github.com/ggml-org/llama.cpp/issues/20643 | — | — | snippet |
| R46 | llama.cpp issue #22615 — prompt cache on Qwen3.5-arch GGUFs | 2026 | https://github.com/ggml-org/llama.cpp/issues/22615 | — | — | snippet |
| R47 | QwenLM/Qwen3 issue #1826 — chat template breaks KV-cache reuse when enable_thinking=false | 2026 | https://github.com/QwenLM/Qwen3/issues/1826 | — | — | snippet |
| R48 | EAGLE-3: Scaling up Inference Acceleration via Training-Time Test | 2025 | https://arxiv.org/abs/2503.01840 | https://github.com/SafeAILab/EAGLE | Apache-2.0 | snippet |
| R49 | Efficient Memory Management for LLM Serving with PagedAttention (vLLM) | 2023 | https://arxiv.org/abs/2309.06180 | https://github.com/vllm-project/vllm | Apache-2.0 | snippet |
| R50 | SGLang: Efficient Execution of Structured LM Programs (RadixAttention) | 2023 | https://arxiv.org/abs/2312.07104 | https://github.com/sgl-project/sglang | Apache-2.0 | snippet |
| R51 | XGrammar: Flexible and Efficient Structured Generation Engine | 2024 | https://arxiv.org/abs/2411.15100 | https://github.com/mlc-ai/xgrammar | Apache-2.0 | snippet |
| R52 | CacheBlend: Fast LLM Serving for RAG with Cached Knowledge Fusion (EuroSys'25) | 2024 | https://arxiv.org/abs/2405.16444 | https://github.com/LMCache/LMCache | Apache-2.0 | snippet |
| R54 | LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression | 2024 | https://arxiv.org/abs/2403.12968 | https://github.com/microsoft/LLMLingua | MIT | snippet |
| R55 | Verifiability in Evidence-Aware RAG: Does Prompt Compression Preserve Citation Grounding? | 2026 | https://aclanthology.org/2026.customnlp4u-1.19.pdf | — | — | snippet |
| R56 | Prompt Compression in the Wild: Measuring Latency, Rate Adherence, and Quality | 2026 | https://arxiv.org/abs/2604.02985 | — | — | snippet |
| R90 | Qwen3.5-9B model configuration (`config.json`) | 2026 | https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/config.json | — | Apache-2.0 | fetched |

## Speech synthesis

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R61 | Kokoro-82M | 2025 | — | https://github.com/hexgrad/kokoro | Apache-2.0 | snippet |
| R62 | Piper — fast local neural TTS | 2023– | — | https://github.com/OHF-Voice/piper1-gpl (successor of rhasspy/piper) | GPL-3.0 ⚠ (old repo MIT) | to verify |
| R63 | Pocket TTS Hindi (109.5M, streaming, voice prompting) | 2026 | — | https://huggingface.co/saryps-labs/pocket-tts-hindi | ? | snippet |
| R64 | IndicF5 — polyglot Indic TTS (1417 h) | 2025 | — | https://huggingface.co/ai4bharat/IndicF5 | ? (check) | snippet |
| R65 | Indic Parler-TTS (21 languages) | 2024 | — | https://huggingface.co/ai4bharat/indic-parler-tts | Apache-2.0 | snippet |
| R66 | Praxy Voice: Commercial-class Indic TTS from a frozen non-Indic base | 2026 | https://arxiv.org/abs/2604.25441 | https://github.com/praxelhq/praxy | ? | snippet |
| R67 | VITS: Conditional VAE with Adversarial Learning for End-to-End TTS | 2021 | https://arxiv.org/abs/2106.06103 | https://github.com/coqui-ai/TTS | MPL-2.0 | known |

## Tool calling and task agents

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R68 | Less is More: Optimizing Function Calling for LLM Execution on Edge Devices | 2024 | https://arxiv.org/abs/2411.15399 | — | — | snippet |
| R69 | An LLM Compiler for Parallel Function Calling (ICML 2024) | 2023 | https://arxiv.org/abs/2312.04511 | https://github.com/SqueezeAILab/LLMCompiler | MIT | snippet |
| R70 | An LLM-Tool Compiler for Fused Parallel Function Calling | 2024 | https://arxiv.org/abs/2405.17438 | — | — | snippet |
| R71 | Parallel Decoding for Real-Time LLM Function Calling | 2026 | https://arxiv.org/abs/2603.00030 | — | — | snippet |
| R72 | Qwen-Audio-Agent Technical Report | 2026 | https://arxiv.org/abs/2609.25195 | — | — | snippet |
| R73 | An Approach to Build Zero-Shot Slot-Filling System for Industry-Grade Assistants | 2024 | https://arxiv.org/abs/2406.08848 | — | — | snippet |
| R74 | Berkeley Function-Calling Leaderboard (BFCL) | 2024– | https://gorilla.cs.berkeley.edu/leaderboard.html | https://github.com/ShishirPatil/gorilla | Apache-2.0 | snippet |
| R75 | small-llm-tool-use-bench (HF) | 2026 | https://huggingface.co/Manojb/small-llm-tool-use-bench | — | ? | snippet |
| R76 | Evaluation and Optimization of Small Language Models for Agentic Tasks on Edge Devices | 2025 | https://arxiv.org/abs/2511.22138 | — | — | snippet |
| R93 | Telephony integration: LiveKit SIP; Pipecat telephony transports | 2025– | https://docs.livekit.io/sip/ | https://github.com/livekit/sip | Apache-2.0 | snippet |

## End-to-end speech models

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R77 | Moshi: a speech-text foundation model for real-time dialogue | 2024 | https://arxiv.org/abs/2410.00037 | https://github.com/kyutai-labs/moshi | MIT/Apache code; CC-BY-4.0 weights | snippet |
| R78 | DuplexOmni — fast interaction model + pluggable System-2 layer | 2026 | — | https://github.com/MuyeHuang/DuplexOmni | ? | snippet |
| R79 | Scaling Full-Duplex Speech Models to Long, Multi-Party, Bilingual Conversation | 2026 | https://arxiv.org/abs/2609.36903 | — | — | snippet |

## Evaluation

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R80 | EVA-Bench: A New End-to-end Framework for Evaluating Voice Agents | 2026 | https://arxiv.org/abs/2605.13841 | https://github.com/ServiceNow/eva | ? | snippet |
| R81 | Benchmarking Full-Duplex Voice Agents on Real-World Domains (τ-voice) | 2026 | https://arxiv.org/abs/2603.13686 | — | — | snippet |
| R82 | Voice Agent Simulation Bench | 2026 | https://arxiv.org/abs/2607.27453 | — | — | snippet |
| R83 | A Reproducible and Verifiable Framework for Evaluating Tool-Calling LLM Agents (audio) | 2026 | https://arxiv.org/abs/2605.15104 | — | — | snippet |

## Distillation and fine-tuning

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R84 | LoRA: Low-Rank Adaptation of Large Language Models | 2021 | https://arxiv.org/abs/2106.09685 | https://github.com/huggingface/peft | Apache-2.0 | known |
| R85 | QLoRA: Efficient Finetuning of Quantized LLMs | 2023 | https://arxiv.org/abs/2305.14314 | https://github.com/artidoro/qlora | MIT | known |
| R86 | RAFT: Adapting Language Model to Domain Specific RAG | 2024 | https://arxiv.org/abs/2403.10131 | https://github.com/ShishirPatil/gorilla/tree/main/raft | Apache-2.0 | snippet |
| R87 | Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection | 2023 | https://arxiv.org/abs/2310.11511 | https://github.com/AkariAsai/self-rag | MIT | known |
| R88 | Unsloth — fast LoRA/QLoRA fine-tuning and GGUF export | 2023– | — | https://github.com/unslothai/unsloth | Apache-2.0 | snippet |

## Additional references added by individual documents

Each document may add sources it fetched while writing. They use the ID range of the
document (03 → R300–R399, 04 → R400–R499, …, 12 → R1200–R1299) and are listed below.

### Added by 03 — Speech input and turn-taking

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R300 | Smart Turn v3 blog — "Announcing Smart Turn v3 with CPU inference in just 12 ms" (Daily/Pipecat) | 2025 | https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/ | https://github.com/pipecat-ai/smart-turn | BSD-2 | fetched (HF card); blog title read |
| R301 | Smart Turn v3 model card — 8M params, Whisper-Tiny encoder + linear head, 8 MB int8 ONNX, multilingual, semantic VAD | 2025 | — | https://huggingface.co/pipecat-ai/smart-turn-v3 | BSD-2 | fetched |
| R302 | vedants254/voice-turn-detection model card — English/Hindi/Hinglish audio turn classifier, Whisper-Tiny encoder, 8 s window, 400 frames, ONNX; 93.70% overall / 93.93% Hindi / 93.66% English acc@0.5, ROC-AUC 0.9826 on smart-turn-data-v3.2-test | 2026 | — | https://huggingface.co/vedants254/voice-turn-detection ; code https://github.com/vedants254/Voice-Turn-detection | MIT | fetched |
| R303 | LiveKit turn detector docs — audio v1 (cloud) + v1-mini (local CPU); 14 languages incl. Hindi; endpointing 0.5–3.0 s default, 0.3–2.5 s with audio detector; VAD min_silence ≥ 250 ms; text detector deprecated (Qwen2.5-0.5B, 396 MB, ~50–160 ms CPU, Hindi TPR 99.4%/TNR 96.3%) | 2026 | https://livekit.com/blog/solving-end-of-turn-detection | https://github.com/livekit/agents ; https://huggingface.co/livekit/turn-detector | Apache-2.0 (SDK); LiveKit Model License ⚠ (v1-mini and text weights) | fetched |
| R304 | SimulStreaming — AlignAtt simultaneous Whisper (frame_threshold policy), ~5× faster than WhisperStreaming, SOTA IWSLT 2025, Whisper large-v3 1.5B, ≥10 GB VRAM recommended, CPU too slow for real time | 2025 | linked IWSLT 2025 system | https://github.com/ufal/SimulStreaming | MIT | fetched |
| R305 | faster-whisper README benchmark — up to 4× faster than openai/whisper same accuracy, less memory; small int8 CPU (i7-12700K, 8 threads) 1m42s / 1477 MB for 13-min audio; large-v2 int8 GPU 59 s / 2926 MB | 2026 | — | https://github.com/SYSTRAN/faster-whisper | MIT | fetched |
| R306 | Vistaar / IndicWhisper (abstract) — 59 Indian-language benchmarks; IndicWhisper lowest WER in 39/59, avg reduction 4.1 WER; fine-tuned Whisper on 10.7K h across 12 Indian languages | 2023 | https://arxiv.org/abs/2305.15386 | https://github.com/AI4Bharat/vistaar | MIT | fetched |
| R307 | Oriserve/Whisper-Hindi2Hinglish-Prime — 2B params, base whisper-large-v3; Hinglish-output WER CommonVoice 32.43 / FLEURS 28.68 / IndicVoices 60.82 (vs Whisper-L-v3 61.94 / 50.84 / 82.56); ~39% avg improvement | 2025 | — | https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Prime ; https://github.com/OriserveAI/Whisper-Hindi2Hinglish | Apache-2.0 | fetched |
| R308 | NVIDIA Parakeet-TDT-0.6B-v3 — 600M FastConformer-TDT, 25 **European** languages (Hindi NOT supported); avg WER Fleurs 11.97% / MLS 7.83% / CoVoST 11.98%; English Open-ASR mean WER 6.32, RTFx 3332; GGUF/NeMo | 2025 | https://arxiv.org/abs/2509.14128 | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 | CC-BY-4.0 | fetched |
| R309 | WhisperLiveKit — real-time local STT server bundling SimulStreaming / WhisperStreaming backends, Silero VAD, diarization; browser + Python clients | 2025 | — | https://github.com/QuentinFuxa/WhisperLiveKit | MIT (check backend licences) | snippet |
| R310 | WhisperLive (Collabora) — near-live Whisper using faster-whisper backend; WebSocket server, browser/Chrome-extension clients | 2024 | — | https://github.com/collabora/WhisperLive | MIT | snippet |
| R311 | Whisper-Streaming / whisper_streaming — LocalAgreement-n streaming policy with self-adaptive latency, faster-whisper backend | 2023 | https://aclanthology.org/2023.ijcnlp-demo.3/ | https://github.com/ufal/whisper_streaming | MIT | snippet |
| R312 | streamlit-webrtc — real-time audio/video streaming component for Streamlit (WebRTC) | 2021– | — | https://github.com/whitphx/streamlit-webrtc | MIT | snippet |
| R313 | WebRTC Acoustic Echo Cancellation (AEC3) / libwebrtc audio processing module (APM); python bindings via `webrtc-audio-processing` / `webrtcvad` ecosystem | 2011– | https://webrtc.googlesource.com/src/+/main/modules/audio_processing/ | https://github.com/xiongyihui/python-webrtc-audio-processing | BSD-3 (libwebrtc) | snippet |
| R314 | AI4Bharat IndicConformer / IndicConformerASR — CTC+RNNT Conformer ASR for 22 Indian languages incl. Hindi (`hi`) | 2024 | https://arxiv.org/abs/2403.01926 | https://github.com/AI4Bharat/IndicConformerASR ; https://huggingface.co/ai4bharat/indicconformer_stt_hi_hybrid_rnnt_large | custom AI4Bharat terms ⚠ (verify) | snippet |
| R315 | Papi et al. — "Does Simultaneous Speech Translation need Simultaneous Models?" (AlignAtt / offline-model-with-policy foundation) | 2022 | https://arxiv.org/abs/2204.03783 | — | — | snippet |
| R316 | NVIDIA Canary-1B-v2 — multilingual ASR/AST, 25 European languages (Hindi NOT supported) | 2025 | https://arxiv.org/abs/2509.14128 | https://huggingface.co/nvidia/canary-1b-v2 | CC-BY-4.0 | snippet |
| R317 | Meta MMS-1B-all `hne` (Chhattisgarhi) adapter — Wav2Vec2 CTC, language-specific adapter | 2023 | https://arxiv.org/abs/2305.13516 | https://huggingface.co/facebook/mms-1b-all | CC-BY-NC-4.0 ⚠ | snippet |

### Added by 04 — Retrieval and knowledge base

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R400 | Qwen3-Embedding-0.6B model card (1024-dim, 32k ctx, MRL 32–1024, MTEB-Multilingual mean(task) 64.33) | 2025 | https://arxiv.org/abs/2506.05176 | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B | Apache-2.0 | fetched |
| R401 | EmbeddingGemma-300M model card (MTEB-Multilingual v2: 768d 61.15, 128d 58.23; ctx 2048; MRL 768/512/256/128; QAT Q4_0 768d 60.62) | 2025 | https://arxiv.org/abs/2509.20354 | https://huggingface.co/google/embeddinggemma-300m | Gemma Terms ⚠ (gated) | fetched |
| R402 | BAAI/bge-reranker-v2-m3 model card (0.6B, XLM-RoBERTa base, multilingual cross-encoder; reranks top-100 of bge-m3 on MIRACL) | 2024 | https://arxiv.org/abs/2402.03216 | https://huggingface.co/BAAI/bge-reranker-v2-m3 | Apache-2.0 | fetched |
| R403 | jina-reranker-v2-base-multilingual (278M cross-encoder, 100+ languages, 1024-token ctx, 6× faster than v1) | 2024 | — | https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual | CC-BY-NC-4.0 ⚠ (non-commercial) | fetched |
| R404 | Qwen3-Reranker-0.6B model card (cross-encoder, 32k ctx, instruction-aware) | 2025 | https://arxiv.org/abs/2506.05176 | https://huggingface.co/Qwen/Qwen3-Reranker-0.6B | Apache-2.0 | snippet |
| R405 | Anthropic — Contextual Retrieval research note (top-20 failure 5.7%→3.7% embeddings −35%, →2.9% +BM25 −49%, →1.9% +rerank −67%) | 2024 | https://www.anthropic.com/research/contextual-retrieval | https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide | — (method) | fetched |
| R406 | Snowflake Arctic-embed 2.0 (arctic-embed-l-v2.0, ~568M, multilingual, MRL, retrieval-focused) | 2024 | https://arxiv.org/abs/2412.04506 | https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0 | Apache-2.0 | snippet |
| R407 | jina-embeddings-v3 (570M, multilingual, task LoRA, MRL 1024→32, 8192 ctx) | 2024 | https://arxiv.org/abs/2409.10173 | https://huggingface.co/jinaai/jina-embeddings-v3 | CC-BY-NC-4.0 ⚠ (non-commercial) | snippet |
| R408 | Comparative analysis: Qwen3-Embedding-0.6B vs BGE-M3 on MMTEB (64.33 vs 59.56, same param count) | 2025 | — | https://medium.com/@mrAryanKumar/comparative-analysis-of-qwen-3-and-bge-m3-embedding-models-for-multilingual-information-retrieval-72c0e6895413 | — (blog) | snippet |
| R409 | Matryoshka Representation Learning (truncatable embeddings) | 2022 | https://arxiv.org/abs/2205.13147 | https://github.com/RAIVNLab/MRL | MIT | snippet |
| R410 | mxbai-rerank-v2 (Mixedbread, multilingual cross-encoder family, Apache-2.0) | 2025 | — | https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v2 | Apache-2.0 | snippet |
| R411 | IBM Granite-Embedding-278M-multilingual (retrieval, 100+ languages) | 2024 | — | https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual | Apache-2.0 | snippet |
| R412 | binary / int8 embedding quantization + rescoring (memory 32×/4× cut, >90% recall retained with rescore) | 2024 | — | https://huggingface.co/blog/embedding-quantization | — (blog) | snippet |
| R413 | HyDE: Precise Zero-Shot Dense Retrieval without Relevance Labels (hypothetical-document embeddings) | 2022 | https://arxiv.org/abs/2212.10496 | https://github.com/texttron/hyde | Apache-2.0 | snippet |

### Added by 05 — LLM inference and serving

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R500 | Prompt Lookup Decoding (PLD) — n-gram draft from the prompt, no draft model | 2023 | — | https://github.com/apoorvumang/prompt-lookup-decoding | ? (no LICENSE file) | fetched |
| R501 | llama.cpp `examples/lookup` — Prompt Lookup Decoding demo (`ngram_min/ngram_max/n_draft`) | 2023– | — | https://github.com/ggml-org/llama.cpp/tree/master/examples/lookup | MIT | fetched |
| R502 | LLGuidance support in llama.cpp (`LLAMA_LLGUIDANCE=ON`, `%llguidance` grammars) | 2024– | — | https://github.com/ggml-org/llama.cpp/blob/master/docs/llguidance.md | MIT (llama.cpp) / Apache-2.0+MIT (llguidance) | fetched |
| R503 | LLGuidance — super-fast structured outputs library (token-mask ≈50 µs/token, 128k vocab) | 2024– | — | https://github.com/guidance-ai/llguidance | Apache-2.0 / MIT | fetched |
| R504 | llama.cpp Discussion #13606 — KV-cache reuse with llama-server (`-sps` prompt-similarity slot match) | 2025 | — | https://github.com/ggml-org/llama.cpp/discussions/13606 | MIT | fetched |
| R505 | llama.cpp Discussion #20574 — host-memory prompt caching in llama-server | 2026 | — | https://github.com/ggml-org/llama.cpp/discussions/20574 | MIT | snippet |
| R506 | llama.cpp Discussion #18244 — slot save/restore via `--slot-save-path` (`/slots/{id}?action=save`) | 2025 | — | https://github.com/ggml-org/llama.cpp/discussions/18244 | MIT | snippet |
| R507 | llama.cpp Issue #26676 — slot KV restore is a no-op after restart (restore reads file, slot stays empty) | 2026 | — | https://github.com/ggml-org/llama.cpp/issues/26676 | — | snippet |
| R508 | Ollama library — Qwen3 dense/MoE sizes (0.6b 523 MB, 1.7b 1.4 GB, 4b 2.5 GB, 8b 5.2 GB, 14b 9.3 GB, 30b 19 GB) | 2025 | — | https://ollama.com/library/qwen3 | Apache-2.0 (Qwen3) | fetched |
| R509 | quivent/qwen-mtp-research — Multi-Token-Prediction speculative decoding for Qwen3.5 in llama.cpp (hybrid attention+DeltaNet) | 2026 | — | https://github.com/quivent/qwen-mtp-research | ? | snippet |
| R510 | Generating Structured Outputs from LMs — JSONSchemaBench (Guidance/Outlines/llama.cpp/XGrammar/OpenAI/Gemini) | 2025 | https://arxiv.org/abs/2501.10868 | https://github.com/guidance-ai/jsonschemabench | ? | fetched |
| R511 | A Simple and Cost-Effective Self-Speculative Decoding Scheme for Low-Memory GPUs | 2024 | https://arxiv.org/abs/2405.20314 | — | ? | snippet |
| R512 | A CPU/GPU Heterogeneous Speculative Decoding for LLM Inference (Dovetail) | 2024 | https://arxiv.org/abs/2412.18934 | — | ? | snippet |
| R513 | ExLlamaV2 — fast quantized (EXL2) inference library | 2023– | — | https://github.com/turboderp-org/exllamav2 | MIT | snippet |
| R514 | ExLlamaV3 — EXL3 quant format and inference | 2025– | — | https://github.com/turboderp-org/exllamav3 | MIT | snippet |
| R515 | NVIDIA TensorRT-LLM — optimized LLM inference on NVIDIA GPUs (FP8/NVFP4) | 2023– | — | https://github.com/NVIDIA/TensorRT-LLM | Apache-2.0 | snippet |
| R516 | AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration | 2023 | https://arxiv.org/abs/2306.00978 | https://github.com/mit-han-lab/llm-awq | MIT | snippet |
| R517 | GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers | 2022 | https://arxiv.org/abs/2210.17323 | https://github.com/IST-DASLab/gptq | Apache-2.0 | snippet |
| R518 | Ollama FAQ — `OLLAMA_KEEP_ALIVE`, `keep_alive` request field, model residency | 2023– | — | https://github.com/ollama/ollama/blob/main/docs/faq.md | MIT | snippet |
| R519 | Ollama API — `/api/tags`, `/api/ps`, `/api/chat` fields (`prompt_eval_count`, `eval_count`) | 2023– | — | https://github.com/ollama/ollama/blob/main/docs/api.md | MIT | snippet |
| R520 | NVIDIA RTX 4060 Laptop GPU — memory bandwidth 256 GB/s specification | 2023 | — | https://www.techpowerup.com/gpu-specs/geforce-rtx-4060-mobile.c3946 | — | snippet |

### Added by 06 — Verification and caching

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R600 | Bespoke-MiniCheck-7B model card (also lists MiniCheck Flan-T5-L 0.8B, RoBERTa-L / DeBERTa-v3-L ≈0.3–0.4B; API `Model(document, sentence)->{0,1}`; >500 docs/min with vLLM on one A6000) | 2024 | https://arxiv.org/abs/2404.10774 | https://github.com/Liyan06/MiniCheck | CC-BY-NC-4.0 ⚠ (7B weights); MIT (MiniCheck repo + Flan-T5/RoBERTa/DeBERTa variants) | fetched |
| R601 | Granite Guardian 3.3 8B — grounded-factuality + RAG/tool hallucination judge, non-thinking low-latency yes/no mode; 3rd on LLM-AggreFact (avg 76.5, RAGTruth 84.3) | 2025 | https://arxiv.org/abs/2412.07724 | https://github.com/ibm-granite/granite-guardian | Apache-2.0 | fetched |
| R602 | FactCG: Enhancing Fact Checkers with Graph-Based Multi-Hop Data (FactCG-DeBERTa-L, 0.4B; LLM-AggreFact avg 75.6, RAGTruth 78.9; outperforms GPT-4o at much smaller size) | 2025 | https://arxiv.org/abs/2501.17144 | https://github.com/derenlei/FactCG | code: check repo (paper: arXiv non-exclusive) | fetched |
| R603 | TinyLettuce (KRLabs) — Ettin encoder hallucination detectors 17M/32M/68M; train-your-own pipeline | 2025 | https://arxiv.org/abs/2502.17125 | https://github.com/KRLabsOrg/LettuceDetect | MIT | fetched |
| R604 | HalluGuard: Evidence-Grounded Small Reasoning Models to Mitigate Hallucinations in RAG (4B; RAGTruth slice 84.0 BAcc, matching MiniCheck-7B at ~half params) | 2025 | https://arxiv.org/abs/2510.00880 | https://www.huggingface.co/papers/2510.00880 | ? | fetched (abstract) |
| R605 | LLM-AggreFact leaderboard (11-dataset grounded-factuality benchmark; model sizes + per-dataset balanced accuracy) | 2024– | https://aclanthology.org/2024.emnlp-main.499/ | https://github.com/Liyan06/MiniCheck | MIT (harness) | fetched |

### Added by 07 — Speech output

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R700 | sherpa-onnx — offline STT/TTS (VITS, Piper, Kokoro, Matcha) on CPU/ARM/RPi, no Internet; VoxSherpa app runs Kokoro+Piper+VITS Hindi 100% offline | 2023– | — | https://github.com/k2-fsa/sherpa-onnx | Apache-2.0 | fetched |
| R701 | Coqui TTS — VITS architecture and ONNX export (`TTS` 0.22.0 in repo) | 2021– | https://arxiv.org/abs/2106.06103 | https://github.com/coqui-ai/TTS | MPL-2.0 | snippet |
| R702 | Pocket TTS Hindi (~110M, streaming, voice-prompting) | 2026 | — | https://huggingface.co/saryps-labs/pocket-tts-hindi | ? (check card) | snippet |
| R703 | XTTS-v2 — multilingual (17 langs incl. Hindi) voice cloning TTS | 2023 | — | https://huggingface.co/coqui/XTTS-v2 | ⚠ Coqui Public Model Licence (non-commercial) | snippet |
| R704 | MeloTTS — real-time multilingual TTS (CPU) | 2024 | — | https://github.com/myshell-ai/MeloTTS | MIT | snippet |
| R705 | F5-TTS — flow-matching TTS (en/zh base; IndicF5 is the Indic fork) | 2024 | https://arxiv.org/abs/2410.06885 | https://github.com/SWivid/F5-TTS | MIT (base; check weights) | snippet |
| R706 | Chatterbox TTS (Resemble AI) — expressive English TTS | 2025 | — | https://github.com/resemble-ai/chatterbox | MIT | snippet |
| R707 | Orpheus TTS (Canopy Labs) — LLM-based 3B TTS, streaming | 2025 | — | https://github.com/canopyai/Orpheus-TTS | Apache-2.0 | snippet |
| R708 | Sesame CSM-1B — conversational speech model (English) | 2025 | — | https://huggingface.co/sesame/csm-1b | Apache-2.0 | snippet |
| R709 | Kyutai TTS / Delayed-Streams-Modeling — streaming TTS (en/fr) | 2025 | — | https://github.com/kyutai-labs/delayed-streams-modeling | CC-BY-4.0 (weights) | snippet |
| R710 | Praxy Voice — commercial-class Indic TTS from a frozen non-Indic base | 2026 | https://arxiv.org/abs/2604.25441 | https://github.com/praxelhq/praxy | ? (check) | snippet |
| R711 | Veena — Hindi/English code-mixed TTS (Maya Research, 3B) | 2025 | — | https://huggingface.co/maya-research/veena | Apache-2.0 (check) | snippet |
| R712 | UTMOS — UTokyo-SaruLab automatic MOS predictor (VoiceMOS 2022) | 2022 | https://arxiv.org/abs/2204.02152 | https://github.com/sarulab-speech/UTMOS22 | MIT | snippet |
| R713 | AI4Bharat IndicTTS (FastPitch/VITS, 13 Indian languages) | 2022– | https://arxiv.org/abs/2211.09536 | https://github.com/AI4Bharat/Indic-TTS | MIT (check weights) | snippet |
| R714 | MediaSource Extensions (MSE) — browser streaming audio API | — | https://developer.mozilla.org/en-US/docs/Web/API/Media_Source_Extensions_API | — | — | snippet |

### Added by 08 — Tool calling and task agents

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R800 | xLAM-2-3b-fc-r (and 1B/8B/32B/70B family) — multi-turn function-calling model; APIGen-MT; 70B τ-bench 56.2% > GPT-4o 52.9%; GGUF for 1B/3B/8B | 2025 | https://arxiv.org/abs/2504.03601 | https://github.com/SalesforceAIResearch/xLAM ; https://huggingface.co/Salesforce/xLAM-2-3b-fc-r | CC-BY-NC-4.0 ⚠ (research only) | fetched (model card) |
| R801 | Hammer2.1 (0.5B/1.5B/3B/7B) — on-device function calling via function masking; Qwen2.5-coder base; Google AI Edge integration | 2024 | https://arxiv.org/abs/2410.04587 | https://github.com/MadeAgents/Hammer ; https://huggingface.co/MadeAgents/Hammer2.1-1.5b | CC-BY-NC-4.0 ⚠ | fetched (model card) |
| R802 | RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation (prompt tokens −50%+, tool-selection 13.62→43.13%) | 2025 | https://arxiv.org/abs/2505.03275 | — (no public code) | arXiv non-exclusive | fetched (abstract) |
| R803 | ToolACE: Winning the Points of LLM Function Calling (8B SoTA on BFCL rivaling GPT-4; 26,507-API pool; dual-layer verification) | 2024 | https://arxiv.org/abs/2409.00920 | model + data subset public (per abstract) | paper CC-BY-NC-ND-4.0 ⚠ (check weight licence) | fetched (abstract) |
| R804 | MCP-Zero: Active Tool Discovery for Autonomous LLM Agents (98% token cut on APIBank; selects from ~3k tools / 248.1k tokens) | 2025 | https://arxiv.org/abs/2506.01056 | — | arXiv | snippet |

### Added by 09 — Distillation and fine-tuning

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R900 | mmBERT: A Modern Multilingual Encoder with Annealed Language Learning (small 140M/42M-non-embed, base 307M/110M, 1800+ langs, 8192 ctx, ModernBERT arch) | 2025 | https://arxiv.org/abs/2509.06888 | https://github.com/jhu-clsp/mmBERT | MIT | fetched |
| R901 | XLM-RoBERTa: Unsupervised Cross-lingual Representation Learning at Scale | 2019 | https://arxiv.org/abs/1911.02116 | https://huggingface.co/FacebookAI/xlm-roberta-base | MIT | snippet |
| R902 | paraphrase-multilingual-MiniLM-L12-v2 (Sentence-Transformers, 50+ langs) | 2021 | https://arxiv.org/abs/2004.09813 | https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | Apache-2.0 | snippet |
| R903 | ModernBERT: Smarter, Better, Faster, Longer encoder (8192 ctx) | 2024 | https://arxiv.org/abs/2412.13663 | https://huggingface.co/answerdotai/ModernBERT-base | Apache-2.0 | snippet |
| R904 | Ettin: open encoder/decoder suite (17M/32M/68M … ; TinyLettuce backbones) | 2025 | https://arxiv.org/abs/2507.11412 | https://huggingface.co/jhu-clsp | MIT | snippet |
| R905 | TinyLettuce: tiny Ettin hallucination detectors (17M/32M/68M) + synthetic data pipeline | 2025 | https://huggingface.co/blog/adaamko/tinylettuce | https://github.com/KRLabsOrg/LettuceDetect | MIT | fetched |
| R906 | LettuceDetect v2 (mmBERT-base encoder + Qwen-2B generative; RAGTruth training recipe, span-F1) | 2026 | https://arxiv.org/abs/2502.17125 | https://github.com/KRLabsOrg/LettuceDetect | MIT | fetched |
| R907 | MiniCheck training data (14K synthetic: 7K C2D + 7K D2C) and Flan-T5-Large <1B reaches GPT-4 | 2024 | https://arxiv.org/abs/2404.10774 | https://github.com/Liyan06/MiniCheck | Apache-2.0 (Bespoke-7B: commercial contact) ⚠ | fetched |
| R908 | Distilling Step-by-Step: smaller models outperform LLMs with less training data | 2023 | https://arxiv.org/abs/2305.02301 | https://github.com/google-research/distilling-step-by-step | Apache-2.0 | snippet |
| R909 | Sequence-Level Knowledge Distillation (Kim & Rush) | 2016 | https://arxiv.org/abs/1606.07947 | — | — | snippet |
| R910 | Distilling the Knowledge in a Neural Network (Hinton et al.; KL/temperature) | 2015 | https://arxiv.org/abs/1503.02531 | — | — | known |
| R911 | On Calibration of Modern Neural Networks (temperature scaling) | 2017 | https://arxiv.org/abs/1706.04599 | https://github.com/gpleiss/temperature_scaling | MIT | snippet |
| R912 | Whisper LoRA / PEFT fine-tuning for low-resource languages (HF PEFT guide) | 2023 | https://arxiv.org/abs/2106.09685 | https://github.com/huggingface/peft | Apache-2.0 | snippet |
| R913 | NF4 / double quantization details (QLoRA §3) | 2023 | https://arxiv.org/abs/2305.14314 | https://github.com/artidoro/qlora | MIT | known |
| R914 | GGUF format + llama.cpp quantize/convert | 2023– | — | https://github.com/ggml-org/llama.cpp | MIT | snippet |
| R915 | ONNX Runtime (encoder deployment, CPU) | 2019– | — | https://github.com/microsoft/onnxruntime | MIT | snippet |
| R916 | AI4Bharat IndicVoices / Hindi–Hinglish ASR fine-tuning corpus context | 2024 | https://arxiv.org/abs/2403.01926 | https://github.com/AI4Bharat/IndicConformerASR | MIT (check weights) | snippet |

### Added by 10 — Throughput, concurrency and telephony

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R1000 | Ollama FAQ — concurrency: `OLLAMA_NUM_PARALLEL` (default 1), `OLLAMA_MAX_LOADED_MODELS` (default 3×GPUs or 3), `OLLAMA_MAX_QUEUE` (default 512), RAM scales by NUM_PARALLEL×CONTEXT_LENGTH; 503 when overloaded | 2026 | https://docs.ollama.com/faq | https://github.com/ollama/ollama | MIT | fetched |
| R1001 | llama.cpp HTTP server README — `-np/--parallel` server slots, `-cb` continuous batching (default enabled), `--kv-unified-per-slot`, context checkpoints per slot (default 32), `/metrics` Prometheus, `/slots`, `--api-key`, `--ssl-key-file`/`--ssl-cert-file`, speculative decoding | 2026 | — | https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md | MIT | fetched |
| R1002 | Little's Law (L = λW) — queueing-theory identity | 1961 | https://doi.org/10.1287/opre.9.3.383 | — | — | known |
| R1003 | M/M/1 and M/M/c queue waiting-time formulas (Erlang-C) — standard queueing theory | — | https://en.wikipedia.org/wiki/M/M/c_queue | — | — | known |
| R1004 | LiveKit SIP — SIP↔WebRTC bridge; dial in/out, digest auth, DTMF send/read; libopus/libsoxr; Redis state; needs public IP; `prometheus_port` for autoscaling | 2025– | https://docs.livekit.io/sip/ | https://github.com/livekit/sip | Apache-2.0 | fetched |
| R1005 | Asterisk — open-source PBX / IP-PBX, dialplan, IVR, queues, SIP | 1999– | — | https://github.com/asterisk/asterisk | GPLv2 (dual commercial) ⚠ | snippet |
| R1006 | FreeSWITCH — modular softswitch / media server, SIP↔WebRTC gateway | 2006– | — | https://github.com/signalwire/freeswitch | MPL-1.1 | snippet |
| R1007 | SGLang: RadixAttention — up to 6.4× higher throughput vs state-of-the-art on agent/RAG/JSON/multi-turn tasks (same as [R50]; cited here for throughput number) | 2023/2024 | https://arxiv.org/abs/2312.07104 | https://github.com/sgl-project/sglang | Apache-2.0 | fetched |
| R1008 | vLLM / PagedAttention — 2–4× throughput at same latency vs FasterTransformer/Orca, more with longer sequences (same as [R49]; cited here for throughput number) | 2023 | https://arxiv.org/abs/2309.06180 | https://github.com/vllm-project/vllm | Apache-2.0 | fetched |
| R1009 | Pipecat — telephony transports (Twilio/Telnyx/Plivo WebSocket media, local SIP) for realtime voice agents | 2024– | https://docs.pipecat.ai/ | https://github.com/pipecat-ai/pipecat | BSD-2 | snippet |
| R1010 | Twilio Media Streams — 8 kHz G.711 μ-law audio over WebSocket (cloud, labelled comparison) | 2019– | https://www.twilio.com/docs/voice/media-streams | — | proprietary (cloud) ⚠ | snippet |
| R1011 | ITU-T G.711 — PCM of voice frequencies, 8 kHz, μ-law/A-law companding | 1972/1988 | https://www.itu.int/rec/T-REC-G.711 | — | ITU standard | known |
| R1012 | Python `audioop` (and `audioop-lts` for 3.13+) — `ulaw2lin`, `ratecv` resampling | 2024– | https://docs.python.org/3/library/audioop.html | https://github.com/AbstractUmbra/audioop-lts | PSF / MIT | known |
| R1013 | DeepSpeed-FastGen / Dynamic SplitFuse (chunked prefill) — up to 2.3× effective throughput, 2× lower latency vs vLLM on throughput-oriented serving | 2023 | https://arxiv.org/abs/2401.08671 | https://github.com/deepspeedai/DeepSpeed-MII | Apache-2.0 | snippet |
| R1014 | DistServe — disaggregating prefill and decode for goodput-optimal LLM serving (OSDI'24) | 2024 | https://arxiv.org/abs/2401.09670 | https://github.com/LLMServe/DistServe | Apache-2.0 | snippet |
| R1015 | NVIDIA MPS (Multi-Process Service) — concurrent CUDA contexts sharing one GPU | 2024– | https://docs.nvidia.com/deploy/mps/ | — | proprietary (driver) | snippet |
| R1016 | NVIDIA Triton Inference Server — dynamic batching, multi-model, concurrent model execution | 2019– | https://docs.nvidia.com/deeplearning/triton-inference-server/ | https://github.com/triton-inference-server/server | BSD-3 | snippet |
| R1017 | Locust — Python load-testing framework (user-behaviour scripting, distributed) | 2011– | https://docs.locust.io/ | https://github.com/locustio/locust | MIT | snippet |
| R1018 | k6 — Grafana load-testing tool; k6 has experimental WebSocket + gRPC support | 2017– | https://grafana.com/docs/k6/ | https://github.com/grafana/k6 | AGPL-3.0 ⚠ | snippet |
| R1019 | TRAI / DoT rules on IP-PSTN interconnect and OTT–telecom bridging in India — regulatory status uncertain; must be confirmed with a current primary source before any PSTN interconnect | — | https://www.trai.gov.in/ | — | — | not verified (flagged uncertain) |
| R1020 | Prometheus + Grafana — metrics scraping and dashboards for serving load | 2015– | https://prometheus.io/docs/ | https://github.com/prometheus/prometheus | Apache-2.0 | snippet |
| R1021 | WebRTC acoustic echo cancellation (AEC3) in libwebrtc — barge-in echo suppression | 2011– | https://webrtc.googlesource.com/src/ | https://webrtc.googlesource.com/src/ | BSD-3 | snippet |

### Added by 11 — End-to-end speech models

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R1100 | Moshi README (Mimi 12.5 Hz / 1.1 kbps / 24 kHz codec; 7B Temporal + Depth Transformer; 160 ms theoretical, 200 ms practical on L4; PyTorch bf16 needs 24 GB GPU) | 2024 | https://arxiv.org/abs/2410.00037 | https://github.com/kyutai-labs/moshi | MIT/Apache (code), CC-BY-4.0 (weights) | fetched |
| R1101 | Qwen3-Omni Technical Report (Thinker–Talker MoE; 119 text / 19 speech-in / 10 speech-out languages; multi-codebook low-latency talker) | 2025 | https://arxiv.org/abs/2509.17765 | https://github.com/QwenLM/Qwen3-Omni | Apache-2.0 (code; weights per model card) | fetched |
| R1102 | Qwen3-Omni README — minimum GPU memory table (Instruct BF16 78.85 GB for 15 s video; `disable_talker()` saves ~10 GB; speech-in list = EN/ZH/KO/JA/DE/RU/IT/FR/ES/PT/MS/NL/ID/TR/VI/Cantonese/AR/UR — **no Hindi**) | 2025 | — | https://github.com/QwenLM/Qwen3-Omni/blob/main/README.md | Apache-2.0 (code) | fetched |
| R1103 | Qwen3.5-Omni Technical Report (Hybrid-Attention MoE Thinker+Talker; 30B total / 3B active; 256k context) | 2026 | https://arxiv.org/abs/2604.15804 | https://github.com/QwenLM | ? (check model card) | snippet |
| R1104 | MiniCPM-o 2.6 model card (8B end-to-end; SigLip-400M + Whisper-medium-300M + ChatTTS-200M + Qwen2.5-7B; vision/speech/full-duplex streaming) | 2025 | — | https://huggingface.co/openbmb/MiniCPM-o-2_6 | ⚠ MiniCPM Model Licence (research free; commercial registration) | fetched |
| R1105 | GLM-4-Voice (end-to-end CN/EN speech model by Zhipu AI; emotion/intonation/rate/dialect control) | 2024 | — | https://github.com/zai-org/GLM-4-Voice | ⚠ model licence (check; GLM family terms) | snippet |
| R1106 | Kimi-Audio (open audio foundation model; evaluation kit) | 2025 | — | https://github.com/MoonshotAI/Kimi-Audio | ? (check) | snippet |
| R1107 | Step-Audio 2 Technical Report (discrete audio tokens into LM; paralinguistic/emotion-aware end-to-end speech conversation) | 2025 | https://arxiv.org/abs/2507.16632 | https://github.com/stepfun-ai/Step-Audio2 | ? (check) | snippet |
| R1108 | VITA-Audio: Fast Interleaved Cross-Modal Token Generation (first MLLM to emit audio output during the first forward pass; trained on open data only) | 2025 | https://arxiv.org/abs/2505.03739 | https://github.com/VITA-MLLM/VITA-Audio | ? (check; NeurIPS 2025) | snippet |
| R1109 | Freeze-Omni (frozen-LLM speech-in/speech-out; AR single-codebook speech decoder, streaming low-latency) | 2024 | — | https://github.com/VITA-MLLM/Freeze-Omni | ? (check) | snippet |
| R1110 | Voxtral (speech understanding LM; direct audio Q&A; 32k context, up to 40 min audio; Mini/Small variants) | 2025 | https://arxiv.org/abs/2507.13264 | https://github.com/mistralai | Apache-2.0 (Mistral open weights; verify) | snippet |
| R1111 | Shuka v1 — Sarvam/AI4Bharat Indic audio LM (Saaras v1 encoder + Llama3-8B-Instruct decoder + ~60M projector; speech-in → text; EN/HI finetune, zero-shot BN/GU/KN/ML/MR/OR/PA/TA/TE) | 2024 | — | https://huggingface.co/sarvamai/shuka_v1 | ⚠ Llama 3 Community Licence | fetched |
| R1112 | Meta AI blog — "Enlisting Llama in India's first open-source audio language model" (Shuka context; Indic voice-first) | 2025 | https://ai.meta.com/blog/sarvam-india-audio-language-model-llama/ | — | — | snippet |
| R1113 | WavRAG: Audio-Integrated RAG for Spoken Dialogue Models (first native end-to-end audio RAG; bypasses ASR for embedding+retrieval; unified audio/text knowledge) | 2025 | https://arxiv.org/abs/2502.14727 | — (ACL 2025 Long) | ? | fetched |
| R1114 | VoxRAG: transcription-free speech-to-speech RAG; retrieves audio segments directly; precision/retrieval quality remain key limitations | 2025 | https://arxiv.org/abs/2505.17326 | — | ? | fetched |
| R1115 | A Reranker for Orchestrating Heterogeneous Speech and Text Retrievers (ASR propagates transcription errors; cross-modal reranking) | 2026 | https://arxiv.org/abs/2608.26194 | — | ? | snippet |
| R1116 | Sesame CSM — Conversational Speech Model (contextual speech generation; 1B open checkpoint) | 2025 | — | https://github.com/SesameAILabs/csm | Apache-2.0 (check model card) | snippet |
| R1117 | LLaMA-Omni 2 — modular speech LM with streaming speech synthesiser on Qwen2.5 backbones (0.5B–14B) | 2025 | https://arxiv.org/abs/2505.02625 | https://github.com/ictnlp/LLaMA-Omni2 | ? (check; research) | snippet |
| R1118 | Ultravox — speech-in multimodal LM (Whisper encoder + text LLM; audio→text, no native speech out) | 2024– | — | https://github.com/fixie-ai/ultravox | MIT (check model weights) | snippet |
| R1119 | Mistral Voxtral-TTS announcement/community benchmark (3B/4B; ~3 GB RAM; 70–90 ms TTFA; 9 languages; Apache-2.0) — cloud/community numbers, not reproduced here | 2026 | — | https://huggingface.co/mistralai | Apache-2.0 (per announcement; verify) | snippet |
| R1120 | AI4Bharat IndicVoices / IndicConformer context for Indic ASR front-ends used as cascade input (cross-ref chapter 03 [R12]) | 2024 | https://arxiv.org/abs/2403.01926 | https://github.com/AI4Bharat/IndicConformerASR | MIT (check weights) | snippet |

### Added by 12 — Evaluation and benchmarking

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R1200 | RAGChecker: A Fine-grained Framework for Diagnosing RAG (claim-level precision/recall, context precision, faithfulness, hallucination) | 2024 | https://arxiv.org/abs/2408.08067 | https://github.com/amazon-science/RAGChecker | Apache-2.0 | fetched |
| R1201 | Ragas: automated RAG evaluation (faithfulness, answer relevancy, context precision/recall) | 2024 | https://arxiv.org/abs/2309.15217 | https://github.com/explodinggradients/ragas | Apache-2.0 | fetched |
| R1202 | ARES: An Automated Evaluation Framework for RAG Systems (LLM judges + PPI confidence intervals) | 2023 | https://arxiv.org/abs/2311.09476 | https://github.com/stanford-futuredata/ARES | Apache-2.0 | snippet |
| R1203 | VoiceBench: Benchmarking LLM-Based Voice Assistants (TACL 2026) | 2024 | https://arxiv.org/abs/2410.17196 | https://github.com/MatthewCYM/VoiceBench | Apache-2.0 (check) | fetched |
| R1204 | VoiceAgentBench: Are Voice Assistants ready for agentic tasks? (6000+ spoken queries, English + 6 Indic; tool selection, parameter filling) | 2025 | https://arxiv.org/abs/2510.07978 | HF dataset + code (per abstract) | CC-BY-4.0 | fetched |
| R1205 | Full-Duplex-Bench: turn-taking, pause handling, backchannel, interruption (v1); FDB-v2 multi-turn examiner | 2025 | https://arxiv.org/abs/2503.04721 ; https://arxiv.org/abs/2510.07838 | https://github.com/DanielLin94144/Full-Duplex-Bench | ? (check) | fetched |
| R1206 | τ-bench / τ²-bench (tau2-bench): tool-agent-user interaction; pass^k reliability metric; voice full-duplex + banking_knowledge RAG domain | 2024–2026 | https://arxiv.org/abs/2406.12045 | https://github.com/sierra-research/tau2-bench | MIT | fetched |
| R1207 | jiwer: WER/CER/MER/WIL computation for ASR | 2018– | — | https://github.com/jitsi/jiwer | Apache-2.0 | fetched |
| R1208 | whisper_normalizer: OpenAI-Whisper text normalizer (BasicTextNormalizer harms Indic/low-resource scoring; use IndicNormalizer) | 2023– | — | https://github.com/kurianbenoy/whisper_normalizer | MIT | fetched |
| R1209 | UTMOS / UTMOSv2: UTokyo-SaruLab automatic MOS prediction (VoiceMOS Challenge) | 2022/2024 | https://arxiv.org/abs/2204.02152 | https://github.com/sarulab-speech/UTMOS22 ; https://github.com/sarulab-speech/UTMOSv2 | MIT | fetched |
| R1210 | SpeechMOS (tarepan): 2-line UTMOS-strong MOS predictor via torch.hub | 2023– | — | https://github.com/tarepan/SpeechMOS | MIT (derived from UTMOS22) | fetched |
| R1211 | Svarah: Indian-accented English ASR benchmark (9.6 h, 117 speakers, 65 districts) | 2023 | https://arxiv.org/abs/2305.15760 | https://github.com/AI4Bharat/Svarah ; HF ai4bharat/Svarah | CC-BY-4.0 (check HF) | fetched |
| R1212 | Lahaja: a robust Hindi ASR benchmark across dialects/accents | 2024 | https://arxiv.org/abs/2408.11440 | https://huggingface.co/datasets/ai4bharat/Lahaja | CC-BY-4.0 (check) | snippet |
| R1213 | IndicVoices / Kathbath (AI4Bharat) read + spontaneous Indic speech test sets | 2023–2024 | https://arxiv.org/abs/2403.01926 | https://github.com/AI4Bharat/vistaar | MIT (code); data CC (check) | fetched |
| R1214 | FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech (102 languages, incl. hi) | 2022 | https://arxiv.org/abs/2205.12446 | https://huggingface.co/datasets/google/fleurs | CC-BY-4.0 | snippet |
| R1215 | Efron & Tibshirani, An Introduction to the Bootstrap (percentile/BCa CIs) | 1993 | — | — | known | known |
| R1216 | McNemar's test for paired nominal data (significance of change) | 1947 | https://doi.org/10.1007/BF02295996 | — | known | known |
| R1217 | Wilson score interval for a binomial proportion | 1927 | https://doi.org/10.1080/01621459.1927.10502953 | — | known | known |
| R1218 | Rule of three: 95% upper bound 3/n for 0 observed events | 1983 | https://doi.org/10.1001/jama.1983.03340130055027 | — | known | known |
| R1219 | Dror et al., The Hitchhiker's Guide to Testing Statistical Significance in NLP (ACL 2018) | 2018 | https://aclanthology.org/P18-1128/ | — | known | snippet |
| R1220 | Koehn, Statistical Significance Tests for MT Evaluation (paired bootstrap resampling) | 2004 | https://aclanthology.org/W04-3250/ | — | known | known |
| R1221 | HELM / holistic evaluation reporting discipline (multi-metric, per-scenario) | 2022 | https://arxiv.org/abs/2211.09110 | https://github.com/stanford-crfm/helm | Apache-2.0 | snippet |
| R1222 | LettuceDetect / TinyLettuce span-level hallucination detector (local checker candidate; see also [R26]) | 2025 | https://arxiv.org/abs/2502.17125 | https://github.com/KRLabsOrg/LettuceDetect | MIT | snippet |
| R1223 | NVIDIA Management Library (nvidia-smi `--query-gpu=power.draw`) for GPU energy sampling | — | https://developer.nvidia.com/management-library-nvml | — | proprietary tool | known |
| R1224 | Intel RAPL via Linux powercap (`/sys/class/powercap/intel-rapl*`) for CPU-package energy | — | https://www.kernel.org/doc/html/latest/power/powercap/powercap.html | — | GPL (kernel docs) | known |

### Added by 14–15 — Knowledge-base methodology review and pipeline v2

| ID | Title / source | Year | Paper | Code | Licence | Checked |
|---|---|---|---|---|---|---|
| R1400 | Is Semantic Chunking Worth the Computational Cost? (Vectara) | 2024 | https://arxiv.org/abs/2410.13070 | — | paper CC-BY-NC-ND | fetched |
| R1401 | Financial Report Chunking for Effective Retrieval Augmented Generation (element-based chunking, FinanceBench) | 2024 | https://arxiv.org/abs/2402.05131 | https://github.com/Unstructured-IO/unstructured | Apache-2.0 (library) | fetched |
| R1402 | NVIDIA — Finding the Best Chunking Strategy for Accurate AI Responses (page vs section vs token) | 2025 | https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/ | https://github.com/NVIDIA-AI-Blueprints/rag | Apache-2.0 | fetched |
| R1403 | Dense X Retrieval: What Retrieval Granularity Should We Use? (EMNLP 2024) | 2023 | https://arxiv.org/abs/2312.06648 | https://github.com/chentong0/factoid-wiki | ? | fetched |
| R1404 | PaddleOCR-VL: Boosting Multilingual Document Parsing via a 0.9B Ultra-Compact VLM | 2025 | https://arxiv.org/abs/2510.14528 | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0 | fetched |
| R1405 | PaddleOCR-VL-1.5: Towards a Multi-Task 0.9B VLM for Robust In-the-Wild Document Parsing | 2026 | https://arxiv.org/abs/2601.21957 | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0 | snippet |
| R1407 | olmOCR 2: Unit Test Rewards for Document OCR (olmOCR-2-7B-1025, 82.4 olmOCR-Bench, English) | 2025 | https://arxiv.org/abs/2510.19817 | https://github.com/allenai/olmocr | Apache-2.0 | snippet |
| R1408 | Docling (IBM) — document conversion, DoclingDocument, HierarchicalChunker/HybridChunker | 2024– | https://arxiv.org/abs/2408.09869 | https://github.com/docling-project/docling | MIT | snippet |
| R1409 | Granite-Docling-258M (IBM) — compact document-conversion VLM emitting DocTags | 2025 | https://www.ibm.com/granite/docs/models/docling | https://huggingface.co/ibm-granite/granite-docling-258M | Apache-2.0 | snippet |
| R1410 | Lost in OCR Translation? Vision-Based Approaches to Robust Document Retrieval | 2025 | https://arxiv.org/abs/2505.05666 | — | — | fetched |
| R1411 | ColPali: Efficient Document Retrieval with VLMs; ViDoRe Benchmark V2 | 2024–2025 | https://arxiv.org/abs/2407.01449 ; https://arxiv.org/abs/2505.17166 | https://github.com/illuin-tech/colpali | MIT code; Gemma-terms weights ⚠ | snippet |
| R1412 | VisRAG: Vision-based RAG on Multi-modality Documents | 2024 | https://arxiv.org/abs/2410.10594 | https://github.com/OpenBMB/VisRAG | ? | snippet |
| R1413 | IRPAPERS: A Visual Document Benchmark for Scientific Retrieval and QA (text vs image retrieval) | 2026 | https://arxiv.org/abs/2602.17687 | — | — | snippet |
| R1414 | jina-embeddings-v4: Universal Embeddings for Multimodal Multilingual Retrieval | 2025 | https://arxiv.org/abs/2506.18902 | https://huggingface.co/jinaai/jina-embeddings-v4 | likely CC-BY-NC ⚠ (verify) | snippet |
| R1415 | Chroma — Evaluating Chunking Strategies for Retrieval (up to 9% recall difference) | 2024 | https://research.trychroma.com/evaluating-chunking | https://github.com/brandonstarxel/chunking_evaluation | ? | snippet |
| R1416 | Question-Based Retrieval using Atomic Units for Enterprise RAG | 2024 | https://arxiv.org/abs/2405.12363 | https://github.com/VatsalRaina/QARAG | ? | snippet |
| R1417 | RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval (ICLR 2024) | 2024 | https://arxiv.org/abs/2401.18059 | https://github.com/parthsarthi03/raptor | MIT | snippet |
| R1418 | Don't Do RAG: When Cache-Augmented Generation is All You Need for Knowledge Tasks | 2024 | https://arxiv.org/abs/2412.15605 | https://github.com/hhhuang/CAG | ? | snippet |
| R1419 | Surya OCR 2 (Datalab) — 650M OCR, 90+ languages | 2026 | https://www.datalab.to/blog/surya-2 | https://github.com/datalab-to/surya | Apache-2.0 code; modified OpenRAIL-M weights ⚠ | snippet |
| R1420 | lipi — decode legacy Hindi font PDFs (KrutiDev, Chanakya, DevLys); krutiextract (PyPI) | 2025–2026 | — | https://github.com/aparsoft/lipi ; https://pypi.org/project/krutiextract/ | ? | snippet |
| R1422 | Structure-Aware Semantic Chunking with Title-Chain Prefixes: A 1600-Query Evaluation | 2026 | https://arxiv.org/abs/2608.00824 | — | — | snippet |
| R1423 | A Systematic Analysis of Chunking Strategies for Reliable Question Answering | 2026 | https://arxiv.org/abs/2601.14123 | — | — | snippet |
| R1424 | MinerU 3.x release notes (MinerU2.5-Pro 1.2B VLM, cross-page table merging, PPTX/XLSX, licence change from AGPLv3) | 2026 | https://github.com/opendatalab/MinerU | https://github.com/opendatalab/MinerU | MinerU Open Source License (Apache-2.0-based, extra terms) | snippet |
