# Local reasoning and manual Groq selection

Demo 2 and the text helpdesk use Ollama by default. Routing, answers, grounding review,
Hindi/Hinglish pronunciation rendering and report labels use the selected provider.
Local inference requires no Groq key and never falls back to the cloud automatically.
The selected default is **Qwen3.5 9B (`qwen3.5:9b`, Q4_K_M)**. It passed the difficult
comparison cases that the smaller models failed. It trades some latency for stronger
multilingual follow-up handling; see the [validation report](LOCAL_MODEL_VALIDATION.md) for measured limits.

## Setup

On the validated machine, Ollama, `qwen3.5:9b` and its tokenizer are already installed.
Start Demo 2 with `bash run.sh` from `code/demo2`. The steps below prepare a fresh setup
or recover missing assets; no knowledge-base rebuild is required for provider switching.

Use the existing `minor` Conda environment. Do not replace its Torch, Transformers,
speech or embedding packages. Ollama runs separately from Python.

If Ollama is not already running as a service, keep this command running in a separate terminal:

```bash
ollama serve
```

From `code/Institute-voice-agent/institute-assistant`, in another terminal:

```bash
conda activate minor
ollama pull qwen3.5:9b
python setup_local.py
python run_cli.py
```

`setup_local.py` downloads only the matching tokenizer from a pinned revision, validates
it, and checks the installed Ollama model. The tokenizer is stored under
`~/.cache/institute-assistant/`, outside Git. The existing model weights, embeddings and
knowledge-base release are reused. Model weights are managed by Ollama, not Python.

Launch Demo 2 normally with `bash run.sh` from `code/demo2`. **Answer model** in the sidebar
starts on **Local · Ollama**. Select **Groq · Cloud** explicitly to use the retained cloud
configuration. Selection is per browser session and applies to subsequent submissions.
Switching models does not submit a question or create a ticket. Audio retries retain the
provider of the original turn and do not repeat the graph.

Typical measured answers took 20–50 seconds on the 8 GB RTX 4060 because some model
layers ran on CPU. The exact-repeat sample improved from 25.882 to 12.687 seconds with
cache reuse. This setup removes dependence on Groq quotas for local reasoning; it does
not establish cloud speed or quality parity. Keep other GPU workloads in mind when
comparing timings. The [validation report](LOCAL_MODEL_VALIDATION.md) records the sample sizes.

For the CLI and reports, set `LLM_PROVIDER=groq` to select Groq; its existing
`GROQ_API_KEY` and `GROQ_CHAT_MODEL` remain supported. Restart after configuration changes.
Never put a real key in the example configuration or Git.

## Configuration

| Variable | Purpose/default |
| --- | --- |
| `LLM_PROVIDER` | `ollama`; alternatively `groq` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `qwen3.5:9b` |
| `OLLAMA_NUM_CTX` | `8192` tokens |
| `OLLAMA_TIMEOUT_SECONDS` | `120` seconds per HTTP request |
| `OLLAMA_KEEP_ALIVE` | `5m` residency after use |
| `OLLAMA_TOKENIZER_PATH` | Matching cached tokenizer, derived from model family |
| `LLM_MAX_TOKENS` | Existing output limit, default `1600` |
| `DEMO2_STT_DEVICE` | `cpu`; explicit `auto`/`cuda` overrides remain available |
| `DEMO2_TTS_DEVICE` | `cpu` |

Supported setup tokenizer families are Llama 3.1, Qwen3 and Qwen3.5. A custom model
requires its matching tokenizer JSON and validation on the helpdesk questions. Tokenizer
counts include a conservative allowance for the chat template. Thinking is disabled;
repetition/presence penalties are disabled to preserve verbatim source quotations.
For grounded answers, the local output grammar limits each evidence item to its source ID
and a contiguous verbatim span from that source. This prevents rewritten or misattributed
quotes during decoding. It does not prove that the prose is supported; grounding review
and final citation validation still run.

Local requests are serialized and reuse the HTTP client and loaded model. Prompt budgeting
first removes oldest complete history pairs, then lower-ranked whole source excerpts for
generation. It reserves room for the draft and reviewed output; review never drops evidence.
An oversized mandatory prompt, failed request, malformed response or truncated output returns
`unavailable`. It does not become a knowledge-base gap or trigger a cloud request.

Answer-cache keys include provider, model, local model digest, endpoint, context size,
effective generation settings and prompt-budget version. Switching providers or replacing
an Ollama tag's model invalidates generated drafts. Retrieval reuse remains independent.
Draft hits still run grounding review. `rag_metrics` adds provider and model names; the
optional `llm_error` field contains only a safe recovery instruction.

## Verification and troubleshooting

```bash
python -m pytest -q
python evaluate_helpdesk.py --live --provider ollama --output /tmp/local-evaluation.json
python evaluate_helpdesk.py --live --provider ollama --case cache_exact --cache-benchmark
ollama ps
```

Run Demo 2's `python -m pytest -q` and `python smoke.py pipeline` separately. The evaluation
uses fixed public questions, temporary conversations/caches, and blocks action writes.
Inspect actual claims against original documents; schema/citation validity alone is not
proof of factual accuracy. Cold loading, warm reasoning and speech timings are separate.

To repeat the verified Hindi voice integration check from `code/demo2`, after speech
models are cached:

```bash
conda activate minor
GROQ_API_KEY= LLM_PROVIDER=ollama HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python smoke.py pipeline --provider ollama
```

The smoke test synthesizes its own question audio and saves the public test result in
`data/smoke/`. It verifies component integration, not microphone accuracy.

If Ollama is stopped, start its service or `ollama serve`. If the model is missing, run
`ollama pull` with the configured model tag. If the tokenizer is missing, run
`python setup_local.py`. For context/output limits, ask a narrower question or explicitly
select Groq. Check `ollama ps` for CPU offloading when responses are slow.

Hindi VITS and speech recognition are local after model setup. English/Hinglish audio still
uses online Edge TTS, even when reasoning is local. Text answers remain available if speech
fails. Chhattisgarhi understanding remains experimental.
