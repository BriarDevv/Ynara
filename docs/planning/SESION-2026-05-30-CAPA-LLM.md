# Bitácora de sesión — Capa de inferencia LLM (2026-05-30)

> **Resumen de este documento.** Es la bitácora/handoff de la sesión del
> 2026-05-30 sobre la **capa de inferencia LLM** del backend de Ynara.
> Registra, en orden: (1) **lo que se implementó y mergeó a `main`**
> (ADR-009 + M0–M6 + migración inicial + conexión a Supabase + un fix de
> config); (2) los **PRs mergeados** y los **issues abiertos**; (3) **lo
> que falta** del roadmap, con sus *gates* (qué bloquea qué); (4) las
> **deudas técnicas y cosas menores** (con y sin issue); (5) **lo que
> conviene revisar por las dudas**; y (6) los **pendientes humanos
> críticos** (rotar credenciales, ADR-008, master key de cifrado,
> revisión de la voz de los prompts). Con esto, cualquiera —humano o
> agente— retoma el trabajo sabiendo exactamente dónde está parado todo.

---

## 1. Qué se hizo (todo mergeado a `main`)

Capa de inferencia LLM desde cero hasta el cliente + tools, más la
migración inicial y la conexión a la base. `main` quedó en historial
lineal, **doctor OK, 175 tests verdes** en `tests/llm`.

| Pieza | Qué entró | PR |
|---|---|---|
| **ADR-009** | Topología de serving vLLM (un modelo por proceso, configurable por `LLM_TOPOLOGY` detrás de un pool) + parsers de tool-calling correctos (`hermes` para Qwen, `gemma4` para Gemma). Refina ADR-002. Estado: **Aceptado**. | #28 |
| **M0** | Config single-source: se eliminó la duplicación de endpoints (estaban en `ynara.config.json` y en `core/config.py`). `ynara.config.json[llm.serving]` = contrato de producto; `.env`/settings = base URLs + `LLM_TOPOLOGY`. `load_llm_config()` con fail-fast. | #28 |
| **M1** | Protocol `LLMClient` + schemas Pydantic v2 strict + taxonomía de errores que nunca expone contenido de usuario (regla #4). | #28 |
| **M2** | `VllmClient` (httpx inyectado, switch por `model`, streaming SSE, mapeo de errores HTTP) + un único `OpenAIToolCallParser` + `FakeLlmClient` + contract tests. | #28 |
| **PR B** | Migración Alembic inicial: extensiones `vector` + `pgcrypto`, 4 enums nativos, **6 tablas** (users, sessions, semantic/episodic/procedural_memory, audit_log), índices HNSW. **Tabla sagrada**: mergeada con override explícito de regla #3 (no había 2do maintainer; review técnico OK). | #29 |
| **M3** | `ClientPool` + `RoutingStrategy` + `CircuitBreaker` + `ResilientClient`: retry con backoff, cadena **primario → secundario on-prem → respuesta degradada** (regla #4, cero externos). Un blocker de review (excepciones `LlmError` no clasificadas escapaban crudas) fue detectado y resuelto. | #34 |
| **M5** | Prompts por modo: `shared.py` (identidad/voz/seguridad) + 5 `SYSTEM_PROMPT` (uno por modo) + `loader.py`. Gemma solo lee; Qwen tools+escritura; conversacionales nunca clínicos/moralizantes (regla #14). | #35 |
| **Fix Vida** | `vida` (Gemma) tenía `calendar` en `tools_enabled`, pero Gemma es solo conversacional + lector de memoria (ADR-002). Se quitó la tool y se alinearon `ynara.config.json` + `AGENTS.md` + `MODES.md`. | #36 |
| **M6** | Framework de tools: `Tool` (Protocol) + `ToolRegistry` (resuelve `tools_enabled` → `ToolSpec`s, ejecuta con **errores siempre estructurados**, nunca traceback al modelo) + `calendar.*` / `reminder.*` como stubs honestos. **Sin `memory.*`** (es M7, sagrado). | #37 |
| **Supabase** | Conectado vía **session pooler** (puerto 5432, IPv4; la conexión directa es IPv6-only y no resuelve). `DATABASE_URL` en `apps/backend/.env` (gitignored). Schema aplicado, DB en `head`. | — |
| **Docs** | Se organizaron 2 PDFs sueltos (`fine-tuning-plan.pdf` → `architecture/`, `compliance.pdf` → `compliance/`) + esta bitácora. | (este PR) |

**PRs mergeados esta sesión:** #28, #29, #34, #35, #36, #37 (todos rebase
merge, historial lineal).

## 2. Estado de `main`

- Capa LLM funcional hasta el **cliente resiliente + prompts + tools**.
  Falta el **router** (M8) que orqueste todo y el **endpoint** (M9).
- Base de datos **conectada** y con el **schema de memoria aplicado**.
- `core/security.py` (auth) sigue en `NotImplementedError` — bloquea el
  router real.
- Doctor 15–16/10 según rama (0 fallas). Tests `tests/llm`: 175 passed.

## 3. Issues abiertos

**De esta sesión (deuda de los reviews):**

| # | Tema |
|---|---|
| #26 | Refactor `settings` lazy en `core/config.py` (hoy el conftest parchea env dummy). |
| #27 | Cablear `request_timeout_s` del config al cliente (hoy usa el default 30s). |
| #30 | Endurecer `OpenAIToolCallParser.parse()` ante `tool_calls` malformado no-lista. |
| #31 | Cubrir el streaming de tool-calls end-to-end (`accumulate()` no tiene consumer hasta M8). |
| #32 | Validar `max_model_len <= context_window` en `load_llm_config`. |
| #33 | Test de migración contra una DB efímera/transaccional (no la MVP). |
| #38 | Validación de datetime en tools acepta epoch numérico (debería ser solo ISO 8601). |
| #39 | Testear el path `execution_error` del registry + test namespace↔name + unificar `reminders`/`reminder` en TOOLS.md/config. |

**Pre-existentes (del equipo, no de esta sesión):** #20 (commit imperativo
vs noun-phrase), #23 (test round-trip de enums contra Postgres real +
fixture `db_session`).

