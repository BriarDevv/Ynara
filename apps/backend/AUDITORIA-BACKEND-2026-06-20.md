# Auditoría full del backend — Ynara

> **Fecha:** 2026-06-20 · **Alcance:** `apps/backend` punta a punta (85 archivos, ~15.8k líneas de `app/`)
> **Método:** workflow multi-agente read-only (31 agentes, ~2.58M tokens) — 12 áreas archivo-por-archivo + 4 dimensiones cross-cutting (código muerto, seguridad/perímetro, escalabilidad, arquitectura) + **verificación adversarial** de cada hallazgo CRITICAL/HIGH.
> **Archivo no trackeado** — entregable de trabajo. Decidí vos si lo movés a `docs/`, lo dejás, o lo borrás cuando terminemos.

---

## 1. Veredicto ejecutivo

**Score global: ~7.5/10.** El backend es **sólido y de calidad de producción** en sus partes críticas (auth/seguridad 9/10, capa LLM 8/10, memoria 8/10). No es un 10 todavía por: **un (1) problema operativo CRITICAL**, un puñado de endurecimientos HIGH, y **deuda estructural acotada** (la capa `services/` está casi vacía → la lógica de negocio vive en routers; `admin.py` tiene 1371 líneas). Nada es un bug que rompa el producto hoy, pero hay cosas que **a escala** (más usuarios/datos o varios workers) se vuelven dolorosas.

**¿Está andando?** Sí. Suite completa **verde: 1263 tests** (922 unit + 341 integración contra DB real + Redis), exit 0. Verificado en esta corrida.

### Severidades (netas, después de verificación adversarial)

| Severidad | Cantidad | Qué son |
|---|---|---|
| 🔴 CRITICAL | **1** | El `celery beat` no está deployado → los 3 jobs periódicos nunca corren en prod |
| 🟠 HIGH | **7** | Endurecimientos de seguridad/escalabilidad reales (JWT, Dockerfile, índices, rate-limit, circuit breaker, Celery, settings) |
| 🟡 MEDIUM | ~51 | Mantenibilidad + performance + dead-code |
| ⚪ LOW | ~64 | Estilo, scaffolding vestigial, micro-optimizaciones |
| ❌ Falsos positivos | 3 | Descartados: eran diseño intencional documentado (no tocar) |

**130 hallazgos únicos** en total. La verificación adversarial **descartó 3 falsos positivos** y **bajó la severidad de 4 HIGH** (admin_audit, `updated_at`, mock de tests → MEDIUM; SoftTimeLimit → LOW) — o sea, los HIGH que quedan son reales y verificados con evidencia de código.

---

## 2. Lo que ya está 10/10 (no romper)

Esto es deliberadamente bueno y hay que **preservarlo** en cualquier refactor:

- **Auth + seguridad (9/10):** TOCTOU del refresh cerrado con `SET NX EX` atómico, reuse-detection a nivel familia (`sid`) retry-safe, login timing-safe + anti-enumeración (status+body+timing idénticos), AES-256-GCM per-user con HKDF-SHA256 y nonce fresco por record, fail-open documentado.
- **Regla #4 (perímetro de datos) impecable** en todo el backend: cada log emite solo `type(exc).__name__`/UUIDs/enums; el scrubber de Sentry dropea body/cookies/headers/breadcrumbs/exception-values; el rate-limit hashea el email con sha256.
- **Aislamiento por usuario ESTRUCTURAL:** el `user_id` se liga en el `__init__` de cada store y deriva la key de cifrado — el caller no puede leakear datos de otro usuario por construcción. Anti-oracle 404 consistente en sessions/memory.
- **Capa LLM bien estratificada:** clientes stateless, httpx inyectado, cadena de resiliencia primario→on-prem→degradado que **nunca** propaga excepción de infra al caller, parsers de tool-call defensivos.
- **db_guard anti-prod** (incidente 2026-05-31), enums con ownership de tipo PG, migraciones reversibles con `downgrade()` simétrico, trigger de inmutabilidad de `audit_log` a nivel DB.
- **Tests excepcionalmente maduros:** "session joined into external transaction" con savepoints, cero mocks de DB en integración, cobertura densa de crypto/auth/regla-#4.

