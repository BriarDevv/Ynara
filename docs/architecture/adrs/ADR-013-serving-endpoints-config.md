# ADR-013: Config de serving LLM explícita (endpoints → served models)

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-06-14 ("hacé lo más
     escalable y la mejor práctica, te doy mi permiso para todo"), habilitando
     el PR de implementación (regla #9 de AGENTS.md). Refina ADR-009 D1/D4. -->

## Fecha

2026-06-14

## Contexto

[ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md) D4 modeló el
serving en `.env` con `LLM_PRIMARY_BASE_URL`, `LLM_SECONDARY_BASE_URL` y
un enum `LLM_TOPOLOGY` (`split_process` / `single_process` / `swap_lru`).
El issue #206 expuso dos limitaciones del esquema posicional:

1. **Bug de ruteo.** `build_llm_client` no tiene cómo saber qué
   `served_name` vive en qué `base_url`, así que le da a **todos** los
   `VllmClient` el set completo de served_names. En `split_process` (2
   procesos, un modelo por proceso — ADR-009 D1), ambos clients dicen
   servir ambos modelos → `ClientPool` rutea una request de `qwen` al
   proceso de `gemma` (FirstHealthy toma el primero) → el proceso de
   gemma no sirve `qwen` → 404.
2. **No escala.** El par primary/secondary está fijo a 2 procesos y no
   expresa N modelos ni N instancias del **mismo** modelo (el gancho
   `LeastQueueDepth` de ADR-009 §4). El enum `topology` además
   conflaciona "cuántos procesos hay" con "co-residencia vs swap".

(Solo Ollama dev se salva del bug: un endpoint sirve de verdad todos los
modelos, así que el set completo es correcto ahí.)

Este ADR **refina** ADR-009: reemplaza el esquema posicional por una
descripción explícita y data-driven del serving.

## Decisión

### D1 — `LLM_SERVING`: lista explícita de procesos

`.env` declara la topología de serving como una lista; cada entrada
describe **un proceso vLLM**: su `base_url` y los `models` (served_names)
que sirve.

```json
LLM_SERVING=[
  {"base_url": "http://localhost:8001/v1", "models": ["gemma4"]},
  {"base_url": "http://localhost:8002/v1", "models": ["qwen"]}
]
```

- **Co-residencia** (vLLM, ADR-012): N entradas, un modelo cada una.
- **Ollama dev**: 1 entrada con todos los `models` en un endpoint.
- **Escalado** (ADR-009 §4): varias entradas con el **mismo** served_name
  → el pool tiene N candidatos → `LeastQueueDepth`. Cero cambios de código.

### D2 — El factory arma un client por entrada

`build_llm_client` crea un `VllmClient` por entrada, con
`served_models = entry.models`. El `ClientPool` reúne todos en el orden de
la lista (= orden de preferencia). `candidates(model)` ya filtra por
`serves_model`, así que el ruteo queda correcto y el multi-instancia es
natural. **Esto cierra #206.**

### D3 — Se retira el enum `LLM_TOPOLOGY`

La topología **es** la lista. El swap (Sleep Mode de vLLM) es un detalle
de orquestación del **servidor** (infra/`start-vllm.sh`), invisible para
el cliente: desde el cliente, un proceso que alterna modelos se modela
como una entrada con varios `models`. El cliente no necesita el enum.

### D4 — Coherencia (fail-fast)

`load_llm_config` valida que cada `models[]` de `LLM_SERVING` sea un
`served_name` declarado en `ynara.config.json[models]`. `served_name`,
parsers y quantization **siguen** en `ynara.config.json` (ADR-009 D4 se
mantiene para eso); lo único que cambia es **cómo `.env` describe los
endpoints**.

## Consecuencias positivas

- Cierra #206: cada client anuncia solo sus modelos → ruteo correcto.
- Escala a N modelos y N instancias del mismo modelo sin tocar código
  (el `RoutingStrategy`/`ClientPool` ya estaban listos para multi-candidato).
- Explícito > posicional; desaparece el enum `topology` ambiguo.
- Una sola fuente describe la realidad del serving (qué corre dónde).

## Consecuencias negativas

- Cambia el contrato de `.env`: migración de `LLM_PRIMARY_BASE_URL` +
  `LLM_SECONDARY_BASE_URL` + `LLM_TOPOLOGY` → `LLM_SERVING`.
- Hay que reescribir los tests que afirmaban el esquema viejo
  (`test_config`, `test_pool`, `test_factory`).

## Alternativas descartadas

- **Mapear por rol** (primary=conversational, secondary=agent): arregla
  #206 pero queda fijo a 2 modelos por rol; no escala a N modelos ni a
  N instancias. Es un parche, no la estructura.
- **`base_url` por modelo en `ynara.config.json`**: viola ADR-009 D4 (los
  endpoints son por-entorno, no contrato de producto).

## Relación con otros ADRs

- **Refina** [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md)
  (D1 serving N-procesos, D4 split de config).
- Se apoya en [ADR-012](./ADR-012-conversational-model-12b-single-process.md)
  (co-residencia 12B + 9B + bge en 16 GB).
