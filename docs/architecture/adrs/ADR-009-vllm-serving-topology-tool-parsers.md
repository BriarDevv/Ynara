# ADR-009: Topología de serving vLLM y parsers de tool-calling

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-05-29, habilitando
     el PR de implementación (regla #9 de AGENTS.md). -->

## Fecha

2026-05-29

## Contexto

La card *Integración con backend LLM* asumía dos cosas como "decisiones
cerradas":

1. **Un solo proceso vLLM sirve los dos modelos**, switcheando por el
   campo `model` del payload OpenAI-compatible.
2. **Parser `qwen3_coder`** para las tool calls de Qwen.

La investigación técnica (fuentes oficiales de vLLM y Qwen, oct
2025–2026) muestra que ambas premisas son incorrectas:

- **vLLM es estrictamente un modelo por proceso.** No existe serving
  concurrente de dos modelos distintos en un mismo proceso; el campo
  `model` solo matchea el modelo cargado (o su `--served-model-name`).
- **En 16 GB no entran los dos juntos.** Gemma 4 26B-A4B en Q4 ocupa
  ~15,7 GB solo en pesos; sumado a Qwen 3.5-9B (~7 GB) es imposible
  simultáneo en la RTX 4080 Super.
- **El parser correcto para Qwen 3.5-9B-Instruct es `hermes`**, no
  `qwen3_coder`. `qwen3_coder` es para modelos `*-Coder-*` y tiene bugs
  conocidos en vLLM (los `tool_calls` quedan en `content` y no se
  populan). **Gemma 4 usa el parser `gemma4`** (serialización custom
  que vLLM normaliza a formato OpenAI estándar en el response).

[ADR-002](./ADR-002-gemma-qwen-dual-stack.md) ya anticipaba "endpoints
separados en puertos distintos" y "alternancia con cache LRU" si la VRAM
no alcanza. Este ADR **refina** (no reemplaza) ADR-002: formaliza la
topología real, fija los parsers y define una abstracción que tolera las
tres topologías posibles sin reescribir código.

## Decisión

### D1 — Serving = N procesos, abstraído por un pool

Cada modelo corre en su propio proceso vLLM (un modelo por proceso). El
backend habla con ellos a través de un `ClientPool` que rutea por el
campo `model`. La topología se elige por configuración, no por código:

- `split_process` — 2 procesos en 2 puertos (default en dev).
- `single_process` — 1 proceso con 1 modelo (si en el futuro hay GPU
  con VRAM suficiente para uno grande, o se sirve un solo modelo).
- `swap_lru` — 1 proceso que alterna modelo activo vía Sleep Mode
  Level 2 de vLLM (~1–3 s de switch). Es el mecanismo concreto de la
  "alternancia con cache LRU" que menciona ADR-002.

El cliente switchea por el campo `model` **siempre**; el pool resuelve a
qué instancia mandar vía `serves_model()`. Cambiar de topología es
cambiar config, no reescribir el router ni el cliente.

### D2 — Parsers de tool-calling

| Modelo | `--tool-call-parser` |
| --- | --- |
| `qwen-3.5-9b` | `hermes` |
| `gemma-4-26b-a4b` | `gemma4` |

Flags de arranque: `--enable-auto-tool-choice --tool-call-parser <X>`.
Las requests usan `tool_choice="auto"` (nunca `"required"`) por el
conflicto conocido de Qwen3 entre thinking mode y `tool_choice=required`
(error 400).

### D3 — VRAM y cuantización

En la 4080 Super 16 GB, la cuantización viable es **Q4 (AWQ-Marlin)**;
FP8 es experimental en Ada Lovelace. Si los dos modelos no entran
juntos, la topología por default operativa es `swap_lru` o
`split_process` con un solo modelo residente. Los valores finales
(`max_model_len`, `kv_cache_dtype`, `gpu_memory_utilization`) se fijan
**después de medir** en el hardware real; este ADR define la estructura,
no los números definitivos.

### D4 — Config: única fuente de verdad

Se elimina la duplicación actual de endpoints (hoy están en
`ynara.config.json[models].endpoint` **y** en
`core/config.py[gemma_endpoint|qwen_endpoint]`):

- **`ynara.config.json[llm.serving]`** = contrato de producto:
  `served_name` por modelo, `tool_parsers`, `quantization`,
  `kv_cache_dtype`, `max_model_len` por modelo, timeouts.
- **`.env` / settings** = valores por entorno y secrets:
  `LLM_PRIMARY_BASE_URL`, `LLM_SECONDARY_BASE_URL`, `LLM_TOPOLOGY`.

## Consecuencias positivas

- El código tolera 1 proceso, 2 procesos o swap sin reescritura.
- Escalar a múltiples instancias del mismo modelo = agregar clients al
  pool + cambiar `RoutingStrategy` (de `FirstHealthy` a
  `LeastQueueDepth`). Cero cambios en router/cliente.
- Parsers correctos: las tool calls de Qwen y Gemma se parsean bien
  desde el día uno.
- La duplicación de config desaparece; un solo lugar por tipo de dato.

## Consecuencias negativas

- El `ClientPool`/gateway agrega un hop de red interno.
- `swap_lru` agrega ~1–3 s de latencia en cada cambio de modelo.
- Sleep Mode requiere `VLLM_SERVER_DEV_MODE=1`, que expone `/sleep` y
  `/wake_up`. Detrás del Cloudflare Tunnel hay que protegerlos con auth
  en el gateway.

## Mitigaciones

- Minimizar switches agrupando requests por modelo cuando se pueda.
- **Contract test** del formato de tool-calls de cada parser: si un
  upgrade de vLLM cambia el formato, el test rompe antes de prod.
- Pinear la versión de vLLM y del parser; testear el upgrade.

## Alternativas descartadas

- **Un proceso multi-modelo**: no existe en vLLM (la premisa original
  de la card).
- **Parser `qwen3_coder` para Qwen-Instruct**: bugs conocidos; es para
  modelos Coder.
- **Fallback a APIs externas (OpenAI/Anthropic/Google)**: viola la
  regla #4. El fallback es siempre on-prem.

## Relación con otros ADRs

- **Refina** [ADR-002](./ADR-002-gemma-qwen-dual-stack.md) (dual-stack).
- **ADR-008** queda reservado para bge-m3 (modelo de embedding), según
  el roadmap de memoria backend.

## Fuentes

- vLLM Sleep Mode — https://blog.vllm.ai/2025/10/26/sleep-mode.html
- vLLM Tool Calling — https://docs.vllm.ai/en/latest/features/tool_calling/
- Qwen on vLLM — https://qwen.readthedocs.io/en/latest/deployment/vllm.html
- vLLM un-modelo-por-proceso — https://github.com/vllm-project/vllm/issues/13633
