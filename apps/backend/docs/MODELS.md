# MODELS.md — Catálogo de modelos SQLAlchemy

> Por cada modelo: nombre, tabla, descripción, columnas, relaciones,
> índices, notas. Tablas sagradas marcadas con 🔴 (regla #3 de
> `AGENTS.md`).
>
> **Fuente de verdad de columnas y constraints**: `apps/backend/app/models/`.
> Esta doc explica el porqué; el código es el qué.

## Convenciones

- Tabla en snake_case plural (`semantic_memory` es singular por
  convención de la capa de memoria — no plural).
- PK siempre `id UUID DEFAULT gen_random_uuid()` (vía `UUIDPKMixin`).
- Timestamps `created_at`, `updated_at` con `TIMESTAMPTZ` y default
  `now()` (vía `TimestampMixin`). `audit_log` no usa `TimestampMixin`
  porque es inmutable post-creación (solo `created_at`).
- Soft delete: **no usar**. Borrado físico (regla del repo).
- FK con `ON DELETE CASCADE` cuando el dueño es claro (memoria pertenece
  al usuario), `ON DELETE SET NULL` para referencias opcionales
  (ej: `source_session_id`), `RESTRICT` cuando hay riesgo de huérfanos.
- Naming convention de constraints definida en `Base.metadata` —
  `ix_*` / `uq_*` / `ck_*` / `fk_*` / `pk_*`.
- Enums usan tipos PostgreSQL nativos (`native_enum=True`). El nombre
  del tipo se declara una sola vez por enum cross-tabla
  (ej: `mode_enum`); las tablas que lo reusan setean
  `create_type=False`.

## Enums compartidos

Viven en `apps/backend/app/enums.py`. Importan tanto modelos como
schemas Pydantic.

| Enum | Tipo PG | Valores | Uso |
|---|---|---|---|
| `Mode` | `mode_enum` | productividad, estudio, bienestar, vida, memoria | `sessions.mode`, `audit_log.origin_mode` |
| `MemoryLayer` | `memory_layer_enum` | semantic, episodic, procedural | `audit_log.target_layer` |
| `LlmModel` | `llm_model_enum` | gemma, qwen | `audit_log.origin_model` |
| `AuditOperation` | `audit_operation_enum` | read, write, update, delete | `audit_log.operation` |
| `TurnRole` | `turn_role_enum` | user, model | `conversation_turns.role` (dueño, único consumidor) |

## Tablas sagradas 🔴

Cualquier cambio aquí requiere tests + **1 aprobación humana explícita**
(review formal en el PR, además del operador autor — regla #3 de
[`AGENTS.md`](../../../AGENTS.md)). El set sagrado son las 3 capas de la **memoria
cifrada** del moat (schema en
[`ADR-007`](../../../docs/architecture/adrs/ADR-007-memory-decay-retention-encryption.md))
más el **`audit_log` inmutable** — el mismo set que AGENTS §0 /
`app/models/{memory,audit}.py`. (`users` / `sessions` son operativas: review normal,
sin el gate extra.)

### 🔴 semantic_memory

Hechos persistentes sobre el usuario (preferencias estables, datos
biográficos, contexto duradero). **Solo Qwen escribe** (regla del
producto). Lectura por ambos modelos vía `search()` por similitud.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | indexed btree |
| `content` | BYTEA NOT NULL | Cifrado AES-256-GCM (key derivada por usuario, ver ADR-007 D3) |
| `content_embedding` | VECTOR(1024) NOT NULL | bge-m3, sin cifrar (necesario para pgvector) |
| `importance` | INTEGER | 0-100, nullable. Constraint: `importance IS NULL OR BETWEEN 0 AND 100` |
| `source_session_id` | UUID FK → sessions.id, ON DELETE SET NULL | Trazabilidad opcional |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Índices**:
- `ix_semantic_memory_user_id` (btree, por `user_id`) — queries por usuario. Naming convention: `ix_%(column_0_label)s` de `Base.metadata` → `ix_<tabla>_<columna>`.
- `ix_semantic_memory_content_embedding_hnsw` (HNSW, `vector_cosine_ops`) — búsqueda por similitud.

