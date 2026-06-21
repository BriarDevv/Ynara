# ADR-020: Circuit breaker per-proceso — cota de despliegue 1-2 workers (no breaker distribuido)

> **Se apoya en** [ADR-014](./ADR-014-serving-ollama-gguf-16gb.md) (motor local en
> una sola GPU) y [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md)
> (topología de serving; estrategia `FirstHealthy` para 1-2 procesos). Fija una
> cota de despliegue, no cambia contratos.

## Estado

Aceptado

<!-- Aprobado por Mateo García (operador humano) el 2026-06-21 como parte de la
     remediación de la auditoría backend (hallazgo H5: split-brain del breaker). -->

## Fecha

2026-06-21

## Contexto

El `CircuitBreaker` (`app/llm/clients/circuit.py`) protege cada `LLMClient` del pool
de martillar una instancia de serving caída. Su estado (`_state`, `_failures`,
`_opened_at`, `_probe_in_flight`) vive **en memoria del proceso** y `ResilientClient`
arma un breaker por endpoint en `app.state` durante el `lifespan` — es decir, **uno
por worker de gunicorn**, sin coordinación entre procesos.

La auditoría backend (H5) detectó una contradicción: el Dockerfile de producción
corría `gunicorn --workers 4`, mientras el propio docstring del breaker y ADR-014
asumen **1-2 procesos** (la caja on-prem es una sola RTX 4080, un solo endpoint de
serving local Ollama/GGUF). Con 4 workers, ante un fallo de la instancia LLM cada
worker acumula su propio `failure_threshold` antes de abrir → hasta `4 ×
failure_threshold` requests pegan al endpoint caído antes de que TODOS los breakers
abran, y las pruebas `HALF_OPEN` se multiplican por la cantidad de workers
("split-brain failover").

Dos caminos para cerrarlo:

- **(A)** Bajar el worker count a la cota real del despliegue (1-2) y documentarla.
- **(B)** Mover el estado del breaker a un store compartido (Redis), coordinando el
  failover entre N procesos/réplicas.

## Decisión

### D1 — `gunicorn --workers 2` en el Dockerfile de producción

`infra/docker/Dockerfile.backend` pasa de `--workers 4` a `--workers 2`, alineando
el despliegue con ADR-014 (single GPU on-prem) y con la estrategia `FirstHealthy`
del pool (ADR-009), pensada para 1-2 procesos. Con 2 workers el "split-brain" queda
acotado a un factor 2× (un worker abre, el otro abre en su siguiente fallo),
impacto despreciable contra un único endpoint de serving local.

### D2 — Se acepta el breaker per-proceso como diseño (NO breaker distribuido)

NO se implementa la opción (B) (breaker en Redis). El modelo de despliegue de la
fase actual es **una sola caja on-prem con una GPU**; no hay escalado horizontal
multi-réplica en alcance. Un breaker distribuido (~100 líneas sobre
`RedisTokenStore` + un Lua de incr+estado) agregaría complejidad y un RTT a Redis en
el hot-path del LLM para coordinar algo que, a 1-2 procesos, no aporta valor real.
La degradación garantizada de `ResilientClient` (primario → on-prem → respuesta
degradada, que NUNCA propaga la excepción de infra al caller) ya acota el daño de un
fallo aunque cada worker decida por separado.

## Consecuencias positivas

- Elimina el split-brain real (4× → 2×) con **cero código nuevo**, solo config.
- El diseño queda **coherente y documentado**: el breaker per-proceso es correcto
  para la cota 1-2 procesos, y la cota está escrita (antes era un supuesto implícito
  en un comentario).
- Sin RTT extra a Redis en el hot-path del LLM.

## Consecuencias negativas / mitigaciones

- **Techo de escalado**: si en el futuro se escala horizontalmente (varias réplicas
  del backend, p.ej. al pasar a multi-GPU o a varias cajas), el breaker per-proceso
  vuelve a ser sub-óptimo. **Mitigación**: este ADR es el punto de re-decisión —
  cuando el escalado horizontal entre en alcance, retomar la opción (B) (breaker en
  Redis). Hasta entonces, YAGNI.
- 2 workers dan menos paralelismo de request que 4. **Mitigación**: para una caja
  con una sola GPU el cuello de botella es el serving del LLM, no los workers HTTP;
  2 workers async (uvicorn) cubren de sobra la concurrencia de I/O.

## Relación con otros ADRs

- **Se apoya en** [ADR-014](./ADR-014-serving-ollama-gguf-16gb.md): el motor local
  vive en una sola GPU → 1-2 procesos.
- **Se apoya en** [ADR-009](./ADR-009-vllm-serving-topology-tool-parsers.md): la
  estrategia `FirstHealthy` del pool está pensada para 1-2 procesos.

## Fuentes

- `app/llm/clients/circuit.py` (estado en memoria de proceso, sin lock).
- `app/llm/clients/resilient.py` (un breaker por endpoint en `app.state`, per-worker).
- Auditoría backend 2026-06-20, hallazgo H5 (split-brain del circuit breaker).
