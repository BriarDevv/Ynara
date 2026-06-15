# ADR-014: Motor de serving local = Ollama/GGUF en 16 GB (vLLM reservado para 24 GB+)

> **Refina** [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md) (motor de serving) y
> [ADR-012](./ADR-012-conversational-model-12b-single-process.md) (D2 co-residencia / D3 números),
> con la medición real bajo vLLM/AWQ de [issue #207](https://github.com/BriarDevv/Ynara/issues/207).

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-06-14, sobre la
     medición de #207, habilitando el cambio de motor de serving local. -->

## Fecha

2026-06-14

## Contexto

[ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md) eligió **vLLM** como
motor de serving y dejó D3 abierta: los números (`max_model_len`,
`gpu_memory_utilization`, `kv_cache_dtype`) se fijaban *después de medir en
hardware real*. [ADR-012](./ADR-012-conversational-model-12b-single-process.md)
midió en **Ollama/GGUF** (12B+9B+bge = 14,55 GB co-residentes a 8K) y eligió la
topología `single_process` co-residente, pero dejó explícito el pendiente:
*"confirmar bajo vLLM/AWQ-Marlin en prod"* (#207).

El 2026-06-14 se levantó **vLLM 0.23.0** en la RTX 4080 Super 16 GB (Docker sobre
WSL2 Ubuntu 24.04, `--gpus all`) con checkpoints AWQ ungated y se midieron los
pesos reales en VRAM. Resultados:

| Modelo | Checkpoint AWQ | Pesos VRAM | Notas |
| --- | --- | --- | --- |
| Gemma 4 12B | `cyankiwi/gemma-4-12B-it-AWQ-INT4` (compressed-tensors) | **8,28 GiB** | multimodal (`Gemma4UnifiedForConditionalGeneration`); el AWQ cargable deja visión/audio/`lm_head` en fp16 |
| Qwen 3.5 9B | `cyankiwi/Qwen3.5-9B-AWQ-4bit` (compressed-tensors) | **8,41 GiB** | híbrido Mamba; requiere `--max-num-seqs ≤192` |
| Qwen 3.5 4B | `cyankiwi/Qwen3.5-4B-AWQ-4bit` | ~4 GiB | probado para co-residencia |
| bge-m3 | `BAAI/bge-m3` (fp16, `--runner pooling`) | **1,06 GiB** | |

**Hallazgo central — bajo vLLM no entran dos LLM en 16 GB, ni siquiera 12B+4B:**

- Gemma 12B **sola** consume **~11,6 GiB reales** (medido con `nvidia-smi` a
  `--gpu-memory-utilization 0.64 --enforce-eager --kv-cache-dtype fp8`, KV 0,86 GiB
  = 11.686 tokens, 1,43x a 8192).
- El overhead **por proceso** de vLLM es ~1,33 GiB de torch (en `--enforce-eager`;
  ~2 GiB con cudagraphs) **más ~1,1 GiB de contexto CUDA que NO entra en el budget
  de `--gpu-memory-utilization`** (`nvidia-smi` marca más que `util × total`).
- Al levantar Qwen **4B** (~5,6 GiB) sobre Gemma 12B (4,4 GiB libres) →
  `ValueError: No available memory for the cache blocks`.
- Pesos solos de los dos LLM al tamaño full: 8,28 + 8,41 = **16,69 GiB > 16 GiB**.

Tres procesos vLLM pagan ~7 GiB de puro overhead sobre los pesos. **Ollama (un
solo proceso, GGUF) no paga ese costo** y por eso sí entra el stack completo
(12B+9B+bge = 14,55 GiB, medido en ADR-012). Lo que sí entra bajo vLLM: Gemma 12B
sola (~11,6 GiB) o Gemma 12B + bge (~13,6 GiB); el agente no cabe residente.

De paso se validó [#205](https://github.com/BriarDevv/Ynara/issues/205) contra
vLLM real: `chat_template_kwargs: {enable_thinking: false}` devolvió `reasoning:
null` y `content` limpio.

## Decisión

### D1 — Motor de serving local en 16 GB = **Ollama/GGUF**

En la RTX 4080 Super 16 GB, el serving local de Ynara usa **Ollama** (GGUF
Q4_K_M), no vLLM. Es el único motor que sostiene el dual-stack completo sin
recortes ni swap: Gemma 4 12B (`gemma4`) + Qwen 3.5 **9B** (`qwen`) + bge-m3
co-residentes en ~14,55 GiB. Se conserva el agente **9B** (no hace falta bajarlo
a 4B) y la calidad conversacional 12B.

### D2 — vLLM queda reservado para GPU de 24 GB+

`infra/vllm/start-vllm.sh` y las systemd units de `infra/prod/` se mantienen como
la ruta para hardware de 24 GB+, con los checkpoints AWQ **confirmados**
(`cyankiwi/...`), el fix `--max-num-seqs ≤192` (Qwen es híbrido Mamba) y los
caveats medidos documentados. No es la ruta de la 4080.

### D3 — Causa raíz (para no repetir el error de estimación)

La estimación GGUF (14,55 GiB) no predice el footprint vLLM porque vLLM corre
**un proceso por modelo** y cada proceso suma ~1,3–2 GiB de overhead torch +
~1,1 GiB de contexto CUDA **fuera** del budget de `--gpu-memory-utilization`.
La regla práctica: en 16 GB, vLLM tolera **un** LLM grande (+ bge), no dos.

### D4 — Tool-calling y thinking en Ollama

El agente (Qwen) hace tool-calling vía la API de Ollama (ya es lo que usa el
smoke de dev). Los `--tool-call-parser` de ADR-009 D2 (`hermes`/`gemma4`) son
flags de vLLM; en Ollama el template del modelo aplica internamente. El control
de thinking de ADR-012 D4 / #205 se mapea en Ollama a `think: false`
(conversacional) — el cliente ya lo contempla.

### D5 — Cuantización

16 GB (Ollama): **GGUF Q4_K_M**. 24 GB+ (vLLM): **AWQ-Marlin** (checkpoints
`cyankiwi/*` confirmados en #207). El campo `llm.serving.quantization` de
`ynara.config.json` describe el perfil vLLM/24GB.

## Consecuencias positivas

- Stack completo sin recortes ni swap; el agente sigue siendo 9B.
- Sin el overhead multi-proceso de vLLM: ~14,55 GiB con margen.
- Ya está andando (es el stack de dev): cero trabajo de standup para "hoy".
- bge-m3 residente: el retrieval nunca se traba por carga/descarga.

## Consecuencias negativas

- El tool-calling de Ollama es menos robusto que el de vLLM (parser `hermes`
  dedicado). Mitigable con contract tests; validar el agente E2E.
- Se difiere la ruta vLLM hasta tener una GPU de 24 GB+.
- ADR-009 eligió vLLM como motor; este ADR lo acota a 24GB+ en hardware actual.

## Mitigaciones

- Contract tests del formato de tool-calls del agente sobre Ollama (igual que el
  contract test que ADR-009 pedía para vLLM).
- Pinear la versión de Ollama; testear upgrades.
- `infra/vllm/` queda listo y medido para migrar a vLLM apenas haya 24 GB+.

## Alternativas descartadas (todas medidas en #207)

- **vLLM Gemma 12B + Qwen 4B (+ bge)**: no entra (~17–18 GiB reales por el
  overhead por-proceso). Medido.
- **vLLM swap 1-LLM-a-la-vez + bge**: entra pero agrega ~10 s de latencia en cada
  cambio conversacional↔agente; mala UX para chat que alterna modos.
- **vLLM con conversacional Gemma E4B (~4 GiB)**: entra todo, pero baja un escalón
  la calidad conversacional que justificaba el 12B (ADR-012).
- **2ª GPU 24 GB**: resuelve de raíz pero es gasto de hardware y no es "hoy";
  queda como camino para la ruta vLLM (D2).

## Relación con otros ADRs

- **Refina** [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md): el motor
  de serving local pasa de vLLM a **Ollama** en 16 GB (vLLM → 24GB+); cierra D3
  con números reales bajo vLLM/AWQ.
- **Refina** [ADR-012](./ADR-012-conversational-model-12b-single-process.md): la
  co-residencia D2 vale para Ollama/GGUF (14,55 GiB), **no** para vLLM/AWQ en
  16 GB; D3 confirmado con medición vLLM.
- **Confirma** [ADR-008](./ADR-008-embedding-model-bge-m3.md): bge-m3 co-reside
  sin problema (1,06 GiB).
- **Valida** [#205](https://github.com/BriarDevv/Ynara/issues/205): el control de
  thinking funciona contra vLLM real (`enable_thinking: false`).

## Fuentes

- Medición propia 2026-06-14 en RTX 4080 Super 16 GB: vLLM 0.23.0 (imagen
  `vllm/vllm-openai`), Docker/WSL2, `nvidia-smi`, líneas `Model loading took` y
  `GPU KV cache size` / `Available KV cache memory` de los logs de vLLM.
- Issue [#207](https://github.com/BriarDevv/Ynara/issues/207) (hilo de medición).
- Checkpoints: `cyankiwi/gemma-4-12B-it-AWQ-INT4`, `cyankiwi/Qwen3.5-9B-AWQ-4bit`,
  `cyankiwi/Qwen3.5-4B-AWQ-4bit`, `BAAI/bge-m3` (HuggingFace, ungated).
