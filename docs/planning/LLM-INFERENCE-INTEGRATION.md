# Capa de inferencia LLM — Plan de integración

> **Actualizado por ADR-013/ADR-014 (junio 2026):** el runtime local de
> serving (16 GB, RTX 4080 Super) es **Ollama/GGUF** ([ADR-014](../architecture/adrs/ADR-014-serving-ollama-gguf-16gb.md)),
> no vLLM (vLLM queda para 24 GB+). El **contrato de config** de serving es
> la lista `llm_serving: list[ServingEndpoint]` (env `LLM_SERVING`, JSON
> `{base_url, models}`, [ADR-013](../architecture/adrs/ADR-013-serving-endpoints-config.md)),
> que reemplaza a `llm_primary_base_url`/`llm_secondary_base_url`/`llm_topology`.
> `LLM_BACKEND=vllm` es el **nombre legacy** del cliente HTTP OpenAI-compatible
> (sirve igual a Ollama). El cuerpo histórico de este plan no se reescribe; los
> puntos vigentes pero fácticamente desactualizados se anotan inline.

> **Estado**: v2 — M0–M9 ejecutados y mergeados; serving local = Ollama/GGUF (ADR-014); infra vLLM real (24 GB+) pendiente
> **Fecha**: 2026-05-29 · **Actualizado**: 2026-05-31
> **Alcance**: `apps/backend/app/llm/` — capa que sirve el dual-stack
> (Gemma 4 12B + Qwen 3.5-9B) sobre la RTX 4080 Super, más la
> conexión escalable a Supabase. La lógica de router + memoria + prompts
> se cruza con la card hermana *Arquitectura de memoria contextual*.
> **Fuentes**: [`AGENTS.md`](../../AGENTS.md),
> [`ADR-002`](../architecture/adrs/ADR-002-gemma-qwen-dual-stack.md),
> [`ADR-009`](../architecture/adrs/ADR-009-vllm-serving-topology-tool-parsers.md),
> [`ADR-004`](../architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md),
> [`ADR-005`](../architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md),
> [`BACKEND-MEMORY-ROADMAP.md`](./BACKEND-MEMORY-ROADMAP.md), card Trello
> *Integración con backend LLM*.

---

## 0. Correcciones a la card (formalizadas en ADR-009)

Dos "decisiones cerradas" de la card eran técnicamente incorrectas y se
corrigen en [`ADR-009`](../architecture/adrs/ADR-009-vllm-serving-topology-tool-parsers.md):

1. **vLLM no sirve dos modelos en un proceso** ni entran juntos en
   16 GB (Gemma 4 Q4 ≈ 15,7 GB). → N procesos detrás de un `ClientPool`,
   topología configurable (`split_process` / `single_process` /
   `swap_lru`) sin reescribir código.
2. **Parser correcto**: `hermes` para Qwen 3.5-9B-Instruct (no
   `qwen3_coder`), `gemma4` para Gemma 4. `tool_choice="auto"`.

