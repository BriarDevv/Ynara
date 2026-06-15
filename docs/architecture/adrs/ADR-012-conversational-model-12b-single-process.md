# ADR-012: Modelo conversacional Gemma 4 12B y topología single_process co-residente en 16 GB

> **Actualización (ADR-014):** la co-residencia de D2 y los números de D3 se
> midieron bajo vLLM/AWQ ([#207](https://github.com/BriarDevv/Ynara/issues/207))
> y **NO entran en 16 GB** por el overhead por-proceso de vLLM (Gemma 12B sola
> ocupa ~11,6 GiB reales). La co-residencia 12B+9B+bge (14,55 GiB) **sí** se
> sostiene en **Ollama/GGUF**, que pasa a ser el motor de serving local en 16 GB
> (vLLM → 24 GB+). La decisión D1 (conversacional = 12B) sigue vigente. Ver
> [ADR-014](./ADR-014-serving-ollama-gguf-16gb.md).

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-06-13, habilitando
     el PR de implementación (regla #9 de AGENTS.md), igual que el gate de
     ADR-009. -->

## Fecha

2026-06-13

## Contexto

[ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md) D3 dejó
explícitamente abierto: *"Los valores finales (`max_model_len`,
`kv_cache_dtype`, `gpu_memory_utilization`) se fijan **después de medir**
en el hardware real; este ADR define la estructura, no los números
definitivos."* También anticipaba que **en 16 GB los dos modelos no
entran juntos** y proponía `swap_lru` o `split_process` con un modelo
residente como fallback.

El 2026-06-13 se midió en la máquina real (RTX 4080 Super, 16 GB) vía
Ollama (GGUF Q4_K_M) para cerrar ese pendiente. Resultados:

**Gemma 4 26B-A4B (`gemma4:26b`, Q4_K_M) — NO entra:**

| Métrica | Valor |
| --- | --- |
| Pesos en disco | **18,0 GB** (> 16 GB de VRAM) |
| Cargado en GPU | 14,72 GB (80,8 %) |
| Spill a CPU (a `num_ctx=2048`) | 3,49 GB |
| Carga (= costo de swap) | 49,8 s |
| Velocidad | 4,7 tok/s |

Los pesos del 26B (18 GB en 4-bit) son **más grandes que toda la VRAM**.
Esto invalida `swap_lru` para el 26B: el swap resuelve "dos modelos no
entran juntos", no "un modelo no entra solo". A 4 bits el formato (GGUF
vs AWQ) no cambia el orden de magnitud: el 26B exige una GPU de 24 GB.

**Opción medida y elegida — 12B + 9B + bge co-residentes:**

| Modelo | VRAM (Ollama, 8K ctx) | % en GPU |
| --- | --- | --- |
| `gemma4:12b` (conversacional) | 8,01 GB | 100 % |
| `qwen3.5:9b` (agente) | 5,88 GB | 100 % |
| `bge-m3` (embedder) | 0,66 GB | 100 % |
| **Total** | **14,55 GB** | sin spill |

Los tres co-residen a `num_ctx=8192`, **sin spill a CPU**, dejando
~150 MiB libres. Velocidad ~28-29 tok/s; cargas 7-9 s.

**Gotcha de thinking:** Gemma 4 (12B y 26B) es un modelo *thinking*. Con
thinking activo quema el presupuesto de tokens en el razonamiento interno
y devuelve `content` vacío (`done_reason=length`). Con thinking
desactivado responde normal (rioplatense correcto). Esto se relaciona con
el conflicto ya documentado en ADR-009 D2 (Qwen3 thinking +
`tool_choice=required`).

Este ADR **refina** ADR-009 (cierra D3 con números reales y cambia la
topología default) y **ajusta** la elección de modelo de
[ADR-002](./ADR-002-gemma-qwen-dual-stack.md).

## Decisión

### D1 — Conversacional = Gemma 4 **12B** (dense), no 26B-A4B

En la 4080 Super 16 GB, el conversacional pasa a **Gemma 4 12B** (variante
dense de la familia Gemma 4), `served_name: gemma4`. El 26B-A4B queda
descartado en este hardware: no entra en VRAM. El agente sigue siendo
**Qwen 3.5 9B** (`served_name: qwen`), sin cambios.

Cambio en `ynara.config.json`: la key `gemma-4-26b-a4b` se renombra a
`gemma-4-12b` en `models`, en los `modes` que la referencian
(estudio, bienestar, vida) y en `llm.serving` (`tool_parsers`,
`max_model_len`). El parser sigue siendo `gemma4` (es el de la familia).

### D2 — Topología default = `single_process` co-residente

Los tres modelos (gemma4-12b + qwen-9b + bge-m3) caben simultáneamente en
16 GB, así que la topología operativa pasa a **co-residencia sin swap**.
En la abstracción de ADR-009 D1 esto se expresa como cada modelo en su
proceso (`split_process` en vLLM, o un endpoint único en Ollama dev), con
**los dos LLM cargados a la vez** — no hay alternancia LRU. Se descarta
`swap_lru` como default: no hace falta y agrega latencia.

### D3 — `max_model_len` y KV cache

- `max_model_len` del conversacional: **8192**. Es el techo de
  co-residencia medido (con ~150 MiB de margen). Ynara no necesita
  ventana grande porque la memoria larga vive en las 3 capas
  (Postgres + pgvector) y se recupera por retrieval (bge-m3 + reranker),
  no metiendo todo en el prompt.
- `kv_cache_dtype: fp8` se mantiene (ADR-009) para conservar margen.
- Si se necesitara más ventana: cuantizar KV o pinear el conversacional y
  swapear solo el agente (carga ~8,5 s, barato) para liberarle VRAM.
- **Pendiente de confirmar bajo vLLM/AWQ** en prod: la medición fue en
  Ollama/GGUF. La decisión (12B entra, 26B no) es robusta al formato; los
  números finos (`gpu_memory_utilization`, `max_model_len` exacto bajo
  AWQ-Marlin) se reconfirman cuando se levante vLLM en la box.

### D4 — Control de thinking por rol

El cliente LLM controla el thinking según el `role` del modelo:

- **Conversacional (`role: conversational`) → thinking OFF.** Respuesta
  directa, baja latencia, sin quemar tokens en razonamiento oculto.
- **Agente (`role: agent`) → thinking ON (configurable).** El
  razonamiento paso a paso ayuda a planificar tool calls.

Implementación: en Ollama es `think: false` (top-level); en vLLM es
`chat_template_kwargs: {enable_thinking: false}`. El parámetro exacto de
vLLM se verifica contra docs oficiales en el PR de la feature. El `role`
ya existe en `ynara.config.json[models]`, así que el router decide sin
config nueva.

## Consecuencias positivas

- **Cero swap**: chat fluido (~28-29 tok/s), sin los ~50 s de carga del
  26B ni los ~1-3 s de switch de `swap_lru`.
- Cierra el pendiente de ADR-009 D3 con evidencia medida.
- bge-m3 queda residente: la memoria (retrieval) nunca se traba por
  carga/descarga de modelos.
- La topología `single_process` co-residente es la más simple de operar
  (sin Sleep Mode, sin timeouts de swap, sin tuning de circuit breaker).
- El enum `LlmModel` (`gemma`/`qwen`) es agnóstico de versión: el cambio
  **no toca DB, `audit_log` ni migraciones**.

## Consecuencias negativas

- Se resigna la calidad tier-26B del conversacional. El 12B es suficiente
  para chat en rioplatense, pero es un escalón menos. Recuperar el 26B
  exige GPU de 24 GB (4090/3090/A5000).
- Margen de VRAM mínimo (~150 MiB a 8K): **8K es el techo** de
  co-residencia. Ventanas mayores (16K/32K) o concurrencia > 1 no entran
  sin cuantizar KV o cambiar a pinear+swap.
- Hay que implementar control de thinking por rol (feature nueva; hoy
  `vllm.py` no lo maneja).

## Mitigaciones

- Apoyarse en retrieval (3 capas) en vez de ventana grande mantiene el
  prompt chico y el KV acotado.
- Para más ventana sin más GPU: KV cache `q8_0`, o pinear gemma + swapear
  qwen para turnos de agente.
- Contract test del payload con thinking OFF/ON para que un upgrade de
  Ollama/vLLM que cambie el parámetro rompa antes de prod.

## Alternativas descartadas

- **Gemma 4 26B-A4B + `swap_lru`**: el 26B no entra ni solo en 16 GB
  (18 GB de pesos); el swap no aplica. Medido: 4,7 tok/s con spill a CPU.
- **Comprar GPU de 24 GB ahora**: válido pero fuera de alcance del MVP;
  queda como camino si se requiere tier-26B.
- **Bajar el 26B a Q3**: entraría pero degrada justo la calidad que
  justificaba el 26B; peor de los dos mundos.
- **Fallback a APIs externas**: viola regla #4 (igual que ADR-009).

## Relación con otros ADRs

- **Refina** [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md):
  cierra D3 con números medidos, cambia la topología default a
  `single_process` co-residente y renombra la key de modelo en D2.
- **Ajusta** [ADR-002](./ADR-002-gemma-qwen-dual-stack.md): el
  conversacional pasa de 26B a 12B en hardware de 16 GB.
- **Confirma** [ADR-008](./ADR-008-embedding-model-bge-m3.md): bge-m3
  co-reside con los dos LLM sin problema.

## Fuentes

- Medición propia 2026-06-13 en RTX 4080 Super 16 GB (Ollama 0.30.7,
  GGUF Q4_K_M): `/api/ps`, `nvidia-smi`, `load_duration` y `eval` rate.
- Gemma 4 lineup (E2B/E4B/12B/26B-A4B/31B) —
  https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
- Gemma 4 26B-A4B (MoE, pesos completos en memoria) —
  https://huggingface.co/google/gemma-4-26B-A4B
- Qwen 3.5 9B —
  https://venturebeat.com/technology/alibabas-small-open-source-qwen3-5-9b-beats-openais-gpt-oss-120b-and-can-run