### 🔴 episodic_memory

Resúmenes de sesiones pasadas. Se generan **vía Celery al cerrar la
sesión**: Qwen toma los mensajes de la sesión + embedding del resumen.
1-a-1 con `sessions` (constraint UNIQUE sobre `session_id`).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | indexed |
| `session_id` | UUID FK → sessions.id, ON DELETE CASCADE | UNIQUE |
| `summary` | BYTEA NOT NULL | Cifrado AES-256-GCM |
| `summary_embedding` | VECTOR(1024) NOT NULL | bge-m3 |
| `is_sensitive` | BOOLEAN NOT NULL DEFAULT false | `true` para modo Bienestar |
| `retention_days` | INTEGER NOT NULL DEFAULT 365 | 180 cuando `is_sensitive=true` (configurable por usuario, ver ADR-007 D2) |
| `occurred_at` | TIMESTAMPTZ NOT NULL | Cuando ocurrió la sesión, no cuando se persistió |
| `topics` | JSONB NOT NULL DEFAULT '{}' | Metadata: tópicos, duración, modo |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Constraints**:
- `retention_days_range`: `retention_days BETWEEN 1 AND 3650`.
- `retention_days_sensitive_cap`: `(is_sensitive = false) OR (retention_days BETWEEN 1 AND 365)` — cap a 12 meses cuando `is_sensitive=true` (ADR-007 D2).

**Índices**:
- `ix_episodic_memory_user_id` (btree, por `user_id`).
- `ix_episodic_memory_summary_embedding_hnsw` (HNSW sobre embedding).

### 🔴 procedural_memory

