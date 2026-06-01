# Bitácora de sesión — Capa de inferencia LLM (2026-05-30)

> **Actualización post-sesión (2026-05-31):** `core/security.py` (auth JWT) fue implementado; `/v1/chat` (sync + SSE streaming), `/v1/sessions` y `/v1/memory` completo están mergeados. Este doc es la bitácora point-in-time de la sesión original — el cuerpo no se reescribe.
>
> **Actualización #66:** M4 observabilidad + Sentry PII scrubbing implementado; el scrubber (`_scrub_event`) cubre también breadcrumbs (message+data), `exception.values`, `contexts` y `extra`, además de request data/cookies/headers/query_string y user.

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
>
> **Actualización (parte 2, mismo día — 2026-05-30).** Se cerraron los **10
> issues de deuda** (#20, #23, #26, #27, #30–#33, #38, #39) en 5 PRs
> revisados; se reescribió la doc de `apps/backend` (AGENTS.md + README)
> para que sea AI-friendly; se saldó la deuda de `ruff` (incluidos 3
> archivos sagrados, con aprobación humana explícita); y se **verificaron
> los tests de integración contra un Postgres+pgvector real** (docker), lo
> que destapó y arregló un bug. Detalle en §1b.

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

## 1b. Continuación (2026-05-30, parte 2): cierre de issues + docs + cleanup

Segunda tanda del mismo día. Se cerraron **los 10 issues de deuda** que
quedaban abiertos, se llevó la doc de `apps/backend` a estado AI-friendly,
se saldó la deuda de `ruff` y se **verificaron los tests de integración
contra un Postgres real**. Todo mergeado a `main` (rebase), **cada PR
revisado por un `code-reviewer` en agente aparte**.

| PR | Cierra | Highlights |
|---|---|---|
| #45 | #26 #27 #30 #31 #32 | settings lazy · `max_model_len ≤ context_window` · parser endurecido (None vs tipo inválido) · `default_timeout_s` desde config · test e2e `stream()→accumulate()` |
| #46 | #38 #39 | datetime **solo ISO 8601** (`IsoDatetime`, rechaza epoch incluso como string) · namespace unificado a singular `reminder` (rename `reminders.py`→`reminder.py`) · test del blindaje `execution_error` · `TOOLS.md` `reminder.cancel`→`reminder.list` |
| #47 | #23 #33 | test AST de la migración (6 tablas + 4 enums, sin DB) · fixtures `db_session` + round-trip de enums · `env.py` acepta `TEST_DATABASE_URL` |
| #49 | #20 | regla #6 acepta **imperativo o noun-phrase** (Opción A) |
| #50 | — | reescritura de `apps/backend/AGENTS.md` (66→148 líneas) + `README` + `docs/README`: gates, mapa de `app/llm/`, invariantes, playbooks |
| #51 | — | **fix** `MissingGreenlet` en el round-trip de audit (lo destapó el run real) + `ruff` en archivos no sagrados |
| #52 | — | `ruff` en 3 archivos **sagrados** (lint cosmético; **aprobación humana explícita** del operador, regla #3) |

**Verificación contra Postgres real (docker pgvector):** los 3 tests de
integración de #23/#33 pasan; el run destapó un `MissingGreenlet` (acceso a
un atributo expirado dentro de un `.where()`) que se arregló con
`db_session.refresh()`. La infra de tests de integración quedó **verificada
end-to-end**, no solo escrita a ciegas.

**Issues abiertos ahora:** solo **#6** (contrato de auth del frontend, de
otro autor). PRs abiertos: ninguno propio (el #48 de onboarding del front lo
mergeó su autor).

## 2. Estado de `main`

- Capa LLM funcional hasta el **cliente resiliente + prompts + tools**.
  Falta el **router** (M8) que orqueste todo y el **endpoint** (M9).
- Base de datos **conectada** y con el **schema de memoria aplicado**.
- `core/security.py` (auth) sigue en `NotImplementedError` — bloquea el
  router real.
- Doctor 16/16 (0 fallas). Tests: **241 passed** en la suite + **3 de
  integración verdes contra Postgres real** (docker); `tests/llm` en 187.
  ⚠️ 1 test rojo **pre-existente ajeno a la capa LLM**:
  `tests/schemas/test_memory.py::test_uuid_round_trip_str_to_uuid` (Pydantic
  v2 strict rechaza UUID como string) — ya fallaba en `main` antes de esta
  sesión; conviene abrir issue.

## 3. Issues — todos cerrados ✅

Los 10 issues de deuda (8 de los reviews de esta sesión + 2 pre-existentes
del equipo: #20 y #23) se cerraron en la **parte 2** (ver §1b): **#20, #23,
#26, #27, #30, #31, #32, #33, #38, #39**. El único issue abierto del repo es
**#6** (contrato de auth del frontend MVP, de otro autor — no es de la capa
LLM).

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

**Ya cerradas** (parte 2, §1b): #26–#33, #38, #39. La **deuda de `ruff`**
del backend quedó **saldada** (PRs #51 no sagrado / #52 sagrado, lint
cosmético con aprobación humana).

**Sin issue (notas de los reviews):**

- `ResilientClient.health()` no envuelve `client.health()` en try/except
  por cliente (defensivo; no es bug con el `VllmClient` actual, que nunca
  lanza).
- `CircuitBreaker` **no es task-safe**: bajo requests concurrentes que
  comparten el breaker, `HALF_OPEN` puede dejar pasar más de una prueba.
  Documentado; aceptable para 1-2 procesos.
- Tools: el `description` del JSON Schema arrastra el docstring RST del
  modelo Pydantic (ruido en el prompt); `_stub_result`/`_first_error`
  siguen duplicados entre `calendar.py` y `reminder.py` (DRY — la validación
  de fechas sí se centralizó en `IsoDatetime`). ✅ El namespace
  `reminders`→`reminder` y `TOOLS.md` (`reminder.cancel`→`reminder.list`) ya
  se unificaron (#39).
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

1. ✅ **Credenciales rotadas (2026-05-30).** El password de la DB y el PAT
   de Supabase que quedaron expuestos en el chat fueron **rotados por el
   operador**. (Si cambió el password, recordar actualizar `apps/backend/.env`
   con la nueva URL del session pooler.)
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