El resto de las decisiones cerradas se respetan sin cambios: vLLM como
runtime, Q4/Q5, pgvector (ADR-004), LlamaIndex en la capa de
orquestación (card hermana), embeddings bge-m3, todo on-prem (regla #4),
Cloudflare Tunnel, Linux nativo.

> **Nota (ADR-014, junio 2026):** "vLLM como runtime" quedó **superado para
> 16 GB**. En la RTX 4080 Super (16 GB) el motor de serving es **Ollama/GGUF**
> ([ADR-014](../architecture/adrs/ADR-014-serving-ollama-gguf-16gb.md)); vLLM
> sólo aplica a 24 GB+. El cliente del backend es HTTP OpenAI-compatible, así
> que sirve a ambos motores sin cambios (`LLM_BACKEND=vllm` es nombre legacy
> del cliente, no implica vLLM).

> **Nota LlamaIndex**: la capa de *cliente* de inferencia (este plan) es
> un wrapper HTTP fino sobre vLLM, independiente de LlamaIndex.
> LlamaIndex vive en el router/orquestación de memoria (card hermana) y
> consume este cliente. No hay conflicto.

---

## 1. Arquitectura objetivo

`LLMClient` (Protocol) ← `VllmClient` (httpx inyectado) ← `ClientPool`
+ `RoutingStrategy` ← `ResilientClient` (retry + circuit breaker +
fallback on-prem). El router (`router.py`) es el **único** consumidor y
nunca conoce `VllmClient` — solo el Protocol. El backend nunca importa
`vllm` (eso corre en otro proceso/GPU; el extra `llm-local` de
`pyproject.toml` es para el host de inferencia, no para la app).

### Layout de `apps/backend/app/llm/` (archivos < 300 líneas)

```
app/llm/
  router.py            # único punto de entrada (completar en M8)
  config.py            # NUEVO — load_llm_config(): fusiona ynara.config.json + settings
  errors.py            # NUEVO — taxonomía LlmError
  observability.py     # NUEVO — métricas + scrubbing Sentry/PostHog
  schemas.py           # NUEVO — ChatMessage, ToolSpec, ToolCall, CompletionResult/Chunk
  clients/             # NUEVO paquete
    base.py            # Protocol LLMClient + ToolCallParser
    vllm.py            # VllmClient concreto
    pool.py            # ClientPool + RoutingStrategy (FirstHealthy)
    circuit.py         # CircuitBreaker por instancia
    resilient.py       # retry + fallback + breaker
    parsers.py         # HermesParser (Qwen) + Gemma4Parser
    fakes.py           # FakeLlmClient para tests
  prompts/             # loader + shared + 5 .md por modo (M5)
  tools/               # base + registry + calendar + reminders + memory (M6/M7)
```

### Contrato de config (única fuente de verdad, ADR-009 D4)

- `ynara.config.json[models][<key>]`: mantiene `role`, `writes_memory`,
  `context_window`; **agrega** `served_name`; **elimina** `endpoint`.
- `ynara.config.json[llm][serving]`: `tool_parsers` por modelo,
  `quantization`, `kv_cache_dtype`, `max_model_len` por modelo,
  `request_timeout_s`. (Valores provisionales hasta medir VRAM real.)
- `core/config.py` settings: **elimina** `gemma_endpoint`/`qwen_endpoint`;
  **agrega** la lista `llm_serving: list[ServingEndpoint]` (env `LLM_SERVING`,
  JSON `[{base_url, models}]` — cada entrada = un endpoint de serving y los
  served_names que anuncia; [ADR-013](../architecture/adrs/ADR-013-serving-endpoints-config.md)).
  > **Corrección (ADR-013, junio 2026):** la propuesta original de este plan
  > (`llm_primary_base_url` + `llm_secondary_base_url` + enum `llm_topology` con
  > `split_process`/`single_process`/`swap_lru`) **nunca se implementó así**.
  > ADR-013 la reemplazó por la lista explícita `llm_serving` (data-driven, escala
  > a N modelos/instancias y cierra el bug de ruteo #206). El enum `llm_topology`
  > se retiró: la topología *es* la lista. Estado real en `core/config.py`.
- Actualizar `docs/architecture/ynara-config.schema.json` y
  `apps/backend/.env.example` en el mismo cambio.

---

## 2. Milestones — track LLM

| # | Milestone | Depende | Tabla sagrada | Gate |
| --- | --- | --- | --- | --- |
| M0 | Config single-source | — | No | #1 (`ynara.config.json`) |
| M1 | Protocol + schemas + errores | M0 | No | — |
| M2 | VllmClient + parsers + FakeLlmClient + contract tests | M1 | No | — |
| M3 | Pool + circuit breaker + fallback on-prem | M2 | No | #4 |
| M4 | Observabilidad + health real (Sentry PII scrubbing) | M3 | No | #4 |
| M5 | Prompts por modo + loader | M1 | No | — |
| M6 | Tools base + calendar + reminders | M3 | No | — |
| M7 | Tool `memory.*` | M6 + PR C | **Sí** | #3, #7 |
| M8 | Router completo + tool loop + consolidación | M4, M5, M7 | No | — |
| M9 | Endpoint `/v1/chat` + E2E | M8 | No | — |

**M0–M6 no necesitan Supabase ni auth**: se desarrollan con mocks
(`FakeLlmClient`, DB real solo en integración). El cruce con memoria
real ocurre en M7/M8. **Nota (2026-05-31): M0–M6 ya están mergeados**
(con `FakeLlmClient` / `FakeEmbeddingClient` / `FakeReranker` por default).
**Actualización (2026-06-13, PR #198)**: los clientes vLLM reales también están
implementados (`VllmClient`, `VllmEmbeddingClient`, `VllmReranker`), wire-ables por
flag (`LLM_BACKEND`/`EMBEDDING_BACKEND`/`RERANKER_BACKEND`=`vllm`) y probados contra
Ollama. El **serving** vLLM en infra de prod sigue siendo un track aparte, pendiente.

### Detalle por milestone

- **M0** — `app/llm/config.py` con `LlmRuntimeConfig` (Pydantic v2
  strict) + `load_llm_config()` con fail-fast (modo apunta a modelo
  inexistente, `served_name` no servido). Borra la duplicación de
  endpoints. Toca `ynara.config.json` → regla #1 (OK humano para
  commit).
- **M1** — Protocols (`LLMClient`, `ToolCallParser`), `schemas.py`
  (mover `ChatRequest`/`ChatResponse` desde `router.py` + agregar
  `CompletionResult`/`Chunk`/`ChatMessage`/`ToolSpec`/`ToolCall`),
  `errors.py` (taxonomía: transitorios / permanentes / semánticos /
  degradación). Solo tipos, sin I/O.
- **M2** — `VllmClient` (httpx OpenAI-compatible, switch por `model`,
  `serves_model()`, streaming SSE), `parsers.py` (`hermes` + `gemma4`),
  `fakes.py`. **Contract tests** contra fixtures JSON grabados de un
  vLLM real (replay en CI sin GPU). Unit tests del parser con tabla de
  fixtures (bien formados / malformados / parciales en streaming).
- **M3** — `ClientPool` + `RoutingStrategy` (`FirstHealthy`),
  `CircuitBreaker` por instancia, `ResilientClient` (retry con backoff +
  jitter vía tenacity, cadena primario → secundario on-prem →
  `LlmDegradedResponse`). Regla #4: cero externos.
- **M4** — `observability.py`: tokens/s, queue depth (scrape de
  `vllm:num_requests_waiting`), TTFT, `tool_parse_errors`, fallback
  counters, circuit state. **Sentry con `before_send` (`_scrub_event`)
  que limpia PII de todo el evento** (regla #4 — Sentry es externo):
  `request.data` / `cookies` / headers sensibles / `query_string`,
  breadcrumbs (`message` + `data`), `exception.values[*].value`, `user`,
  `server_name`, `contexts` y `extra` — no solo el texto del usuario y la
  respuesta. `init_sentry()` es idempotente (flag de módulo). Extender
  `health.py` a readiness real (503 si el modelo crítico no responde).
  **Implementado y mergeado (#66).**
- **M5** — `prompts/{loader,shared}.py` + 5 `.md` por modo, alineados a
  `IDENTITY.md` + `TONE-OF-VOICE.md` (rioplatense). Snapshot tests.
- **M6** — `tools/{base,registry,calendar,reminders}.py`. Schema JSON
  OpenAI tool-calling. Solo Qwen recibe tools (ADR-002). Errores como
  `{"error": {"code", "message"}}`, nunca excepciones que escapen al
  modelo.
- **M7** — `tools/memory.py` que invoca los wrappers `app/memory/`.
  `memory.add` **encola Celery**, no escribe sincrónico (regla landmine).
  **Tabla sagrada (regla #3)**: cualquier cambio a `app/memory/` requiere
  tests + 1 aprobación humana + commit propio (regla #7). Depende de PR C
  del roadmap (wrappers reales).
- **M8** — Completar `router.py`: clasificar modo→modelo, recuperar
  memoria (top-3 semantic + top-2 episodic + procedural activo), armar
  prompt, `pool.pick`, tool loop para Qwen, encolar consolidación. Lee
  memoria pero no modifica esquema.
- **M9** — `app/api/v1/chat.py` + service sin framework. Mapeo de la
  taxonomía de errores a HTTP (503 / 500 / 200-degradado). E2E
  auth → router → memoria → respuesta.

### Estrategia de testing (3 niveles)

1. **Unit** (sin red, sin DB): router contra `FakeLlmClient` (routing,
   inyección de memoria, tool loop, fallback). Parser con fixtures.
   Circuit breaker con clock inyectado.
2. **Contract**: que `VllmClient` arme payloads conformes y parsee
   respuestas conformes contra fixtures grabados de vLLM real. Detecta
   drift en upgrades.
3. **Integración** (nightly, GPU opcional): vLLM real + DB real. Mocks
   de DB **prohibidos** (regla del repo); mocks de LLM permitidos
   (servicio externo determinista por contrato). Marca
   `@pytest.mark.integration`, excluida del `uv run pytest` default.

---

## 3. Track Supabase (paralelo, owner: operador humano)

El proyecto Supabase **ya existe** (ref `hmsfcqvnhlevfwfgatxd`) y está
**conectado** (session pooler, schema aplicado, DB en `head`). Pasos:

1. ✅ **PAT rotado** (2026-05-30, operador).
2. ✅ **MCP autenticado** con el PAT nuevo.
3. ✅ **Connection string** configurado en `apps/backend/.env`:
   - Runtime: **session pooler** (puerto 5432, IPv4; la conexión directa
     es IPv6-only).
   - Migraciones: conexión directa (5432).
   - 3 toggles OFF (Data API / auto-expose / RLS) — regla #5.
4. ✅ **Fix de `core/deps.py`** (bug de escalado para alta concurrencia) —
   **implementado y cubierto por tests de regresión (#210, 2026-06-14)**. El
   pooler de transacciones (6543) + asyncpg requiere desactivar prepared
   statements; `get_engine()` ya aplica `connect_args={"statement_cache_size": 0}`
   siempre y `poolclass=NullPool` cuando el puerto es 6543 (en 5432/directa usa
   `pool_size`). El branching está blindado por `tests/core/test_deps_engine.py`.

   ```python
   engine_kwargs = {
       "pool_pre_ping": True,
       "connect_args": {"statement_cache_size": 0},  # siempre (inocuo en 5432)
   }
   if urlsplit(url).port == 6543:                     # transaction pooler
       engine_kwargs["poolclass"] = NullPool          # el pooling lo hace Supavisor
   else:
       engine_kwargs["pool_size"] = settings.database_pool_size
   ```

   Alembic (`env.py`) ya usa `NullPool` (correcto), pero debe apuntar a
   la conexión directa (5432).
5. ✅ **PR B** — migración inicial mergeada (extensiones `vector` +
   `pgcrypto`, 4 enums, 6 tablas en orden FK, índices HNSW,
   constraints, tests up/down/roundtrip). **Tabla sagrada → regla #3
   (1 aprobación humana — mergeada con override explícito)**.

---

## 4. Consideraciones de escalado (10/10)

- **Multi-instancia por modelo**: agregar `VllmClient`s al pool +
  cambiar `RoutingStrategy` a `LeastQueueDepth`. Cero cambios en
  router/cliente.
- **Balanceo por queue depth real** de vLLM (`/metrics`), no LB ciego.
- **Continuous batching es de vLLM**, no del backend: el cliente manda
  requests individuales.
- **Embeddings (bge-m3) en pool separado** del chat: perfil de carga
  opuesto (batch alto vs TTFT crítico). Cache de queries frecuentes en
  Redis.
- **Backpressure**: si la cola supera umbral → 429/503 rápido
  (`LlmOverloadedError`), no encolar indefinido.
- **Consolidación Celery** desacoplada del path de respuesta: un pico de
  chat no roba GPU al TTFT del usuario.

---

## 5. Estado de ejecución

*(Actualizado 2026-06-13)*

- ✅ ADR-009 aprobado (humano) + card Trello actualizada.
- ✅ M0 — config single-source mergeado.
- ✅ M1 — Protocol + schemas + errores mergeado.
- ✅ M2 — VllmClient + parsers + FakeLlmClient + contract tests mergeados.
- ✅ M3 — Pool + circuit breaker + fallback on-prem mergeado.
- ✅ M4 — Observabilidad + health real (Sentry PII scrubbing) mergeado (#66).
- ✅ M5 — Prompts por modo + loader mergeados.
- ✅ M6 — Tools base + calendar + reminders mergeados.
- ✅ M7 — Tool `memory.*` mergeado (depende de PR C; mergeado con aprobación humana).
- ✅ M8 — Router completo + tool loop + consolidación mergeado.
- ✅ M9 — Endpoint `/v1/chat` (sync + SSE streaming) mergeado; E2E con Fakes.
- ✅ PR B — Migración Alembic inicial mergeada (6 tablas, 4 enums, pgvector).
- ✅ Track Supabase — proyecto conectado (session pooler, schema en `head`).
- ✅ PR C — `core/crypto.py` (AES-256-GCM per-user) + wrappers de memoria mergeados.
- [ ] Serving vLLM real en infra de prod — **pendiente**: reconciliar `start-vllm.sh` (served_name/puertos/proceso bge-m3), medir VRAM. Los clientes vLLM reales (`VllmClient`/`VllmEmbeddingClient`/`VllmReranker`) ya están mergeados (PR #198) y probados contra Ollama; se prenden por flag.
- [ ] Rate-limit — pendiente.
- ✅ Fix `core/deps.py` transaction pooler (6543) — el soporte (NullPool + `statement_cache_size=0`) ya estaba implementado en `core/deps.py`; queda cubierto por tests de regresión (#210, 2026-06-14).

> Documento operativo. Cambios de decisión van por ADR. Cambios de plan
> se editan acá con fecha + autor.
