#!/usr/bin/env bash
# Levanta Gemma 4 26B-A4B y Qwen 3.5-9B vía vLLM.
#
# Asume:
# - Python venv con vllm instalado (uv sync --extra llm-local en
#   apps/backend/).
# - CUDA 12.x y drivers NVIDIA disponibles.
# - Los pesos descargados (HuggingFace cache).
#
# Uso: ./start-vllm.sh

set -euo pipefail

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"

# TODO: confirmar el nombre exacto del modelo en HuggingFace cuando
# se elija el checkpoint final (Q4 / Q5, AWQ / GPTQ, etc.).
GEMMA_MODEL="${GEMMA_MODEL:-google/gemma-4-26b-a4b}"
QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-9B-Instruct}"

echo "[vllm] arrancando Gemma en :8000..."
nohup vllm serve "$GEMMA_MODEL" \
    --port 8000 \
    --max-model-len 128000 \
    --gpu-memory-utilization 0.45 \
    --served-model-name gemma-4-26b-a4b \
    > "$LOG_DIR/vllm-gemma.log" 2>&1 &
echo $! > "$LOG_DIR/vllm-gemma.pid"

echo "[vllm] arrancando Qwen en :8001..."
nohup vllm serve "$QWEN_MODEL" \
    --port 8001 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.45 \
    --served-model-name qwen-3.5-9b \
    > "$LOG_DIR/vllm-qwen.log" 2>&1 &
echo $! > "$LOG_DIR/vllm-qwen.pid"

echo "[vllm] PIDs: gemma=$(cat $LOG_DIR/vllm-gemma.pid), qwen=$(cat $LOG_DIR/vllm-qwen.pid)"
echo "[vllm] logs en $LOG_DIR/"
echo "[vllm] para detener: kill \$(cat $LOG_DIR/vllm-gemma.pid) \$(cat $LOG_DIR/vllm-qwen.pid)"
