# MODELS.md — Catálogo de modelos SQLAlchemy

> Por cada modelo: nombre, tabla, descripción, columnas, relaciones,
> índices, notas. Tablas sagradas marcadas con 🔴 (regla #3 de
> `AGENTS.md`).
>
> **Fuente de verdad de columnas y constraints**: `apps/backend/app/models/`.
> Esta doc explica el porqué; el código es el qué.

## Convenciones

- Tabla en snake_case plural (`semantic_memory` es singular por
  convención de Mem0 — no plural).
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

## Tablas sagradas 🔴

Cualquier cambio aquí requiere tests + **1 aprobación humana explícita**
(review formal en el PR, además del operador autor — regla #3 de
[`AGENTS.md`](../../../AGENTS.md)). Schema definido en
[`ADR-007`](../../../docs/architecture/adrs/ADR-007-memory-decay-retention-encryption.md).

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
| `importance` | SMALLINT | 0-100, nullable. Constraint: `importance IS NULL OR BETWEEN 0 AND 100` |
| `source_session_id` | UUID FK → sessions.id, ON DELETE SET NULL | Trazabilidad opcional |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Índices**:
- `ix_users_id` (btree, por `user_id`) — queries por usuario.
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

**Constraint**: `retention_days BETWEEN 1 AND 3650`.

**Índices**:
- `ix_users_id` (por `user_id`).
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
| `confidence` | REAL NOT NULL DEFAULT 1.0 | 0-1, decay aplica desde `last_reinforced_at` |
| `last_reinforced_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | Resetea con cada `upsert` del mismo key |
| `stale` | BOOLEAN NOT NULL DEFAULT false | `true` cuando `confidence < 0.3`. El router no inyecta automáticamente entradas stale; el agente decide si preguntar al usuario |
| `created_at`, `updated_at` | TIMESTAMPTZ | TimestampMixin |

**Constraint**:
- `UNIQUE (user_id, key)` — un patrón por usuario.
- `confidence BETWEEN 0 AND 1`.

**Borrado físico**: cuando `confidence < 0.1` y `last_reinforced_at > 90 días` (worker periódico). Ver ADR-007 D1.

## Tablas operativas

### users

Usuario de Ynara. Auth completa todavía no implementada
(`app/core/security.py` en `NotImplementedError`).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `email` | VARCHAR(254) UNIQUE | Nullable hasta que auth real esté implementada (ephemeral users no tienen email) |
| `password_hash` | VARCHAR(255) | Nullable hasta auth real |
| `display_name` | VARCHAR(40) | Nullable hasta que onboarding lo capture |
| `is_ephemeral` | BOOLEAN NOT NULL DEFAULT false | Modo "probar sin cuenta" |
| `onboarding_completed` | BOOLEAN NOT NULL DEFAULT false | Setea el frontend al final del onboarding |
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

### audit_log

Registro inmutable de operaciones sobre memoria. Retention: 24 meses
(`docs/product/MEMORY.md`). No usa `TimestampMixin` — una vez creada,
una entrada no se modifica.

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

## Migración inicial

Pendiente para el PR siguiente del plan T1 (PR B). Va en
`apps/backend/alembic/versions/`. Requerirá:

1. Extensión `pgvector` activa.
2. Creación de los 4 enums (`mode_enum`, `memory_layer_enum`,
   `llm_model_enum`, `audit_operation_enum`).
3. Las 6 tablas en orden de FKs: `users` → `sessions` → `semantic_memory`,
   `episodic_memory`, `procedural_memory`, `audit_log`.
4. Índices HNSW sobre embeddings (creación con `CONCURRENTLY` en prod).
5. Tests up/downgrade ida y vuelta.

Regla #3 + tablas sagradas + Alembic = **1 aprobación humana
explícita obligatoria** (review formal en el PR, además del operador
autor) para PR B.

## Wrappers de memoria

Implementación de `add` / `search` / `update` / `delete` en
`apps/backend/app/memory/` es PR C del plan T1. Hoy están en
`NotImplementedError`. Dependen de:

- Helper `app/core/crypto.py` con `encrypt_for_user` / `decrypt_for_user`
  (parte de PR B o C, ver ADR-007 D3).
- `Mem0 OSS v2` para extracción + dedup (ADR-003).
- Cliente Postgres async (`asyncpg`) y `pgvector.sqlalchemy.Vector`.
