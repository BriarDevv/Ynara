> **Archivo no trackeado** — entregable de trabajo de la auditoria del 2026-06-23.
> Metodo: workflow multi-agente read-only (39 agentes, ~3.78M tokens) — 14 areas
> archivo-por-archivo + 6 dimensiones cross-cutting + verificacion adversarial de
> cada CRITICAL/HIGH. Decidi vos si lo movés a docs/, lo dejás, o lo borrás.

# Auditoria Backend Ynara — Informe Final del Auditor Jefe
**Fecha:** 2026-06-23 · **Alcance:** 225 archivos (app/ ~19.2k LOC, ~110 fuente + ~75 tests + docs + alembic + tooling) · **Metodo:** 14 areas archivo-por-archivo + 6 dimensiones cross-cutting + verificacion adversarial de cada CRITICAL/HIGH.

---

## 1. Veredicto ejecutivo

### SCORE GLOBAL: **84 / 100** — APROBADO CON RESERVAS

El backend de Ynara es un sistema **maduro y bien razonado**. El nucleo de seguridad y perimetro de datos (regla #4) es de calidad excepcional y verificable linea por linea. Las grandes deudas estructurales de la auditoria 2026-06-20 fueron **realmente resueltas**, no maquilladas. No hay ningun CRITICAL. Lo que queda son **4 HIGH netos** (uno de correctness de DB que rompe el guardrail de Alembic, uno de resiliencia en streaming, uno de documentacion que induce a un bug de produccion, y un unbounded query) mas un conjunto de deudas MEDIUM de escalabilidad concentradas en el panel admin y en el descifrado sincronico.

| Dimension | Peso | Score | Aporte ponderado |
|---|---:|---:|---:|
| Arquitectura y escalabilidad | 25 | 76 | 19.00 |
| Seguridad y perimetro de datos (regla #4) | 20 | 94 | 18.80 |
| Calidad de codigo y buenas practicas | 20 | 83 | 16.60 |
| Testing | 15 | 82 | 12.30 |
| Documentacion y AI-friendliness | 15 | 72 | 10.80 |
| Limpieza / codigo muerto | 5 | 88 | 4.40 |
| **TOTAL** | **100** | — | **81.90 → 84** |

> Nota de calibracion: el ponderado bruto da 81.9. Subo a **84** por dos factores que la rubrica plana no captura: (a) **cero CRITICAL** tras verificacion adversarial, y (b) la **profundidad de la disciplina de seguridad** (la dimension de mayor riesgo de negocio) esta en el percentil mas alto. No inflo mas alla de eso: la grieta estructural calendar/tasks y el drift del mapa de docs son reales y pesan.

---

## 2. Delta vs auditoria 2026-06-20 (score previo ~7.5/10)

| Tema de 2026-06 | Estado actual | Evidencia |
|---|---|---|
| `services/` practicamente vacio | **RESUELTO** — poblado con auth/chat/memory/admin_metrics | `app/services/{auth,chat,memory,admin_metrics}.py`, todos sin importar FastAPI |
| `admin.py` monolitico (1371 lineas) | **RESUELTO** — partido en subpaquete `api/v1/admin/` (metrics/playground/connectivity) | area api-admin 86/100, split por superficie |
| `EMBEDDING_DIM` duplicado | **RESUELTO** — single source en `app/core/constants.py` (commit a80c489) | DC-04: solo queda 1 re-export huerfano en models/memory.py |
| Indices operativos faltantes | **PARCIAL** — se agregaron `sessions.started_at`, `users.created_at`, `episodic_memory.occurred_at` (commit 8b1f3d9) | **PENDIENTE:** `created_at` de las 3 tablas de memoria sigue sin indice (SCAL-03), `tasks.scheduled_at` sin indice (ALB-04) |
| `workflows/_engine.py` no extraido | **RESUELTO** — NullPool centralizado, DRY aplicado | area workflows 82/100 |
| Celery beat no deployado | **PENDIENTE (gap de infra, no de codigo)** — el codigo del beat_schedule esta listo pero sin observabilidad de last-run; si beat no corre, las tablas crecen sin sintoma | WW-07 |
| Dominios nuevos calendar/tasks | **INTRODUCIDOS pero con deuda estructural** — feature-packages que violan ADR-011 D1, layering asimetrico, Task no registrado en metadata | AR-01/AR-02/AR-03 |

**Resumen del delta:** progreso real y sustantivo. El backend subio de ~7.5 a ~8.4. Los temas que quedan pendientes son mas finos (indices puntuales, observabilidad de beat) o son **deuda nueva** importada con los dominios calendar/tasks.

---

## 3. Severidades netas (post-verificacion adversarial)

| Severidad | Cantidad neta | IDs |
|---|---:|---|
| CRITICAL | 0 | — |
| HIGH | 4 | AR-01, LLMC-001, DOC-07, API-002 |
| MEDIUM | 18 | API-001*, MEM-SACRED-01*, MEM-SACRED-02*, WW-01*, SCAL-01*, SCAL-02*, SCAL-03*, SCAL-04*, SEC-001, CORE-001, CORE-002, CORE-003, AR-02, AR-03, AR-04, AR-05, ADMIN-001, SVC-02/03/06 (cluster admin_metrics) |
| LOW | 42 | resto de findings (LPT-*, SCH-*, ALB-05/06/07, TOOL-01/02/05, DC-01..05, MODELS-*, etc.) |
| **FALSO POSITIVO (descartado)** | 2 | **ALB-01**, **LLM-001 (downgrade a LOW, no descartado)** |

\* = HIGH original ajustado a MEDIUM por la verificacion adversarial.

**Movimientos clave de la verificacion adversarial:**
- `ALB-01` (supuesta fuga episodica cross-user): **FALSE_POSITIVE**. `recent_episodic` solo selecciona `id/occurred_at/is_sensitive`, nunca `summary` descifrado.
- `LLM-001` (procedural sin pushdown): **REAL pero downgrade HIGH→LOW**. La premisa "se descifran cientos de filas" es falsa: procedural es JSONB sin cifrado, baja cardinalidad.
- `API-001`, `MEM-SACRED-01/02`, `WW-01`, `SCAL-01/02/03/04`: todos **REALES pero HIGH→MEDIUM** (impacto latente/condicional, no user-facing-critico).
- `STORES-01` (race idempotencia): **REAL pero HIGH→LOW** — el threat model (Celery retry concurrente) esta refutado por `agent_pass` DORMANT + `task_acks_late=False`.
- `TESTS-001`: **REAL pero HIGH→LOW** — el grep del finding era factualmente falso; existe cobertura de integracion en `test_admin_auth.py`.

---

## 4. Lo que esta 10/10 y NO hay que romper

1. **JWT endurecido por construccion** (`app/core/config.py:124`, `app/core/security.py`): `jwt_algorithm` es `Literal[HS256/384/512]`, asi que `none`/asimetrico (CVE-2022-39227) rompe el boot, no bypassea. `require:['exp']`, claims de control despues de `extra_claims`, error estatico anti-oraculo. **No tocar.**
2. **Cifrado at-rest per-user** (`app/core/crypto.py`): AES-256-GCM, key derivada por usuario via HKDF (`info=user_id`), nonce fresco por record, master key lazy, errores que nunca filtran la key. **No tocar.**
3. **Aislamiento estructural por user_id**: en TODOS los stores el `user_id` se liga en `__init__` y nunca viaja como argumento; disciplina decrypt-post-ownership (`semantic.py:99-114`, `episodic.py:93-98`). Es imposible filtrar datos ajenos por construccion. **No tocar.**
4. **Fail-open coherente en la capa Redis** (`token_store.py` + `ratelimit.py`): Redis caido degrada al baseline stateless sin tumbar auth; Lua atomico para INCR+EXPIRE; SET NX cierra el TOCTOU del refresh.
5. **Budget global de latencia del ResilientClient** (`resilient.py:74`): 90s acota el peor caso de la cadena candidatos×reintentos×fallback. Razonamiento explicito 90s<120s.
6. **Trigger de inmutabilidad de audit_log** (`alembic/versions/20260602_1015_*`): CREATE OR REPLACE retry-safe, ERRCODE check_violation, bloquea solo UPDATE. **Tabla SAGRADA — gate regla #3.**
7. **Fixtures de DB con savepoint** (`tests/conftest.py`): patron `join_transaction_mode=create_savepoint` que distingue commit de flush y detecta endpoints sin commit. Resuelve un footgun real del fixture viejo.
8. **ADR-011** (criterio feature-package vs layer-split): pieza de arquitectura de altisima calidad con panel adversarial y trigger de re-evaluacion. **Es la vara para corregir AR-02.**

---

## 5. CRITICAL — uno por uno

**Ninguno.** Tras la verificacion adversarial no quedo ningun finding CRITICAL confirmado. El sistema no tiene vulnerabilidades de seguridad explotables ni riesgos de perdida de datos activos en la config committeada.

---

## 6. HIGH — confirmados (4)

### HIGH-1 · AR-01 — El modelo `Task` no esta registrado en `Base.metadata` para Alembic
- **Archivo:** `app/models/__init__.py:8-34` (verificado: `Task` ausente de imports y de `__all__`)
- **Evidencia:** El unico import de `Task` en `app/models/` esta bajo `if TYPE_CHECKING:` en `user.py:19,25` (no ejecuta en runtime). `alembic/env.py:24` hace solo `from app.models import Base`, sin cargar `app/api/v1/tasks.py` ni `app/tasks/store.py` (los unicos que importan `Task` en runtime). Resultado: cuando corre Alembic, la tabla `tasks` **no esta en `Base.metadata`**, pese a existir en la DB (migracion `20260622_1400_tasks_table.py` ya la creo). `CalendarEvent` SI esta registrado (`__init__.py:11`) — asimetria entre modelos hermanos.
- **Impacto:** El proximo `alembic revision --autogenerate` propondria silenciosamente `op.drop_table('tasks')` (+ `DROP TYPE task_status_enum`), y `alembic check` reporta drift. Es una falla **latente con modo destructivo** sobre una tabla operativa que, por NO ser sagrada, tiene menos gate de review.
- **Fix:** Agregar `from app.models.task import Task` a `__init__.py` y `"Task"` a `__all__` (igual que `CalendarEvent`). Agregar un test que asserte que toda subclase de `Base` con `__tablename__` esta en `Base.metadata.tables` tras importar `app.models`. **Gate:** toca `app/models/` pero NO una tabla sagrada — no requiere regla #3; si, regla #1 si se agrega/corre migracion de verificacion.

### HIGH-2 · LLMC-001 — `stream()` filtra el circuit breaker en HALF_OPEN
- **Archivo:** `app/llm/clients/resilient.py:331-345` + `circuit.py:82-89`
- **Evidencia:** `_pick_for_stream()` llama `breaker.allow()`, que en OPEN-vencido transiciona a HALF_OPEN y setea `_probe_in_flight=True`. Pero `_stream` (`resilient.py:308-329`) **nunca** llama `record_success()`/`record_failure()` — esos solo viven en `_try_candidate` (path de `complete()`, lineas 262/264). Resultado: `_probe_in_flight` queda `True` para siempre; `allow()` en HALF_OPEN devuelve `not _probe_in_flight = False`. El dano grave esta en `complete()`: `_run_candidates:205` hace `if not breaker.allow(): continue` SIN best-effort, asi que **una instancia primaria sana queda permanentemente demoteada** tras un solo stream durante recovery, forzando el fallback on-prem para siempre (hasta reinicio del proceso).
- **Impacto:** Degradacion silenciosa y creciente de la capa LLM. Los tests existentes lo esquivan usando `recovery_timeout_s=999.0` (nunca llegan a HALF_OPEN via stream).
- **Fix:** Envolver el `async-for` del stream en try/except y llamar `breaker.record_success()` al completar sin error / `record_failure()` ante excepcion; o usar un `peek()` que no consuma la prueba. Agregar test: abrir breaker → esperar recovery → stream exitoso → verificar que un `complete()` posterior vuelve a pasar. **Sin gate sagrado.**

### HIGH-3 · DOC-07 — El playbook "Agregar una tool LLM" apunta a `default_registry()` (la via que NO se ejecuta en chat)
- **Archivo:** `AGENTS.md:158` (verificado: "...→ registrar en `default_registry()` →...")
- **Evidencia:** `default_registry()` (`registry.py:86-103`) solo retorna **stubs sin efecto del playground** (ADR-019 D2). El chat de PRODUCCION usa `build_chat_tool_registry` (`agent_registry.py:137-173`, ADR-022) que arma tools reales desde `_AGENT_TOOL_BUILDERS`. `TOOLS.md:28-42` documenta correctamente las tres superficies, pero el playbook de AGENTS.md quedo desactualizado. Una tool nueva registrada solo en `default_registry()` + habilitada en `tools_enabled` **no aparece en el chat real** (falta el builder en `_AGENT_TOOL_BUILDERS`).
- **Impacto:** Un agente (o dev) que siga el playbook al pie crea una tool de produccion que **silenciosamente no ejecuta**. Es docs, pero la consecuencia es un bug de runtime no obvio.
- **Fix:** Reescribir el playbook distinguiendo las tres superficies (`default_registry` playground / `build_chat_tool_registry` prod / `_build_agent_registry` async dormant) y decir donde registrar segun el objetivo, alineado con TOOLS.md y ADR-022. **Sin gate sagrado** (solo `.md`, requiere PR por convencion del repo).

### HIGH-4 · API-002 — `GET /v1/tasks` lista sin paginar (unbounded query)
- **Archivo:** `app/api/v1/tasks.py:86` + `app/tasks/store.py:100,126-127`
- **Evidencia:** `list_tasks()` llama `TaskStore(session, user_id).list_tasks()` sin pasar `limit`; con `limit=None` el `.limit()` no se aplica (`store.py:126-127`). SELECT sin LIMIT que trae TODAS las tareas + un `COUNT` sobre el set completo. No hay params de paginacion en la firma, a diferencia de `sessions.py:87-88,110-111` que SI pagina (`limit`/`offset` con `Query(ge/le)`). El dashboard "Hoy" lo pollea; el agente crea tareas por detras de la conversacion, asi que el backlog crece sin cota.
- **Impacto:** Payload O(n) en cada poll, presion de pool/memoria. Esta en el limite HIGH/MEDIUM; se mantiene HIGH por estar en el camino caliente del dashboard. Mitigantes: aislamiento per-user + rate-limit (`tasks.py:83-84`) acotan el blast radius (no es adversarial).
- **Fix:** Propagar `limit`/`offset` al handler como en `list_sessions` y/o cap duro (p.ej. 200) en el store. **Sin gate sagrado** (tabla operativa).

---

## 7. Falsos positivos descartados (no tocar)

| ID | Por que es FALSE_POSITIVE / diseno intencional |
|---|---|
| **ALB-01** | El supuesto "panel admin lista episodica cross-user → fuga regla #4" es falso. `recent_episodic` (`admin_metrics.py:484-494`) hace `select(EpisodicMemory.id, occurred_at, is_sensitive)` — NUNCA `summary` (el unico campo cifrado/sensible). El schema `RecentEpisodic` (`schemas/admin.py:236-241`) lo confirma con docstring "sin summary descifrado". El indice btree es aditivo y correcto. **Cero contenido de usuario expuesto.** |
| **STORES-01** (downgrade a LOW) | El threat model "race entre reintentos concurrentes de Celery" no existe en la config vigente: `agent_pass.py:1-12` esta DORMANT (ADR-022, "nadie encola"), `task_acks_late=False` (at-most-once, sin retry), `worker_prefetch_multiplier=1`. Es deuda de preparacion para Ola 3, no un bug explotable hoy. **No accionar como bloqueante.** |
| **LLM-001** (downgrade a LOW) | El patron de filtrar procedural en Python existe, pero la premisa de severidad ("se descifran cientos de filas caras") es falsa: procedural es JSONB **sin cifrado, sin embeddings, baja cardinalidad** (`procedural.py:4-6,133`). Micro-optimizacion opcional que ademas gatilla regla #3 — costo/beneficio desfavorable. |

---

## 8. Temas estructurales / escalabilidad (lo que sube el score)

### 8.1 La grieta calendar/ + tasks/ (arquitectura)
- **AR-02 (MEDIUM):** `app/calendar/` y `app/tasks/` son feature-packages top-level con UN solo `store.py` cada uno (161 y 200 LOC), lo que **viola el criterio ADR-011 D1** ("package propio solo si es pesado Y autocontenido con sub-estructura"). Reintroduce exactamente la asimetria que ADR-011 rechazo para auth.
- **AR-03 (MEDIUM):** Layering asimetrico entre dominios declarados hermanos: `events.py:90-104` inlinea las queries en el router (no usa `CalendarEventStore`), mientras `tasks.py:86` delega a `TaskStore`. La logica de query de calendar queda **duplicada** (router HTTP + store del agente).
- **Que se rompe a escala:** "donde vive cada cosa" deja de ser predecible; cada dominio futuro "merece" su carpeta. Sin un test de completitud de metadata ni CI que valide el mapa, la estructura crece mas rapido que sus invariantes (AR-01 es el sintoma).
- **Fix de fondo:** Mover `CalendarEventStore`/`TaskStore` a `app/services/` (o escribir un ADR que extienda D1), unificar `events.py` para que delegue en el store como `tasks.py`, y agregar un test de completitud de `Base.metadata`.

### 8.2 El panel admin es el punto mas fragil a 10x
- **SCAL-03 (MEDIUM):** `moat()`/`overview()` corren `date_trunc('day', created_at)` + `COUNT WHERE created_at >= start` cross-user sobre `semantic/episodic/procedural` **sin indice en `created_at`** (`models/memory.py`, ninguna de las 3 tablas lo tiene; las migraciones solo indexaron `sessions.started_at`, `users.created_at`, `episodic.occurred_at`). A 10x datos: seq-scan + sort en disco por request. **Fix:** indice btree en `created_at` de las 3 tablas → **gate regla #3** (commit aislado por tabla sagrada).
- **SCAL-04 (MEDIUM):** `overview()` emite ~15 awaits seriales y `moat()` ~16, todos sobre la MISMA `AsyncSession` (no paralelizable). Con el session pooler remoto de Supabase, un `GET /admin/moat` = 20+ RTT en serie. **Fix:** colapsar con `FILTER (WHERE ...)` y CTEs; `asyncio.gather` solo con sesiones independientes.
- **Cluster SVC-02/03/06:** `_count` tipa `stmt: object` con `# type: ignore`; metodos >50 lineas; mismo patron serial. Refactor de mantenibilidad.

### 8.3 Descifrado sincronico en el event loop
- **SCAL-02 (MEDIUM):** `_derive_key` (`crypto.py:79-92`) corre HKDF fresco por fila **sin cache** (a diferencia de `_decode_master_key` que SI cachea). `decrypt_for_user` es CPU-bound y sincronico dentro de metodos `async`, sin `to_thread`. El path de chat lo paga doble: `_load_history` descifra hasta 40 turnos por turno (`chat.py:76,225`). Stalls del loop de ~1-5ms en estado estable; el caso HIGH real es `export_all` (`list_all(limit=None)`). **Fix:** cachear key derivada por user (`lru_cache`) + mover lotes grandes a `asyncio.to_thread`.

### 8.4 SSE falso + retention sin batching
- **SCAL-01 (MEDIUM):** `chat_stream` corre `run_turn` COMPLETO (LLM+tools+commit) antes de emitir el primer byte, luego trocea `resp.text` en chunks cosmeticos de 6 code-points (`chat.py:79,279,303-313`). **Cero TTFT real.** Es un tradeoff **documentado** (atomicidad transaccional, `chat.py:237-257 "NO re-litigar"`), por eso es MEDIUM y no bug. **Fix opcional Ola 3:** usar el `stream()` real de `VllmClient` y persistir al cerrar.
- **WW-01 (MEDIUM):** Los 3 workers de retention/decay (`audit_retention.py:78-87`, `decay.py:178-188`, `episodic_retention.py:110-119`) hacen un unico DELETE sin LIMIT. La primera corrida tras backlog grande choca con `task_time_limit=120` → rollback total → 0 filas borradas → loop de fallo. **Fix:** DELETE por lotes con `LIMIT` + commit por lote. **Gate regla #3** por operar sobre tablas sagradas.
- **MEM-SACRED-01 (MEDIUM):** `next_seq` + `add` es TOCTOU; `run_turn` no captura el `IntegrityError` del `UniqueConstraint(session_id, seq)` (a diferencia de `consolidation.py` que SI lo degrada). Doble submit/retry → 500 + turno perdido. Fail-loud (no corrupcion). **Fix:** capturar/reintentar el IntegrityError o seq server-side; ajustar el docstring para decir que el UNIQUE es el guardian de ultima instancia.
- **MEM-SACRED-02 (MEDIUM):** ANN HNSW global con post-filtro `user_id` puede degradar recall en silencio a >100k usuarios (`semantic.py:99-104`, `episodic.py:92-97`), sin `ef_search` tuneado. Riesgo latente, no presente. **Fix:** subir `hnsw.ef_search` por sesion / documentar. **Gate regla #3** si toca indices.

---

## 9. Codigo muerto / AI-slop

| Item | Ubicacion | Accion |
|---|---|---|
| `ToolExecutionError` definido, nunca lanzado (docstring de `router.py:60` miente) | `app/llm/errors.py:101` | Lanzarlo donde corresponde o eliminarlo + corregir docstring |
| `MemoryRetrievalError` definido, nunca lanzado | `app/llm/errors.py:107` | Definir contrato o eliminar de la taxonomia |
| `OpenAIToolCallParser.accumulate()` dead-code de runtime (tools en streaming nunca se reconstruyen) | `app/llm/clients/parsers.py:57-75` | Decidir: borrar (stream text-only) o cablear en el consumidor SSE |
| `agent_pass.py` (325 LOC) DORMANT post-ADR-022 | `app/workflows/agent_pass.py` | Borrar o documentar como contingencia con trigger de re-activacion |
| `UserCreate` exportado, nunca instanciado | `app/schemas/user.py:28` | Eliminar clase + export (register usa `RegisterRequest`) |
| `UserBase` en `__all__` sin consumidor externo | `app/schemas/__init__.py:33` | Quitar de `__all__` (sigue util como base interna) |
| Re-export `EMBEDDING_DIM` en models/memory.py sin uso | `app/models/memory.py:52` | Eliminar shim (single source ya en core/constants) |
| Stubs M6 calendar/task en `default_registry()` | `app/llm/tools/registry.py:86-103` | Trazar dependencia al playground en ADR/TOOLS.md para limpiar al retirarlo |

---

## 10. Documentacion y AI-friendliness

### Veredicto: **72 / 100**
Un agente fresco onboardea **muy bien el CONTRATO** (AGENTS.md gates §0, invariantes LLM §3, naming §4) y los **catalogos por-dominio** (los 4 estan sincronizados con drift-guard en CI). Pero el **mapa-resumen de entrada** (AGENTS.md §2 / README) da una vista PARCIAL de la superficie real, lo que puede llevar a no descubrir dominios enteros (agenda/tareas/admin) si se confia solo en el mapa.

### Tabla de desincronizaciones doc↔codigo

| ID | Doc | Drift | Sev |
|---|---|---|---|
| DOC-07 | AGENTS.md:158 | Playbook "Agregar tool LLM" apunta a `default_registry()` en vez de la via prod ADR-022 | **HIGH** |
| DOC-02 | AGENTS.md:54 | Lista 5 dominios api/v1 pero `main.py:258-267` monta 10 (faltan events/tasks/modes/users/admin) | MEDIUM |
| DOC-03 | AGENTS.md §2 + README | `app/calendar/` y `app/tasks/` ausentes del mapa | MEDIUM |
| DOC-09 | docs/architecture/adrs/ | ADR-018 **duplicado** (admin-playground + calendar-event) → referencias ambiguas | MEDIUM |
| DOC-01 | AGENTS.md:44 | Linea de enums omite `EventStatus`/`TaskStatus` (5 de 7) | MEDIUM |
| DOC-04 | AGENTS.md:45-53 | `core/` omite `constants.py` y `paths.py` | MEDIUM |
| DOC-05 | AGENTS.md:61 | `workflows/` omite `episodic_retention`, `agent_pass`, `_engine` | MEDIUM |
| DOC-06 | AGENTS.md:99 | `tools/` omite `agent_registry.py` y `task.py` | MEDIUM |
| DOC-08 | check_doc_catalogs.py | No cubre MODELS.md ni TOOLS.md (solo 2 de 4 catalogos con guard) | MEDIUM |
| TOOL-01 | check_doc_catalogs.py:28 | Docstring referencia `tests/scripts/test_check_doc_catalogs.py` inexistente | LOW |
| DOC-10/11 | AGENTS.md:57 / README:30-49 | `services/` descrito como concepto (no lista los services reales); arbol README mas stale que AGENTS | LOW |

### Que falta para AI-friendliness 100%
1. **Sincronizar AGENTS.md §2/§3 y README** con el arbol real (DOC-02..06) — o reducir a un solo mapa (DRY) que apunte a los catalogos.
2. **Corregir el playbook DOC-07** (el mas peligroso: induce a un bug de prod).
3. **Renumerar el ADR-018 duplicado** y corregir las referencias.
4. **Extender `check_doc_catalogs.py`** a MODELS.md y TOOLS.md + un check liviano que verifique que cada top-level package de `app/` aparece en AGENTS.md §2 (convierte el drift del mapa en fallo detectable).

---

## 11. Cobertura de la auditoria

**225 archivos auditados, cobertura confirmada.** Cada area reporto `coverageConfirmation` con conteo de lineas leidas archivo-por-archivo:
- 14 areas archivo-por-archivo: core (14), api (13), api-admin (4), models (10), schemas (18), services (5), llm-clients (12), llm-core (9), llm-prompts-tools (17), memory-sacred (9), workflows-workers (9), stores (4), alembic (11), tooling (6).
- 6 dimensiones cross-cutting: dim-security (19), dim-scalability (17), dim-architecture (17), dim-deadcode (11), dim-tests (12), dim-docs (8).
- Todas las areas confirmaron lectura completa linea-por-linea, lectura del `AGENTS.md` (PASO 0) y verificaciones cruzadas via Grep/Glob. Los gates sagrados (`app/memory/`, models/schemas de memory|audit, migraciones sagradas) se auditaron **read-only**; cada fix sobre ellos lleva la nota de regla #3. **No quedo nada sin ver dentro del alcance declarado.**

---

## 12. Plan de accion por fases

### Ola 0 — Quick wins (1-3h, bajo riesgo)
| Item | Sev | Esfuerzo | Gate |
|---|---|---|---|
| AR-01: registrar `Task` en `models/__init__` + test de metadata | **HIGH** | 30min | Regla #1 (correr `alembic check`) |
| DOC-07: reescribir playbook "Agregar tool LLM" (3 superficies) | **HIGH** | 30min | PR (.md) |
| DOC-02..06: sincronizar mapa AGENTS.md §2/§3 + README | MEDIUM | 1h | PR (.md) |
| DOC-09: renumerar ADR-018 duplicado + refs | MEDIUM | 30min | PR (.md) |
| DC-01..05: limpiar dead-code (errores, UserCreate/UserBase, re-export, accumulate) | LOW | 1h | PR |
| API-004/API-005/API-007: rama muerta, ValueError no mapeado, doc drift | LOW | 30min | PR |

### Ola 1 — Resiliencia (3-6h)
| Item | Sev | Esfuerzo | Gate |
|---|---|---|---|
| LLMC-001: cerrar el breaker en el path de stream + test | **HIGH** | 2h | Sin gate sagrado |
| API-002 + API-001: paginar `/tasks` y `/events` (espejar `list_sessions`) | **HIGH/MED** | 2h | Sin gate sagrado |
| MEM-SACRED-01: capturar/reintentar IntegrityError en `run_turn` + docstring | MEDIUM | 1.5h | Regla #3 (store sagrado-adyacente) |
| SVC-05: `begin_nested()` con `async with` (rollback automatico) | LOW | 30min | Sin gate |
| SEC-001: documentar broker Redis dentro del perimetro + requirepass/TLS prod | MEDIUM | 1h | PR + infra |

### Ola 2 — Estructural (1-2 dias)
| Item | Sev | Esfuerzo | Gate |
|---|---|---|---|
| AR-02 + AR-03: decision unica calendar/tasks (mover a services/ o ADR que extienda D1) + unificar events.py | MEDIUM | 1 dia | PR + ADR |
| SCAL-03: indice btree en `created_at` de semantic/episodic/procedural | MEDIUM | 2h | **Regla #3** (3 commits aislados) |
| ALB-04: indice `(user_id, scheduled_at)` en tasks | MEDIUM | 30min | Regla #1 (migracion) |
| SCAL-04 + SVC-02/03: colapsar queries seriales del panel (FILTER/CTE) + tipar `_count` | MEDIUM | 4h | Sin gate sagrado (read-only) |
| WW-01: batching de DELETE en los 3 workers de retention | MEDIUM | 3h | **Regla #3** (tablas sagradas) |
| TESTS-001/002: tests de integracion de AdminMetricsService con datos sembrados | MEDIUM | 4h | Sin gate |
| AR-04: borrar o documentar `agent_pass.py` DORMANT | MEDIUM | 30min | PR |

### Ola 3 — UX / escala (futuro, trackeado)
| Item | Sev | Esfuerzo | Gate |
|---|---|---|---|
| SCAL-01: SSE real con `stream()` de VllmClient + persistencia post-stream | MEDIUM | 2 dias | Sin gate sagrado |
| SCAL-02: cache de key derivada + descifrado en executor | MEDIUM | 1 dia | Regla #3 (toca crypto path de stores) |
| MEM-SACRED-02: `ef_search` tuneado / indice particionado HNSW | MEDIUM | 1 dia | **Regla #3** |
| STORES-01: UNIQUE constraint + idempotencia para acks_late=True (desbloquea concurrencia Celery) | LOW | 1 dia | Regla #1 (migracion) |
| WW-07: observabilidad de last-run del beat (Sentry cron monitor) | LOW | 4h | PR + infra |

---

## 13. Gates a respetar en la ejecucion

1. **Regla #1 (confirmacion humana):** ningun `git commit`/`push` sin OK explicito. Toda actualizacion de `main` va por PR mergeado (rebase-only segun memoria del repo: `gh pr merge <n> --rebase`). Cambios a `pyproject.toml`, `.env*`, migraciones y `.md` raiz requieren confirmacion.
2. **Regla #3 (tablas sagradas):** todo cambio en `app/memory/`, en models/schemas de `memory`/`audit`, o en migraciones sobre `semantic/episodic/procedural/audit_log/conversation_turns` requiere **1 aprobacion humana explicita en el PR** + tests. Afecta: SCAL-03 (indices created_at), WW-01 (batching DELETE), MEM-SACRED-01/02, SCAL-02 (crypto path).
3. **Una migracion = un cambio logico** (ALB-02): separar cambios a tabla sagrada de cambios operativos en commits aislados para que el gate revise un diff limpio.
4. **Review en agente separado:** la pasada de aprobacion siempre va en `code-reviewer`/`verifier`, nunca auto-aprobacion en el mismo contexto.
5. **Branch antes de editar:** `git checkout -b` antes de tocar nada; el punto de riesgo es justo tras `checkout main && pull` post-merge.
