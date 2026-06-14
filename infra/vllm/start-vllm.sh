#!/usr/bin/env bash
# Levanta el stack de inferencia de Ynara via vLLM: Gemma 4 12B (conversacional),
# Qwen 3.5-9B (agente) y bge-m3 (embeddings), co-residentes en la RTX 4080 Super
# 16GB. Ver ADR-012 (modelo 12B + co-residencia) y ADR-009 (topologia/parsers).
#
# Topologia: cada modelo = un proceso vLLM (ADR-009 D1), los 3 co-residen en la
# misma GPU. En el backend esto es LLM_TOPOLOGY=split_process (2 base_url de LLM:
# primary=gemma :8001, secondary=qwen :8002) + EMBEDDING_BACKEND=vllm (:8003).
#
# Asume:
# - Python venv con vllm instalado (uv sync --extra llm-local en apps/backend/).
# - CUDA 12.x y drivers NVIDIA disponibles.
# - Los pesos descargados (HuggingFace cache).
#
# Uso: ./start-vllm.sh
#
# NOTA (issue #207): los valores de --gpu-memory-utilization y --max-model-len son
# PROVISIONALES, derivados de la medicion en Ollama/GGUF (ADR-012). Falta
# confirmarlos bajo vLLM/AWQ-Marlin co-residiendo los 3 en 16GB; si OOMea, bajar
# primero el --max-model-len de Qwen.

set -euo pipefail

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"

# TODO (#207): confirmar el checkpoint AWQ exacto en HuggingFace.
GEMMA_MODEL="${GEMMA_MODEL:-google/gemma-4-12b-it}"
QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-9B-Instruct}"
EMBED_MODEL="${EMBED_MODEL:-BAAI/bge-m3}"

# --served-model-name = el served_name de ynara.config.json (el backend rutea por
# ESE nombre, no por la key del modelo). Puertos = LLM_PRIMARY/SECONDARY_BASE_URL
# y EMBEDDING_BASE_URL de apps/backend/.env.example (8001 / 8002 / 8003).

echo "[vllm] Gemma 4 12B (conversacional) en :8001..."
nohup vllm serve "$GEMMA_MODEL" \
    --port 8001 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.50 \
    --served-model-name gemma4 \
    --enable-auto-tool-choice --tool-call-parser gemma4 \
    > "$LOG_DIR/vllm-gemma.log" 2>&1 &
echo $! > "$LOG_DIR/vllm-gemma.pid"

echo "[vllm] Qwen 3.5-9B (agente) en :8002..."
nohup vllm serve "$QWEN_MODEL" \
    --port 8002 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.36 \
    --served-model-name qwen \
    --enable-auto-tool-choice --tool-call-parser hermes \
    > "$LOG_DIR/vllm-qwen.log" 2>&1 &
echo $! > "$LOG_DIR/vllm-qwen.pid"

echo "[vllm] bge-m3 (embeddings) en :8003..."
nohup vllm serve "$EMBED_MODEL" \
    --port 8003 \
    --task embed \
    --gpu-memory-utilization 0.06 \
    --served-model-name bge-m3 \
    > "$LOG_DIR/vllm-embed.log" 2>&1 &
echo $! > "$LOG_DIR/vllm-embed.pid"

# Reranker (bge-reranker-v2-m3, :8004) NO se levanta aca todavia: es un 4to proceso
# que compite por la VRAM ya ajustada; presupuestarlo es parte de #207. En dev queda
# RERANKER_BACKEND=fake (Ollama tampoco sirve cross-encoders).

echo "[vllm] PIDs: gemma=$(cat $LOG_DIR/vllm-gemma.pid), qwen=$(cat $LOG_DIR/vllm-qwen.pid), embed=$(cat $LOG_DIR/vllm-embed.pid)"
echo "[vllm] logs en $LOG_DIR/"
echo "[vllm] detener: kill \$(cat $LOG_DIR/vllm-gemma.pid) \$(cat $LOG_DIR/vllm-qwen.pid) \$(cat $LOG_DIR/vllm-embed.pid)"
