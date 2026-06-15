# infra/vllm/

> **⚠️ En 16 GB el serving local NO usa vLLM (ADR-014 / #207).** Medido: bajo
> vLLM no entran dos LLM en la 4080 16 GB (Gemma 12B sola = ~11,6 GiB reales por
> el overhead por-proceso). El serving local de 16 GB usa **Ollama/GGUF**
> (12B+9B+bge = 14,55 GiB; ver
> [ADR-014](../../docs/architecture/adrs/ADR-014-serving-ollama-gguf-16gb.md)).
> Este directorio es la ruta vLLM para **GPU de 24 GB+**, con los checkpoints
> AWQ confirmados en #207.

Scripts para levantar el stack de inferencia de Ynara con vLLM en GPU de
**24 GB+**: **Gemma 4 12B** (conversacional), **Qwen 3.5-9B** (agente) y
**bge-m3** (embeddings).

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

Para producción, usar las systemd units por modelo en lugar del script:
[`infra/prod/vllm-gemma.service`](../prod/vllm-gemma.service),
[`infra/prod/vllm-qwen.service`](../prod/vllm-qwen.service) y
[`infra/prod/vllm-bge.service`](../prod/vllm-bge.service). Levantar el
stack completo bajo systemd:

```sh
systemctl enable --now vllm-gemma.service vllm-qwen.service vllm-bge.service
```

## Topología (cómo lo ve el backend)

La topología operativa es **`single_process` co-residente** (ADR-012 D2):
los tres modelos (gemma 12B + qwen 9B + bge-m3) cargan a la vez en la
misma GPU 16 GB, **sin swap ni alternancia LRU**. A nivel de procesos
vLLM eso son tres procesos (uno por modelo, ADR-013 / ADR-009 D1), que el
backend ve vía `LLM_SERVING` (gemma `:8001`, qwen `:8002`) detrás del
`ClientPool`, más el embedder con `EMBEDDING_BACKEND=vllm` apuntando a
`:8003`. La co-residencia (los dos LLM + el embedder cargados
simultáneamente) es lo que define `single_process` en la abstracción de
ADR-009 D1, no la cantidad de procesos del sistema. En dev con Ollama
(un solo endpoint que sirve todos los modelos) la topología es la misma:
`single_process` co-residente.

## Configuración (medida en #207, cerrada por ADR-014)

Medición vLLM 0.23.0 en la 4080 16 GB (pesos reales en VRAM): Gemma 12B
**8,28 GiB**, Qwen 9B **8,41 GiB**, Qwen 4B ~4 GiB, bge **1,06 GiB**. Con
~1,3–2 GiB de overhead torch + ~1,1 GiB de contexto CUDA **por proceso**, **dos
LLM no entran en 16 GB** (Gemma 12B sola = ~11,6 GiB reales) → en 16 GB se usa
Ollama (ADR-014). En **GPU de 24 GB+**, estos son los valores confirmados:

- Checkpoints AWQ (ungated): `cyankiwi/gemma-4-12B-it-AWQ-INT4`,
  `cyankiwi/Qwen3.5-9B-AWQ-4bit`, `BAAI/bge-m3`. Los `QuantTrio/*` están
  inflados (Qwen 9B = 11,2 GiB); evitar.
- `--max-num-seqs ≤192` en Qwen: es híbrido Mamba (el default 256 falla con
  *"exceeds available Mamba cache blocks"*).
- `--tool-call-parser`: `gemma4` (Gemma) / `hermes` (Qwen) — ADR-009 D2.
- `--kv-cache-dtype fp8`: soportado en Ada (sm_89).

## Resueltas por ADR-012 (antes "Open questions")

- ¿Los dos en paralelo o alternancia LRU? → **Co-residentes**
  (`single_process` co-residente, sin swap): el 26B no entraba en 16 GB,
  el 12B sí.
- ¿Tamaño de cuantización? → AWQ-Marlin Q4 (ADR-009 D3); medir
  KV/contexto reales en #207.
- ¿Si la 4080 satura? → bajar `--max-model-len` de Qwen o cuantizar KV;
  el 26B + swap quedó descartado (ADR-012).
