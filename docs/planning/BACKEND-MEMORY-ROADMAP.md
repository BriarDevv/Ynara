# Backend · Memoria contextual + capa LLM — Roadmap

> **Estado**: v1 — punto de partida después de PR A (modelos + schemas + enums) mergeado
> **Fecha**: 2026-05-21
> **Owner**: @BriarDevv
> **Alcance**: `apps/backend` — desde el estado actual hasta tener el agente respondiendo con memoria viva.
> **Fuentes**: [`AGENTS.md`](../../AGENTS.md), [`docs/architecture/informe-tecnico.pdf`](../architecture/informe-tecnico.pdf), [`docs/architecture/adrs/`](../architecture/adrs/), Trello cards *Arquitectura de memoria contextual* + *Integración con backend LLM*.

---

## 0. Contexto

Este documento es el plan operativo para llevar el backend de Ynara desde su estado actual (modelos + schemas + enums mergeados en PR A) hasta el primer agente funcionando end-to-end con memoria contextual viva.

Se apoya en cuatro fuentes:

1. **Informe técnico §1.5 y §2.4** — dual-stack Gemma + Qwen, vLLM, LlamaIndex, Mem0, patrón ADD/UPDATE/DELETE/NOOP.
2. **ADR-002** — Gemma 4 26B-A4B (conversacional) + Qwen 3.5-9B (agente), cuantización Q4/Q5 para 16GB VRAM.
3. **ADR-004** — Postgres + pgvector como único vector store.
4. **ADR-007** — decay exponencial, retention diferenciada (`is_sensitive`), cifrado AES-256-GCM con HKDF.

### Por qué este plan existe ahora

- PR A (modelos + schemas + enums) cerró el contrato de datos. El siguiente paso natural es la migración Alembic, pero **necesita proyecto Supabase listo**.
- Hay dos cards de Trello (memoria contextual + integración LLM) que se solapaban; ya quedaron deslindadas, pero los pendientes están dispersos.
- El camino crítico hasta "agente respondiendo con memoria" tiene varias dependencias en cadena (Supabase → PR B → ADR-008 → PR C → auth → router → cliente vLLM) y conviene fijarlo antes de empezar a ejecutar en paralelo.

---

## Tabla de contenidos