---

## 3. 🔴 CRITICAL — arreglar antes de cualquier deploy real

### C1. El `celery beat` no está deployado: los 3 jobs periódicos nunca corren en prod
**`infra/docker/docker-compose.yml:28-51`** · *correctness*

El compose define un único servicio `worker` con `celery worker --concurrency=2`, **sin** `-B/--beat` ni un servicio `beat` separado. Pero `celery_app.py` define `beat_schedule` con tres jobs: `decay_procedural`, `purge_audit_log`, `purge_episodic_memory`. Sin un proceso beat:
- los **episodios vencidos nunca se purgan** → regresión de privacidad (ADR-007 D2),
- el **`procedural_memory` nunca decae** → contrato ADR-007 D1 roto,
- el **`audit_log` crece sin límite** → riesgo de storage/OOM eventual.

**Fix:** agregar un servicio `beat` separado:
```yaml
beat:
  command: uv run celery -A app.workers.celery_app beat --loglevel=info --scheduler celery.beat.PersistentScheduler
  volumes: [ celerybeat-data:/var/run/celery ]   # schedule persistente
```
No usar `--beat` dentro del worker con `concurrency>1` (dispara tasks dobles).

---

## 4. 🟠 HIGH — confirmados con evidencia

### H1. JWT algorithm sin allowlist — riesgo de algorithm confusion
**`app/core/config.py:115`** · *security* · (el único que puede escalar a CRITICAL por mala config de operador)
`jwt_algorithm: str = Field("HS256", ...)` acepta cualquier string. `JWT_ALGORITHM=none` → bypass total de firma; `RS256` con secret simétrico corto → patrón CVE-2022-39227. `verify_token` propaga el valor sin validar.
**Fix:** `jwt_algorithm: Literal["HS256","HS384","HS512"] = "HS256"` + `field_validator` de arranque.

### H2. Dockerfile corre como root, sin usuario dedicado ni HEALTHCHECK
**`Dockerfile:1-37`** · *security*
`gunicorn` arranca como UID 0 → un RCE/path-traversal en la app o una dep da root en el contenedor. Sin `HEALTHCHECK`, el orquestador no distingue "vivo pero roto" de "sano".
**Fix (~4 líneas):** `RUN useradd -r -s /bin/false appuser && chown -R appuser /app` + `USER appuser` + `HEALTHCHECK ... CMD curl -fs http://localhost:8080/v1/health || exit 1` (curl ya está instalado, `/v1/health` ya existe).

### H3. `GET /memory/search` sin rate-limit: abuso de embedding
**`app/api/v1/memory.py:510-542`** · *security*
`search` corre el pipeline embed→ANN→rerank (caro en GPU/CPU) **sin** rate-limit, a diferencia de `export` y `wipe`. Un usuario autenticado puede disparar cientos de queries/s. No inyecta `TokenStoreDep`.
**Fix:** `check_memory_search_rate_limit` (bucket por `user_id`) antes de `build_memory_stores`, igual que el patrón ya presente.

### H4. `sessions.started_at` sin índice — full scans en todo el panel admin
**`app/models/session.py:42-49`** · *performance*
Casi todos los endpoints del panel filtran/agrupan por `started_at` (overview, heatmap que escanea **371 días**, active-users, modes, moat). Sin índice → sequential scan creciente por request. **`sessions` NO es sagrada** (operativa) → la migración no requiere gate regla #3.
**Fix:** índice btree sobre `started_at` (+ evaluar compuesto `(mode, started_at)` y parcial `WHERE ended_at IS NULL`). También indexar `users.created_at` (no sagrada).

