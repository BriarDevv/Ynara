# MODELS.md — Catálogo de modelos SQLAlchemy

> Por cada modelo: nombre, tabla, descripción, columnas, relaciones,
> índices, notas. Tablas sagradas marcadas con 🔴.

## Convenciones

- Tabla en snake_case plural (`semantic_memory`, `users`).
- PK siempre `id UUID DEFAULT gen_random_uuid()`.
- Timestamps `created_at`, `updated_at` con `TIMESTAMPTZ`.
- Soft delete: **no usar**. Borrado físico.
- FK con `ON DELETE CASCADE` cuando el dueño es claro (memoria
  pertenece al usuario), `RESTRICT` cuando hay riesgo.

## Tablas sagradas 🔴

Cualquier cambio aquí requiere tests + 2 aprobaciones humanas
(regla #3 de AGENTS.md).

### 🔴 semantic_memory

- TODO: completar columnas finales.
- `id` UUID PK
- `user_id` UUID FK → users.id
- `content` TEXT
- `embedding` VECTOR(1024)  -- bge-m3
- `importance` SMALLINT (0-100)
- `source` TEXT (modo de origen)
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ
- Índices: HNSW sobre `embedding`, btree sobre `user_id`.

### 🔴 episodic_memory

- TODO: completar.
- `id` UUID PK
- `user_id` UUID FK
- `session_id` UUID FK → sessions.id
- `summary` TEXT
- `embedding` VECTOR(1024)
- `metadata` JSONB (modo, duración, tópicos)
- `occurred_at` TIMESTAMPTZ
- `created_at` TIMESTAMPTZ

### 🔴 procedural_memory

- TODO: completar.
- `id` UUID PK
- `user_id` UUID FK
- `key` TEXT (ej: "prefiere_recordatorios_noche")
- `value` JSONB
- `confidence` REAL
- `updated_at` TIMESTAMPTZ

## Tablas operativas

### users

- TODO: completar después del diseño de auth.
- `id` UUID PK
- `email` TEXT UNIQUE
- `password_hash` TEXT (bcrypt)
- `created_at`, `updated_at`

### sessions

- TODO: completar.
- `id` UUID PK
- `user_id` UUID FK
- `mode` TEXT (productividad/estudio/...)
- `started_at`, `ended_at`

### audit_log

- TODO: completar.
- `id` UUID PK
- `user_id` UUID FK
- `operation` TEXT (read/write/update/delete)
- `target_table` TEXT
- `target_id` UUID
- `origin` JSONB (modelo, modo, tool)
- `created_at` TIMESTAMPTZ