1. [Estado actual](#1-estado-actual)
2. [Decisiones inmediatas (bloqueantes)](#2-decisiones-inmediatas-bloqueantes)
3. [Plan T1 — memoria contextual](#3-plan-t1--memoria-contextual)
4. [Capa LLM — router + cliente vLLM + prompts](#4-capa-llm--router--cliente-vllm--prompts)
5. [Workers Celery](#5-workers-celery)
6. [Endpoints FastAPI](#6-endpoints-fastapi)
7. [Camino crítico](#7-camino-crítico)
8. [Riesgos y bloqueantes](#8-riesgos-y-bloqueantes)
9. [Definition of Done](#9-definition-of-done)
10. [Referencias](#10-referencias)

---

## 1. Estado actual

### Hecho

| Pieza | PR | Detalle |
|---|---|---|
| Modelos SQLAlchemy de las 3 capas | PR #15 + #19 | `SemanticMemory`, `EpisodicMemory`, `ProceduralMemory` con BYTEA cifrado, HNSW, retention diferenciada |
| Modelo `User` + `ChatSession` + `AuditLog` | PR #15 | `retention_sensitive_days` (30-365), `record_hash` inmutable con CHECK regex |
| Schemas Pydantic + validator cross-field | PR #15 + #19 | `model_validator` para `is_sensitive` + `retention_days ≤ 365` |
| Enums compartidos | PR #15 | `Mode`, `MemoryLayer`, `LlmModel`, `AuditOperation` |
| ADR-007 (decay/retention/encryption) | PR #14 | Decisiones cerradas sobre operaciones de memoria |
| Tests Pydantic puros | PR #19 | ~300 líneas, sin DB |
| Doctor check #7 ampliado | PR #19 | Detecta tablas sagradas + audit |
| Doctor check #10 | PR #16 | Detecta rama derivada del tip de un PR ajeno |
| Branch protection: linear history + rebase merge | PR #17 | `required_linear_history: true`, `allow_force_pushes: false` |

### En espera

- **Issue #20** (deuda D1) — commits imperativo vs noun-phrase, esperando decisión.
- **Proyecto Supabase** — pendiente de creación con los 3 toggles OFF.

### Pendiente (cubierto por este roadmap)

- PR B (migración Alembic)
- ADR-008 (bge-m3)
- PR C (crypto + wrappers)
- `core/security.py` (auth)
- Router + cliente vLLM + prompts + tools
- Workers Celery (consolidación, decay, retention)
- Endpoints FastAPI

---

## 2. Decisiones inmediatas (bloqueantes)

### 2.1 Issue #20 — deuda D1

Esperando elección entre:

- **Opción A** *(recomendada)* — ajustar regla #6 de `AGENTS.md` para permitir noun-phrase cuando el commit describe un artefacto, no una acción.
- **Opción B** — reescribir el history del PR #15 (8 commits) a imperativo. Costoso, no aporta valor.
- **Opción C** — aceptar discrepancia + nota en `COMMITS.md`. Menos limpio que A.

**Acción**: decidir y aplicar en un PR chico de un solo archivo.

### 2.2 Proyecto Supabase

Crear con:

- Region: `sa-east-1` (São Paulo) — latencia LATAM.
- Toggles: **3 OFF** (Data API, auto-expose, auto-RLS) — alineado con regla #5.
- Anotar `DATABASE_URL` en gestor de secretos del equipo (no en repo).

**Acción**: crear proyecto, anotar credentials, agregar `MEMORY_ENCRYPTION_MASTER_KEY` generada con `openssl rand -base64 32`.

### 2.3 Fix de 1 línea

`apps/backend/app/models/memory.py:4` dice *"2 aprobaciones humanas"*. Desde PR #17 es **1 aprobación**.

**Acción**: PR chico, un archivo, un commit.

---

## 3. Plan T1 — memoria contextual

### 3.1 PR B — migración Alembic inicial

**Bloqueado por**: proyecto Supabase listo (2.2).

**Scope**:

- Activar extensión `vector` en Postgres.
- Crear los 4 enums nativos (`mode`, `memory_layer`, `llm_model`, `audit_operation`) con `create_type` ownership documentada en docstrings.
- Crear las 6 tablas en orden FK correcto: `users` → `sessions` → `semantic_memory` / `episodic_memory` / `procedural_memory` → `audit_log`.
- Índices HNSW sobre `content_embedding` y `summary_embedding` con `vector_cosine_ops`.
- Constraints: `retention_days_range`, `retention_days_sensitive_cap`, `confidence_range`, `importance_range`, `record_hash` regex.
- Tests up/downgrade en `apps/backend/tests/migrations/`.

**Tabla sagrada** → requiere **1 aprobación humana explícita** (regla #3).

**Estimación**: 1 sesión.

### 3.2 ADR-008 — bge-m3 como modelo de embedding

**No bloqueado**. Puede arrancar ya.

**Scope** (chico, sin código):

- Documentar **bge-m3** (multilingüe, 1024-dim) como el modelo único de embedding para semantic + episodic.
- Justificar vs alternativas (text-embedding-3, sentence-transformers genéricos) — coherencia con informe técnico §4 tabla resumen.
- Definir cómo se hostea (vLLM aparte, transformers en proceso, servicio dedicado).
- Definir API contract: `embed(text: str) -> list[float]` con shape `(1024,)`.

**Estimación**: 1-2 horas. Desbloquea PR C.

### 3.3 PR C — crypto helper + wrappers de memoria

**Bloqueado por**: PR B + ADR-008.

**Scope**:

- `apps/backend/app/core/crypto.py`:
  - `derive_user_key(user_id: UUID) -> bytes` con HKDF-SHA256.
  - `encrypt_for_user(user_id: UUID, plaintext: str) -> bytes` (AES-256-GCM, layout `nonce||ct||tag`).
  - `decrypt_for_user(user_id: UUID, ciphertext: bytes) -> str` con manejo de `InvalidTag`.
  - Master key vía `MEMORY_ENCRYPTION_MASTER_KEY` env.
- `apps/backend/app/memory/semantic.py` — `add`, `search`, `update`, `delete`. Cifra `content` antes de persistir, descifra al leer.
- `apps/backend/app/memory/episodic.py` — `add`, `search_by_user`, `delete_expired`. Setea `is_sensitive=true` cuando el modo es Bienestar.
- `apps/backend/app/memory/procedural.py` — `upsert`, `get_active`, `mark_stale`. Resetea `confidence=1.0` en reforzar.
- Tests integración con DB real en `apps/backend/tests/memory/`:
  - Roundtrip cifrado, manejo de wrong-key, edge cases (empty, unicode largo, payload > 1MB).
  - Búsqueda semántica con bge-m3 mockeado.
  - Cap de `retention_days` cuando `is_sensitive=true`.
  - Decay manual: `confidence < 0.3 → stale=true`.

**Tabla sagrada** → requiere **1 aprobación humana explícita** (regla #3).

**Estimación**: 2-3 sesiones.

---

## 4. Capa LLM — router + cliente vLLM + prompts

### 4.1 `core/security.py` — auth mínimo

**Bloquea router** (necesita `user_id` autenticado).

**Scope**:

- Endpoint `/auth/login` con email + password contra `users` table.
- JWT con `user_id` + `exp`.
- Dependency `get_current_user(token) -> User` para FastAPI.
- Tests unitarios.

**Estimación**: 1 sesión.

### 4.2 Cliente vLLM

**Path**: `apps/backend/app/llm/clients/vllm.py`.

**Scope**:

- Wrapper async sobre `/v1/chat/completions` (OpenAI-compatible).
- Switch por modelo via campo `model` (Gemma vs Qwen).
- Parser `qwen3_coder` para tool calls.
- Streaming desde primer token.
- Health check `/v1/models`.
- Config en `ynara.config.json[llm]`: `endpoint`, `quantization`, `max_model_len`, `kv_cache_dtype`.

**Estimación**: 1-2 sesiones.

### 4.3 Router

**Path**: `apps/backend/app/llm/router.py` (esqueleto actual a completar).

**Scope**:

1. Clasificar intención (reglas + clasificador rápido) → modo + modelo.
2. Recuperar memoria via wrappers de T1: top-3 semantic + top-2 episodic + procedural activo.
3. Armar prompt con contexto inyectado + system prompt del modo.
4. Llamar vLLM con el modelo elegido.
5. Si es Qwen, parsear tool calls y ejecutar (memory.*, calendar.*, reminder.*).
6. Encolar consolidación Celery con el par (user_msg, model_response).
7. Devolver respuesta al cliente.

**Estimación**: 2 sesiones.

### 4.4 Prompts por modo

**Path**: `apps/backend/app/llm/prompts/`.

**Scope**:

- Un archivo por modo: `productividad.md`, `estudio.md`, `bienestar.md`, `vida.md`, `memoria.md`.
- Alineados con `IDENTITY.md` (4 pilares) + `TONE-OF-VOICE.md` (rioplatense, calidez, sin moralizar).
- Loader en `app/llm/prompts/loader.py`.

**Estimación**: 1 sesión.

### 4.5 Tools

**Path**: `apps/backend/app/llm/tools/`.

**Scope**:

- `memory.add`, `memory.search`, `memory.update`, `memory.delete` — depende de T1.
- `calendar.create_event`, `calendar.list_events` — puede ir paralelo.
- `reminder.set`, `reminder.list` — puede ir paralelo.
- Schema JSON de cada tool en formato OpenAI tool calling.

**Estimación**: 1-2 sesiones por bloque (memory / calendar / reminder).

### 4.6 Fallback OnPrem-only

**No** caer a OpenAI/Anthropic/Google (regla #4).

**Scope**:

- Si vLLM principal falla → reintentar con backoff (3 veces).
- Si sigue fallando → instancia secundaria on-prem (Qwen 3.5-9B solo, sin Gemma).
- Si secundario también falla → respuesta degradada al usuario: *"Estoy con un problema técnico, probá en un ratito"*.
- Circuit breaker contra `/v1/models`.

**Estimación**: 1 sesión.

---

## 5. Workers Celery

**Bloqueado por**: PR B + Redis configurado.

### 5.1 Consolidación post-turn

- Trigger: post-respuesta del modelo (cualquiera).
- Input: `(user_msg, model_response, session_id)`.
- Lógica: pedirle a Qwen extracción de hechos en formato Mem0 (ADD/UPDATE/DELETE/NOOP).
- Output: escribir en `semantic_memory` + actualizar `procedural_memory`.

### 5.2 Decay procedural

- Trigger: diario (Celery Beat).
- Lógica: `confidence *= 0.9` cuando `last_reinforced_at` > 14 días.
- Marcar `stale=true` cuando `confidence < 0.3`.
- Hard delete cuando `confidence < 0.1` **y** `last_reinforced_at` > 90 días.

### 5.3 Retention episodic

- Trigger: diario (Celery Beat).
- Lógica: borrar entradas donde `created_at + retention_days < now()`.
- Separar `is_sensitive=true` con audit log diferenciado.

**Estimación**: 1-2 sesiones por worker.

---

## 6. Endpoints FastAPI

**Bloqueado por**: router + wrappers + auth.

| Endpoint | Método | Scope |
|---|---|---|
| `/v1/chat` | POST | Entrada del usuario, dispatch al router |
| `/v1/memory/semantic` | GET / POST / PATCH / DELETE | CRUD para debug + export |
| `/v1/memory/episodic` | GET / DELETE | Lectura + borrado manual |
| `/v1/memory/procedural` | GET / DELETE | Lectura + reset |
| `/v1/memory/settings` | PATCH | Update `retention_sensitive_days` |
| `/v1/memory/export` | GET | JSON con sensible separado |
| `/auth/login` | POST | Auth básico |

**Estimación**: 2-3 sesiones.

---

## 7. Camino crítico

```
[2.2 Supabase project]
        |
        v
[3.1 PR B — Alembic]      [3.2 ADR-008 — bge-m3]    [4.1 core/security.py]
        \                         /                          |
         \                       /                           |
          v                     v                            |
       [3.3 PR C — crypto + wrappers]                        |
                        \                                    /
                         \                                  /
                          v                                v
                  [4.3 Router]  <----  [4.2 Cliente vLLM]
                          |
                          v
                  [4.4 Prompts por modo]
                          |
                          v
                  [4.5 Tools (memory primero)]
                          |
                          v
                  [5.1 Worker consolidación]
                          |
                          v
                  [6 Endpoint /v1/chat]
                          |
                          v
                  AGENTE FUNCIONANDO E2E
```

**Paralelizables sin bloqueo**:

- ADR-008 puede arrancar **ya** (sin Supabase).
- Fix de 1 línea (2.3) puede ir en cualquier momento.
- Issue #20 (2.1) puede resolverse en cualquier momento.
- Tools de calendar/reminder pueden ir paralelo a memory tools.
- Workers de decay/retention pueden ir paralelo al router.

---

## 8. Riesgos y bloqueantes

| Riesgo | Mitigación |
|---|---|
| Supabase tarda en estar listo | ADR-008 + fix de 1 línea + issue #20 en paralelo |
| bge-m3 muy lento para embeddings en cada turno | Cachear embeddings de queries frecuentes en Redis (post-MVP) |
| Cifrado rompe búsqueda semántica | No aplica — embeddings van plain, solo `content`/`summary` cifrados (ADR-007) |
| vLLM no entra Gemma + Qwen en 16GB | Cuantización Q4 forzada en ADR-002; si no entra, swap modelo activo (un solo modelo a la vez en RAM) |
| Auth bloquea router | Auth mínimo primero (JWT básico) — refinamiento por separado |
| Master key se pierde | Backup en gestor de secretos del equipo (no en repo). V2 evalúa key escrow |
| Tablas sagradas requieren aprobación cada PR | Bloque PR B + PR C asume 1 reviewer disponible (regla #3 ya en 1 aprobación) |

---

## 9. Definition of Done

El roadmap se considera **completo** cuando:

- [ ] Un usuario puede mandar un mensaje a `/v1/chat`, ser autenticado, recibir respuesta del modelo correcto según modo, con memoria inyectada (top-3 semantic + top-2 episodic + procedural activo).
- [ ] La conversación se guarda cifrada en Postgres.
- [ ] Qwen extrae hechos en background y escribe a `semantic_memory`.
- [ ] Decay diario corre y marca `stale` correctamente.
- [ ] Retention diario borra entradas vencidas.
- [ ] Fallback on-prem funciona ante caída de vLLM principal.
- [ ] Tests pasan: unit (Pydantic, crypto, router) + integración (DB real, wrappers, workers) + e2e (`/v1/chat` con DB + vLLM mockeado).
- [ ] Doctor pasa 10/10 en cada PR del camino crítico.

---

## 10. Referencias

- [`AGENTS.md`](../../AGENTS.md) — 10 reglas no negociables.
- [`docs/architecture/informe-tecnico.pdf`](../architecture/informe-tecnico.pdf) §1.5 (flow turn-por-turn) y §2.4 (capa LLM).
- [`docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md`](../architecture/adrs/ADR-002-gemma-qwen-dual-stack.md) — dual-stack.
- [`docs/architecture/adrs/ADR-003-mem0-vs-letta.md`](../architecture/adrs/ADR-003-mem0-vs-letta.md) — Mem0 OSS v2.
- [`docs/architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md`](../architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md) — Postgres + pgvector.
- [`docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md`](../architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md) — Supabase MVP → self-hosted V2.
- [`docs/architecture/adrs/ADR-007-memory-decay-retention-encryption.md`](../architecture/adrs/ADR-007-memory-decay-retention-encryption.md) — decay, retention, cifrado.
- [`docs/product/MEMORY.md`](../product/MEMORY.md) — modelo de memoria.
- [`apps/backend/docs/MODELS.md`](../../apps/backend/docs/MODELS.md) — catálogo de tablas.
- Trello cards: *Arquitectura de memoria contextual*, *Integración con backend LLM*.

---

> Este documento es **operativo**, no arquitectónico. Cambios de decisión van por ADR. Cambios de plan se editan acá y se marcan con fecha + autor en el header.