### H5. Circuit breaker per-proceso: split-brain failover bajo escalado horizontal
**`app/llm/clients/circuit.py:39-110`** · *architecture*
El estado del breaker vive en memoria del proceso. El Dockerfile de prod corre **`gunicorn --workers 4`**: cada worker aprende los fallos por separado → hasta `4 × failure_threshold` requests pegan al endpoint caído antes de que abran todos; las pruebas HALF_OPEN se multiplican por worker. El propio docstring asume "1-2 procesos", contradicho por los 4 workers.
**Fix:** o mover el estado a Redis (los primitivos `set_flag/has_flag` de `RedisTokenStore` ya existen, ~100 líneas), **o** fijar 1-2 workers en un ADR explícito como cota de escalado. Decidir, no dejarlo implícito.

### H6. Celery AT-MOST-ONCE: pérdida silenciosa de consolidaciones a escala
**`app/workers/celery_app.py:74-82`** · *correctness*
`task_acks_late=False` → el broker ackea antes de ejecutar. Un crash/OOM/time-limit tras el ack pierde la consolidación **sin retry, sin dead-letter, sin alarma**. Está documentado como intencional (evitar duplicados hasta "Ola 3"), y `task_reject_on_worker_lost=True` es **inerte** hoy (da falsa sensación de protección). A escala + rolling deploys, la pérdida crece.
**Fix (sin esperar Ola 3):** dead-letter queue para `workflows.*` + TTL en el result backend para detectar consolidaciones faltantes por monitoreo. Ola 3: `task_acks_late=True` + search-before-add idempotente (el `_episode_exists()` ya es precedente).

### H7. `settings = get_settings()` a nivel módulo viola el patrón lazy del propio repo
**`app/main.py:29`** (y `app/workers/celery_app.py:27`) · *correctness*
Instancia `Settings` al **importar** el módulo → importar `app.main` sin `DATABASE_URL`/`JWT_SECRET` revienta con `ValidationError` en *collection time*. Además, el global `settings` se usa en `SecurityHeadersMiddleware.__call__`, dejando el switch de HSTS por entorno **no testeable** sin recrear la app (el docstring que dice lo contrario es incorrecto).
**Fix:** leer `environment` en el `__init__` del middleware vía `get_settings()` (la `lru_cache` lo hace O(1)); seguir el patrón lazy del resto.

---

## 5. ❌ Falsos positivos descartados (diseño intencional — NO tocar)

La verificación adversarial confirmó que **estos NO son problemas**:

1. **`resilient.py` breakers keyed por `id(client)` → "KeyError latente":** falso. El pool es inmutable post-arranque; nunca se reconstruye. (La parte *real* —breaker per-proceso— se captura en H5, que es la versión correcta del hallazgo.)
2. **`/memory/export` materializa y descifra todo en memoria (O(n)):** intencional y documentado ("on-prem, pocos hechos por user; no hace falta streaming"), con rate-limit + decay/retention como controles compensatorios. *Sigue siendo una mejora válida a futuro (ver E5), pero no es un bug HIGH.*
3. **NullPool: nueva conexión PG por task de Celery:** intencional y documentado ("decisión #4": evita "Future attached to a different loop" en prefork). Con `concurrency=2` el costo es marginal. *Optimización futura (ver E-workers), no bug.*

---

## 6. Temas estructurales para llegar a 10/10 escalable

El **gran tema** que separa el backend de un 9-10:

### S1. La capa `services/` está casi vacía → la lógica de negocio vive en los routers
Hoy `services/` solo tiene `auth.py`. Como consecuencia: `admin.py` (1371 líneas, rompe el límite de 800), `memory.py` (765), y `_run_chat_turn` (~160 líneas con la decisión de consolidación) viven en routers.
**Estructura objetivo:** `services/chat.py` (`ChatService.run_turn`), `services/memory.py` (`MemoryService`: list/get/update/delete/export/wipe/search + auditoría por-capa centralizada), `services/admin_metrics.py` (las 6 métricas como métodos que reciben `AsyncSession`). Los routers quedan como mapeo I/O→service→status. **Respeta la convención intencional** (services reciben deps por argumento, no importan FastAPI).

