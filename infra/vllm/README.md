# infra/vllm/

Scripts para levantar el stack de inferencia de Ynara con vLLM en la
máquina con RTX 4080 Super 16GB: **Gemma 4 12B** (conversacional),
**Qwen 3.5-9B** (agente) y **bge-m3** (embeddings), co-residentes.

Ver [ADR-012](../../docs/architecture/adrs/ADR-012-conversational-model-12b-single-process.md)
(modelo 12B + co-residencia) y
[ADR-009](../../docs/architecture/adrs/ADR-009-vllm-serving-topology-tool-parsers.md)
(topología + parsers).

## Modelos

- **Gemma 4 12B** (dense) → conversacional, `served_name: gemma4`, puerto 8001.
- **Qwen 3.5-9B** → agente, `served_name: qwen`, puerto 8002.
- **bge-m3** → embeddings, `served_name: bge-m3`, puerto 8003.

Los tres co-residen en la 4080 Super 16GB (medido ~14,5 GB; ADR-012).
Cuantización AWQ-Marlin para los LLM (ADR-009 D3).

## Comandos

```sh
./start-vllm.sh             # levanta los 3 procesos en background
```

Para producción, usar systemd units por modelo en lugar del script
(issue #212).

## Topología (cómo lo ve el backend)

La co-residencia se expresa como `LLM_TOPOLOGY=split_process`: dos
base_url de LLM (primary=gemma `:8001`, secondary=qwen `:8002`) detrás
del `ClientPool`, **ambos procesos en la misma GPU**. El embedder se
prende con `EMBEDDING_BACKEND=vllm` apuntando a `:8003`. (En dev con
Ollama, que sirve todo en un endpoint, la topología es `single_process`.)

## Configuración (provisional — issue #207)

Los valores de `start-vllm.sh` salen de la medición en Ollama/GGUF
(ADR-012) y faltan confirmar bajo vLLM/AWQ:

- `--max-model-len`: Gemma 8192, Qwen 32768. Si los 3 no entran juntos,
  bajar primero el de Qwen.
- `--gpu-memory-utilization`: 0.50 / 0.36 / 0.06 provisionales (deben
  sumar < 1 dejando aire para el escritorio/CUDA).
- `--tool-call-parser`: `gemma4` (Gemma) / `hermes` (Qwen) — ADR-009 D2.

## Resueltas por ADR-012 (antes "Open questions")

- ¿Los dos en paralelo o alternancia LRU? → **Co-residentes**
  (`split_process`, sin swap): el 26B no entraba en 16 GB, el 12B sí.
- ¿Tamaño de cuantización? → AWQ-Marlin Q4 (ADR-009 D3); medir
  KV/contexto reales en #207.
- ¿Si la 4080 satura? → bajar `--max-model-len` de Qwen o cuantizar KV;
  el 26B + swap quedó descartado (ADR-012).
