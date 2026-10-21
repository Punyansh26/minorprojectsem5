#!/usr/bin/env bash
# 02_serve_config.sh — Tier T2 (A100/A80) serving config for the reasoning model.
#
# On T2 the T0 "free VRAM / A1" step is NOT needed: the 9B (~6.6 GB) fits with
# tens of GB to spare. What still matters:
#   * A3: keep the model resident (OLLAMA_KEEP_ALIVE=-1) so there are no reloads.
#   * Larger context / full GPU offload (default on A100).
#   * Writes a .env.colab you can source before running demo2.
#
# Usage: bash 02_serve_config.sh [MODEL_TAG]
set -uo pipefail
MODEL="${1:-qwen3.5:9b}"
WORK="/content/minor"
OUT="/content/colab_out"; mkdir -p "$OUT"

echo "=== T2 serving config for '$MODEL' ==="
echo

echo "--- GPU ---"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv 2>/dev/null || echo "no GPU visible"
echo

echo "--- Ensure model is resident and fully on GPU ---"
export OLLAMA_KEEP_ALIVE=-1
curl -s http://127.0.0.1:11434/api/version >/dev/null 2>&1 \
  || { echo "ollama not running — run 01_bootstrap.sh first"; exit 1; }
# Touch the model once so it loads.
ollama run "$MODEL" "ok" >/dev/null 2>&1 || { echo "model '$MODEL' not available; run: ollama pull $MODEL"; exit 1; }
echo "ollama ps (PROCESSOR should read 100% GPU on A100):"
ollama ps || true
echo

echo "--- Write demo2 env override (.env.colab) ---"
ENVFILE="$OUT/.env.colab"
cat > "$ENVFILE" <<EOF
# Source before running demo2 on Colab:  set -a; source $ENVFILE; set +a
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=$MODEL
OLLAMA_NUM_CTX=8192
OLLAMA_KEEP_ALIVE=-1
OLLAMA_NUM_PREDICT=512
DEMO2_CODE_ROOT=$WORK/code
# Speech on Colab: GPU is free, so Whisper can use CUDA. VITS/TTS stays CPU.
DEMO2_STT_DEVICE=cuda
DEMO2_WHISPER_MODEL=small
DEMO2_TTS_DEVICE=cpu
DEMO2_SPEECH_THREADS=4
JEV_ROUTING_MODE=off
EOF
echo "Wrote $ENVFILE"
echo

cat <<'EOF'
--- OPTIONAL: vLLM / SGLang (true T2 serving, roadmap D1/C1) ---
Ollama is fine for correctness and A3. For the *T2 throughput* wins
(prefix cache + batching + speculative decoding, ~4x decode) use vLLM:

    pip install vllm
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen2.5-7B-Instruct \        # or your 9B HF weights
        --dtype bfloat16 --gpu-memory-utilization 0.90 \
        --enable-prefix-caching --port 8000

Then point demo2 at it with an OpenAI-compatible base URL. This is a separate
task (roadmap D1) and needs the HF weights, not the GGUF. Keep Ollama as the
default unless you are specifically benchmarking the serving engine.
EOF
echo
echo "Next: bash 03_benchmark_decode.sh $MODEL"