### S2. Partir `api/v1/admin.py` en subpaquete `api/v1/admin/`
Mezcla 4 dominios con ciclos de cambio y riesgo distintos: métricas read-only, playground LLM (sync/stream/agent), serving, connectivity (exec de subprocess). Sub-módulos: `metrics.py`, `playground.py`, `serving.py`, `connectivity.py` + `__init__.py` con router agregado. ~130 líneas de prelude del playground están **copy-pasteadas en los 3 endpoints** → extraer `_resolve_playground_request`.

### S3. Índices que faltan (operativos = sin gate; sagrados = con gate regla #3)
- **Sin gate:** `sessions.started_at`, `users.created_at` (H4).
- **Con gate regla #3:** `episodic_memory.occurred_at DESC`, `procedural_memory (user_id) WHERE stale=false`, `audit_log (user_id, created_at DESC)`, tunear HNSW (`m`, `ef_construction`), y `created_at` de las 3 capas.

### S4. Worker DB pool + utilidad compartida
Los 4 workflows duplican `create_async_engine(NullPool)+sessionmaker+commit+dispose` e importan el privado `_normalize_db_url` de `consolidation.py` (acoplamiento cross-module). Extraer `app/workflows/_engine.py` con `async with worker_session(cfg)`. (Opcional a escala: pool persistente por worker vía `worker_process_init`.)