Preferencias y patrones del usuario. JSONB plain — son preferencias no
sensibles por diseño (ej: `{"voseo": true, "pomodoro_minutes": 25}`).
Decay exponencial sobre `confidence`; worker Celery diario aplica
`confidence *= 0.9` cada `decay_interval_days` desde
`last_reinforced_at`.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | indexed |
| `key` | VARCHAR(120) NOT NULL | UNIQUE con `user_id` |
| `value` | JSONB NOT NULL | Plain, sin cifrar |
| `confidence` | DOUBLE PRECISION NOT NULL DEFAULT 1.0 | 0-1, decay aplica desde `last_reinforced_at` (`sa.Float()` genera `double precision` en Postgres) |
| `last_reinforced_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | Resetea con cada `upsert` del mismo key |
| `stale` | BOOLEAN NOT NULL DEFAULT false | `true` cuando `confidence < 0.3`. El router no inyecta automáticamente entradas stale; el agente decide si preguntar al usuario |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Constraint**:
- `UNIQUE (user_id, key)` — un patrón por usuario.
- `confidence BETWEEN 0 AND 1`.

**Borrado físico**: cuando `confidence < 0.1` y `last_reinforced_at > 90 días` (worker periódico). Ver ADR-007 D1.

### 🔴 audit_log

Sagrada por **inmutabilidad / integridad de auditoría** (regla #3), no por cifrado:
no es una tabla del moat ADR-007 (guarda metadata + hash, sin contenido en claro).

Registro inmutable de operaciones sobre memoria. **Se escribe** (issue
#158): la consolidación (`app/llm/memory_engine.apply_ops` vía
`app/memory/audit.AuditStore`) inserta **una fila por op de memoria
consolidada** que cambia el estado (ADD/UPDATE/DELETE sobre semantic o
procedural; NOOP y ops skippeadas no auditan). La fila guarda solo
metadata + un `record_hash` SHA-256 del contenido/identificador
afectado, **nunca el contenido en claro** (regla #4): el hash es
unidireccional, así que cero PII llega a la tabla de auditoría. El
**formato canónico** del `record_hash` (incluido el payload procedural
`(key, value)` con `sort_keys`) vive en `app/memory/hashing.py`
(`compute_record_hash` + `procedural_hash_payload`, funciones puras de
solo stdlib): es la **sede única**, importada tanto por la consolidación
(`apply_ops`) como por las mutaciones por endpoint.
Además, las **mutaciones por endpoint** (`PATCH`/`DELETE`/`wipe` en
`/v1/memory`, issue #161) escriben una fila por operación efectiva, en la
**misma** transacción del request. Las filas de consolidación van
`sensitive=false` (`apply_ops` no toca episódica); en las mutaciones por
endpoint, un `DELETE` sobre episódica va `sensitive=true` (conservador, sin
descifrar el `summary`). La escritura es siempre atómica con la op que audita
(mismo `commit`). Dos vías de eliminación:

1. **Temporal (worker)**: 24 meses por worker periódico de Celery —
   retention normal para usuarios activos (`docs/product/MEMORY.md`).
2. **Cascada al borrar usuario** (`ON DELETE CASCADE` en
   `user_id`): cuando un usuario ejecuta `DELETE /v1/memory` o
   elimina su cuenta, su audit log también se borra. Decisión de
   producto: **privacidad > compliance forense**. Cumple "derecho
   al olvido" alineado con regla #4 (datos del usuario nunca quedan
   colgados). Si en V2 hace falta audit anonimizado por compliance,
   evaluar `ON DELETE SET NULL` + `user_id NULL`.

No usa `TimestampMixin` — una vez creada, una entrada no se modifica. La
inmutabilidad se enforcea **a nivel DB**: el trigger `trg_audit_log_block_update`
(BEFORE UPDATE, función `ynara_audit_log_block_update`, migración `20260602_1015`)
aborta cualquier UPDATE con una EXCEPTION (SQLSTATE 23514), aunque el SQL venga por
fuera del ORM. Solo se bloquea UPDATE: el DELETE queda permitido a propósito (cascade
GDPR + worker de retention).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | indexed |
| `operation` | `audit_operation_enum` NOT NULL | read / write / update / delete |
| `target_layer` | `memory_layer_enum` NOT NULL | Qué capa de memoria se tocó |
| `target_id` | UUID | Nullable (para operaciones sobre toda la capa, ej `DELETE /v1/memory`) |
| `origin_model` | `llm_model_enum` | gemma / qwen, nullable (operación del usuario directo) |
| `origin_mode` | `mode_enum` | Modo activo cuando ocurrió, nullable |
| `origin_tool` | VARCHAR(80) | Nombre de la tool si la operación vino de tool-call, nullable |
| `record_hash` | VARCHAR(64) NOT NULL | SHA-256 hex del contenido afectado (texto plano antes de cifrar). CHECK constraint `record_hash ~ '^[0-9a-f]{64}$'` enforce el formato a nivel DB |
| `sensitive` | BOOLEAN NOT NULL DEFAULT false | `true` para ops sobre episódica con `is_sensitive=true` |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | Indexed (queries por rango temporal) |

## Tablas operativas

### users

Usuario de Ynara. Auth JWT implementada (`app/core/security.py`:
`create_access_token`, `verify_access_token`, `create_refresh_token`,
`verify_token`, `hash_password`, `verify_password`). Endpoints activos:
`/v1/auth/register`, `/v1/auth/token`, `/v1/auth/me`, `/v1/auth/refresh`,
`/v1/auth/logout`. Refresh/logout implementados (#63): POST
`/v1/auth/refresh` (rotación single-use con reuse-detection a nivel
familia/`sid`, retry-safe — #142) + POST `/v1/auth/logout` (revoca la
familia entera vía `sid` + blocklist por `jti` — #142).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `email` | VARCHAR(254) UNIQUE | Nullable hasta que auth real esté implementada (ephemeral users no tienen email) |
| `password_hash` | VARCHAR(255) | Nullable hasta auth real |
| `display_name` | VARCHAR(40) | Nullable hasta que onboarding lo capture |
| `is_ephemeral` | BOOLEAN NOT NULL DEFAULT false | Modo "probar sin cuenta" |
| `onboarding_completed` | BOOLEAN NOT NULL DEFAULT false | Setea el frontend al final del onboarding |
| `is_admin` | BOOLEAN NOT NULL DEFAULT false | Gate del panel admin interno (`/v1/admin/*`). `server_default=false` para no romper filas existentes. Bootstrap inicial (antes de poblar la columna) vía `ADMIN_BOOTSTRAP_IDS` en `get_current_admin`; esta flag es la fuente de verdad persistente. Agregada en la migración `20260619_1200_add_is_admin_and_admin_audit` |
| `retention_sensitive_days` | INTEGER NOT NULL DEFAULT 180 | TTL configurable por usuario para episódica con `is_sensitive=true`. Rango 30-365 (constraint) |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Constraint**: `retention_sensitive_days BETWEEN 30 AND 365`.

### sessions

Una sesión es una conversación contigua de un usuario en un modo fijo.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | indexed |
| `mode` | `mode_enum` NOT NULL | Inmutable post-creación (un modo por sesión) |
| `started_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `ended_at` | TIMESTAMPTZ | NULL hasta que se cierre |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Relación con `episodic_memory`**: 1-a-1 (UNIQUE en `episodic_memory.session_id`).
Al cerrar la sesión, un worker Celery genera la entrada episódica.

### conversation_turns

**OPERATIVA**, no sagrada (sin 🔴): buffer **transitorio** de los turnos crudos
(user/modelo) de una sesión. Es la **fuente** que el worker episódico
(`consolidate_session`, issue #209) lee al cerrar la sesión para resumir y
persistir en `episodic_memory` (sagrada), y que luego **purga**
(`ConversationTurnStore.purge_session`): retención **efímera**, no almacenamiento
de largo plazo. El resumen consolidado vive en `episodic_memory`; los turnos
crudos se borran tras consolidar.

Aun siendo operativa, el `content` viaja **cifrado AES-256-GCM per-user** (regla
#4: cero PII en claro en la DB) — exactamente como `semantic_memory.content` /
`episodic_memory.summary`. El cifrado lo hace el store
(`app/memory/conversation_turns.py`), no el modelo. Se escribe en `/v1/chat` y
`/v1/chat/stream` (vía `ChatService.run_turn`), en la **misma** transacción que la
`ChatSession` (turnos + sesión atómicos); no se persiste si el turno degradó.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `user_id` | UUID FK → users.id, ON DELETE CASCADE | (cubierto por el índice compuesto, ver abajo) |
| `session_id` | UUID FK → sessions.id, ON DELETE CASCADE | (cubierto por el UNIQUE y el índice compuesto) |
| `role` | `turn_role_enum` NOT NULL | `user` o `model` |
| `content` | BYTEA NOT NULL | Cifrado AES-256-GCM (key derivada por usuario, ADR-007 D3) |
| `seq` | INTEGER NOT NULL | Orden monotónico por sesión (0 = primer turno user, 1 = primera respuesta model, ...) |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Constraint**:
- `UNIQUE (session_id, seq)` — un turno por posición en la sesión (idempotencia de orden).

**Índices**:
- `ix_conversation_turns_user_id_session_id_seq` (btree compuesto, `(user_id, session_id, seq)`) —
  **único** índice de la tabla, matchea el patrón real de queries del store: todas filtran por
  `user_id` Y `session_id` (`next_seq`, `list_for_session`, `purge_session`) y ordenan por `seq`.
  Su prefijo `(user_id)` cubre el cascade-delete por usuario; el índice implícito del
  `UNIQUE (session_id, seq)` cubre el acceso por sesión. Reemplaza los 3 índices parciales
  originales (`ix_..._user_id`, `ix_..._session_id`, `ix_..._session_id_seq`), eliminados en la
  migración `20260615_0200_drop_redundant_conversation_turns_indexes`.

### admin_audit

**OPERATIVA**, no sagrada (sin 🔴): registra las acciones que un **operador** (admin)
ejecuta sobre el panel interno (`/v1/admin/*`). **No es `audit_log`** (sagrada,
inmutable, audita operaciones sobre la **memoria cifrada** del usuario): `admin_audit`
audita actividad del operador, no contenido del moat. Modelo en
`app/models/admin_audit.py` (`UUIDPKMixin` + `TimestampMixin`). Agregada en la migración
`20260619_1200_add_is_admin_and_admin_audit`.

Privacidad (regla #4): `admin_id` es un UUID opaco (no PII); `meta` (JSONB) lleva
contexto liviano de la acción, **nunca** contenido de memoria descifrado ni PII del
usuario observado. La columna se llama `meta` y no `metadata` porque `metadata` choca
con el atributo reservado de la declarative base de SQLAlchemy.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `admin_id` | UUID FK → users.id, ON DELETE CASCADE | indexed; al borrar el admin se borra su rastro |
| `action` | VARCHAR(80) NOT NULL | Nombre de la acción del panel |
| `target_type` | VARCHAR(40) | Tipo del objeto afectado, nullable |
| `target_id` | UUID | Id opaco del objeto afectado, nullable |
| `meta` | JSONB NOT NULL DEFAULT '{}' | Contexto liviano (sin PII / sin contenido descifrado) |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Índice**:
- `ix_admin_audit_admin_id` (btree, por `admin_id`) — queries por admin + cascade-delete.

## Migración inicial

Mergeada. La migración inicial vive en `apps/backend/alembic/versions/`
e incluye:

1. Extensión `pgvector` activa.
2. Los 4 enums (`mode_enum`, `memory_layer_enum`, `llm_model_enum`,
   `audit_operation_enum`). El enum `turn_role_enum` NO está acá: se agrega en la
   migración `20260614_1700_conversation_turns_table` (ver abajo).
3. Las 6 tablas en orden de FKs: `users` → `sessions` → `semantic_memory`,
   `episodic_memory`, `procedural_memory`, `audit_log`.
4. Índices HNSW sobre embeddings.
5. Tests up/downgrade ida y vuelta.

La migración `20260614_1700_conversation_turns_table` agrega el enum
`turn_role_enum` + la tabla `conversation_turns` (FKs a `users` y `sessions`),
llevando el total a **7 tablas** (#209). La migración siguiente,
`20260615_0200_drop_redundant_conversation_turns_indexes` (**HEAD**), reemplaza
los 3 índices parciales de `conversation_turns` por el único índice compuesto
`(user_id, session_id, seq)`.

Ver [`docs/MIGRATIONS.md`](./MIGRATIONS.md) para la cadena completa y la política.

## Wrappers de memoria

Implementados en `apps/backend/app/memory/` (M7, mergeado). Las
operaciones `search` / `add` / `update` / `delete` están activas.
`memory.add` NO escribe de forma síncrona (la consolidación es async;
ver `app/llm/tools/memory.py`). El engine es **in-house** (ADR-010,
que supersede ADR-003/Mem0): no se usa Mem0. Cifrado AES-256-GCM
per-user via `app/core/crypto.py` (`encrypt_for_user` /
`decrypt_for_user`, ADR-007 D3, mergeado).

**Módulos neutrales** (siblings de comportamiento, no tocan columnas de las tablas
sagradas):

- `app/memory/hashing.py` — sede única del formato de los digests de `audit_log`
  (`compute_record_hash` + `procedural_hash_payload`). Antes vivían como helpers
  privados de `app/llm/memory_engine.py` (boundary leak); ahora son la API pública de
  este módulo, importada por el motor de extracción y por los endpoints de memoria.
- `app/memory/embedding.py` — helper compartido `embed_one(embedder, text)`: embeddea un
  texto plaintext y devuelve el vector de 1024 floats. Antes duplicado como `_embed_one`
  en `semantic.py` / `episodic.py`.
- `app/memory/config.py` — loader de los thresholds de `ynara.config.json[memory]`:
  `DecayConfig` / `load_decay_config` (decay procedural, ADR-007 D1) y `RetentionConfig`
  / `load_retention_config` (retention episódica, ADR-007 D2). Pydantic frozen + strict +
  `extra='forbid'`, fail-fast (`MemoryConfigError`) pero **default-safe** (config viejo sin
  esas keys → defaults de ADR-007, no rompe).