> Nota: #23 y #33 se solapan (ambos piden infra de tests contra DB real);
> conviene resolverlos juntos.

## 4. Lo que queda por hacer (roadmap + gates)

```
        [ADR-008 bge-m3]      [MEMORY_ENCRYPTION_MASTER_KEY]
                \                    /
                 v                  v
              [PR C — crypto + wrappers de memoria]  (SAGRADO, regla #3)
                          |
                          v
              [M7 — tool memory.*]  (SAGRADO)
                          |
   [M4 — observabilidad]  |   [M5 ✓]
            \             |    /
             v            v   v
                  [M8 — router completo + tool loop + consolidación]
                          |
                          v
                  [M9 — endpoint /v1/chat + E2E]
                          |
                          v
                  AGENTE FUNCIONANDO E2E
```

- **M4 — Observabilidad + health real**: métricas (tokens/s, queue depth,
  TTFT, tool-parse-errors, fallback counters), Sentry con **PII scrubbing
  obligatorio** (regla #4), health endpoint readiness. Mayormente
  hacible; el health-endpoint se acopla a M8 (necesita el cliente
  cableado).
- **PR C — crypto + wrappers de memoria** 🔴 SAGRADO: `core/crypto.py`
  (AES-256-GCM + HKDF) + wrappers `app/memory/`. **Bloqueado por** ADR-008
  + la master key. Requiere 1 aprobación humana (regla #3).
- **M7 — tool `memory.*`** 🔴 SAGRADO: depende de PR C.
- **M8 — router**: clasificar modo→modelo, recuperar memoria, armar
  prompt, `pool.pick`, tool loop, encolar consolidación. Depende de M4,
  M5 (✓), M7.
- **M9 — endpoint `/v1/chat` + E2E**.
- **`core/security.py`** (auth JWT) — está en `NotImplementedError`; el
  router lo necesita.
- **ADR-008 (bge-m3)** — decisión de modelo de embedding, sin código.
  Desbloquea PR C.
- **Workers Celery** — consolidación post-turno, decay procedural,
  retention episódica.
- **Endpoints de memoria** — CRUD/export/settings (`/v1/memory/*`).

## 5. Deudas técnicas y cosas menores

**Con issue** (ver §3): #26–#33, #38, #39.

**Sin issue (notas de los reviews):**

- `ResilientClient.health()` no envuelve `client.health()` en try/except
  por cliente (defensivo; no es bug con el `VllmClient` actual, que nunca
  lanza).
- `CircuitBreaker` **no es task-safe**: bajo requests concurrentes que
  comparten el breaker, `HALF_OPEN` puede dejar pasar más de una prueba.
  Documentado; aceptable para 1-2 procesos.
- Tools: el `description` del JSON Schema arrastra el docstring RST del
  modelo Pydantic (ruido en el prompt); `_stub_result`/`_first_error`
  están duplicados entre `calendar.py` y `reminders.py` (DRY).
- `TOOLS.md` lista `reminder.cancel` pero se implementó `reminder.list` →
  alinear el catálogo (parte de #39).
- **CI** sigue en `workflow_dispatch` solamente. Ya existen `uv.lock` y
  `pnpm-lock.yaml`, así que se podría reactivar `push`/`pull_request`
  (ver landmine en `AI-GUIDELINES.md`).

## 6. Cosas que conviene revisar por las dudas

- **Voz de los prompts (subjetiva)** 👀: leer los 5 `SYSTEM_PROMPT` de
  `app/llm/prompts/`. Los tests anclan invariantes estructurales (voseo,
  perímetro, no-tools en Gemma), **no** la redacción fina. Ajustá el
  wording tranquilo.
  - **Protocolo de crisis de Bienestar**: `MODES.md` lo tiene como `TODO`
    (cierre con equipo + revisión legal). El prompt es genérico.
  - **Acentos**: los prompts van en ASCII (consistencia con `app/llm`).
    Si la voz prefiere tildes, es un cambio chico.
  - **IDENTITY.md rasgos 3-5** siguen `TODO`; los prompts usan solo los
    rasgos 1-2 cerrados (no se inventó voz).
- **Conexión a la base**: el `.env` usa el **session pooler (5432)**. Para
  escalar a alta concurrencia con el **transaction pooler (6543)** hace
  falta el fix de `core/deps.py`: `NullPool` + `connect_args={"statement_cache_size": 0}`
  (asyncpg + pooler de transacción no soporta prepared statements).
- **Migración ya aplicada a la DB MVP real** (queda en `head`). Si PR B se
  modifica en review, re-aplicar.
- **Sentry/PostHog** (M4, aún no implementado): cuando se cablee, el
  `before_send` **debe** borrar el texto del usuario y la respuesta
  (regla #4 — Sentry es externo).

## 7. Pendientes humanos (críticos)

1. 🔐 **Rotar el password de la DB y el PAT de Supabase** — quedaron en el
   chat de esta sesión → comprometidos. Settings → Database → Reset
   password; account/tokens para el PAT. Después actualizar `.env` y la
   env var `SUPABASE_ACCESS_TOKEN`.
2. **ADR-008 (bge-m3)** — escribir/aprobar la decisión de embedding.
   Desbloquea PR C.
3. **`MEMORY_ENCRYPTION_MASTER_KEY`** — generar con `openssl rand -base64 32`
   y guardarla en el gestor de secretos (no en el repo). Desbloquea el
   crypto de PR C.
4. **Revisión de la voz** de los prompts (§6) antes de considerarla final.

---

> Documento de handoff de una sesión puntual. No reemplaza al plan
> operativo ([`LLM-INFERENCE-INTEGRATION.md`](./LLM-INFERENCE-INTEGRATION.md))
> ni al roadmap de memoria ([`BACKEND-MEMORY-ROADMAP.md`](./BACKEND-MEMORY-ROADMAP.md)).