### S5. Otros techos de escalabilidad mapeados
- **Streaming SSE "fake":** `/chat/stream` re-trocea una respuesta ya completa (mismo TTFB que `/chat`). Real token-por-token cuando el serving lo soporte (`CompletionChunk.delta_text` ya existe).
- **Export de memoria:** streaming/Celery con descarga diferida (ver FP#2).
- **Pushdown del filtro `stale` + orden por `confidence`** de procedural a la DB (hoy `list_all()` materializa todo en el hot path del context builder).
- **AES-GCM decrypt off the event loop** (`run_in_executor`) en search/export bajo carga concurrente.
- **Keyset pagination** en `/sessions` y memoria (hoy OFFSET).

---

## 7. Código muerto / AI-slop (para el `/ai-slop-cleaner`)

El backend está **muy limpio** (>95% del código es activo; dim-dead-code dio 8/10). Lo concreto a limpiar:

| Item | Ubicación | Acción |
|---|---|---|
| `EMBEDDING_DIM = 1024` **duplicado** | `llm/clients/embedding.py` **y** `models/memory.py` | Consolidar en una fuente de verdad (riesgo: corromper índices HNSW si divergen) |
| Modelo `AdminAudit` + migración + relationship **sin write-path** | `models/admin_audit.py`, migración `20260619` | Cablear (cierra gap de accountability del panel) **o** borrar + corregir docstring |
| Campos R2 de Cloudflare en `Settings` sin consumidor | `core/config.py` | Eliminar o mover a optional group (superficie de secrets innecesaria) |
| Deps de prod sin imports: **`authlib`, `boto3`** | `pyproject.toml` | ~30-50 MB + superficie de ataque; mover a optional o eliminar |
| `MemorySettingsUpdate` exportado sin endpoint `PATCH /memory/settings` | `schemas/memory.py:141`, `__init__.py` | Implementar o quitar del API surface |
| Errores `MemoryRetrievalError`, `ToolExecutionError` nunca lanzados | `llm/errors.py` | Cablear o eliminar (el docstring de `route()` los cita como manejados) |
| Stubs `memory.add` / `self._store` sin uso + comentarios "pendiente M8" vencidos | `llm/tools/memory.py` | Decidir si `memory.add` es no-op permanente y actualizar firmas |
| Stubs `calendar`/`reminder` en el registry de prod (siempre `not_wired_result`) | `llm/tools/` | Feature flag o registry "pending" separado |
| Exports huérfanos en `__init__.py` | `schemas/__init__.py`, `models/__init__.py` | Limpiar API pública implícita |

---

## 8. Otros HIGH→bajados y MEDIUM destacados

- **`updated_at onupdate` ignorado en bulk updates** (`models/base.py:41-46`, HIGH→**MEDIUM**): el decay worker usa `sa_update` (bypassa el ORM), así que `procedural_memory.updated_at` queda congelado. Solo afecta un campo read-only de presentación. Fix: trigger DB `BEFORE UPDATE` (mismo patrón que `audit_log`, **gate regla #3**).
- **`SoftTimeLimitExceeded` y `engine.dispose()`** (`workflows/consolidation.py`, HIGH→**LOW**): el `finally` puede no correr ante SIGALRM, pero con NullPool no hay pool que drenar y Postgres reclama la conexión. Documentar la limitación.
- **Mock de DB en tests unit** (`tests/workflows/test_consolidation.py`, HIGH→**MEDIUM**): `MagicMock(spec=AsyncSession)` viola AGENTS §5 y ejercita el branch equivocado (savepoint). Fix: pasar `session=None` (contrato documentado de `apply_ops` para unit).
- **Catálogos de docs desactualizados:** migración `20260619` no está en `MIGRATIONS.md`; `/v1/admin/connectivity` no está en `ENDPOINTS.md`. Agregar un check de CI que valide catálogo↔código.
- **Warnings de tests:** 3 corrutinas no-awaited (`_async_purge_episodic`, `_async_consolidate`, `_async_decay`) en tests de workflows; `InsecureKeyLengthWarning` (JWT secret de test < 32 bytes — confirmar que prod sí exige largo mínimo, que el fail-fast de `config.py` parece cubrir); `path_separator=os` faltante en `alembic.ini`.
- **Hardening de seguridad menor:** access token TTL default de 7 días (reducir a ~60 min, el refresh ya existe); CORS con `allow_methods=['*']`/`allow_headers=['*']` (restringir a explícitos); falta CSP/Permissions-Policy en el middleware; cerrar `openapi_url` en prod junto con `docs_url`.

---

## 9. Plan de acción priorizado

**Ola 0 — Quick wins de alto impacto (bajo esfuerzo, sin gate):**
1. 🔴 Deployar `celery beat` (C1) — *bloqueante para prod*.
2. 🟠 Allowlist de `JWT_ALGORITHM` (H1).
3. 🟠 Dockerfile: usuario no-root + HEALTHCHECK (H2).
4. 🟠 Rate-limit en `/memory/search` (H3).
5. 🟠 Índice `sessions.started_at` + `users.created_at` (H4) — *migración, requiere OK humano (regla #1)*.
6. Limpieza dead-code barata: `EMBEDDING_DIM`, deps `authlib`/`boto3`, exports huérfanos, R2 settings.

**Ola 1 — Resiliencia/operabilidad a escala:**
7. 🟠 Circuit breaker: decisión Redis vs ADR de 1-2 workers (H5).
8. 🟠 Celery DLQ + observabilidad de tasks perdidas (H6).
9. 🟠 `settings` lazy en `main.py`/`celery_app.py` (H7).
10. Worker DB engine compartido (S4).

**Ola 2 — Estructural para 10/10 (esfuerzo alto, mayor pago):**
11. Poblar `services/` (S1) → empezar por `MemoryService` y `ChatService`.
12. Partir `admin.py` en subpaquete (S2).
13. Índices sagrados + HNSW tuning (S3) — *gate regla #3 + OK humano*.

**Ola 3 — Mejoras de UX/escala (opcional según prioridad de producto):**
14. Streaming SSE real, export por streaming/Celery, pushdown procedural, keyset pagination, decrypt off-loop (S5).

### Gates a respetar en la ejecución
- **Regla #1:** OK humano antes de commit/push/migraciones; todo a `main` vía PR con rebase merge; rama nueva antes de editar.
- **Regla #3 (tablas sagradas):** cualquier índice/trigger sobre `semantic/episodic/procedural_memory` o `audit_log` → tests + **1 aprobación humana** en commit aislado.
- **Commits atómicos** (regla #7): uno por cambio lógico.
