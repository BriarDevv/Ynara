# MIGRATIONS.md — Política de migraciones Alembic

## Naming

`YYYYMMDD_HHMM_descripcion_corta.py`

Ejemplos:
- `20260518_1430_add_episodic_memory_table.py`
- `20260520_0900_drop_legacy_session_field.py`

## Regla de oro

Una migración = un cambio lógico atómico. No mezclar cambios no
relacionados.

## downgrade obligatorio

Siempre implementar `downgrade()`. Si la migración borra datos sin
posibilidad de revertir (ej: drop column con datos), documentar en el
docstring + agregar el riesgo al PR.

## Tablas sagradas 🔴

Las siguientes tablas requieren **tests pasando + 1 aprobación humana
explícita** (review formal en el PR, además del operador autor) para
cualquier migración que las afecte (regla #3 de `AGENTS.md`):

- `semantic_memory`
- `episodic_memory`
- `procedural_memory`
- `audit_log`

(`users` / `sessions` / `conversation_turns` son **operativas**: review normal en
el PR, sin el gate extra de regla #3. El perímetro sagrado es la memoria cifrada
del moat + el `audit_log` inmutable — la misma lista que AGENTS §0 /
`app/models/{memory,audit}.py`. `conversation_turns` es un buffer transitorio que
se purga tras consolidar; aunque cifra su `content` per-user por regla #4, no es
parte del moat: su migración va por review normal.)

Esto es regla #3 de [`AGENTS.md`](../../../AGENTS.md).

## Migraciones registradas

| Archivo | Revision | Down revision | Qué hace |
|---|---|---|---|
| `20260529_1949_initial_schema.py` | `b7b06025f4bb` | (inicial) | 6 tablas sagradas/operativas, 4 enums, pgvector + pgcrypto. |
| `20260602_1015_audit_log_block_update_trigger.py` | `a1f3c9d27e84` | `b7b06025f4bb` | Trigger BEFORE UPDATE que bloquea UPDATE sobre `audit_log` (inmutabilidad). |
| `20260614_1700_conversation_turns_table.py` | `c4e8a1d50b93` | `a1f3c9d27e84` | Tabla **operativa** `conversation_turns` (buffer de turnos para la episódica, issue #209) + enum `turn_role_enum` + UNIQUE `(session_id, seq)` + 3 índices parciales. |
| `20260615_0200_drop_redundant_conversation_turns_indexes.py` | `b7e2f4a16c9d` | `c4e8a1d50b93` | Tabla **operativa** `conversation_turns`: dropea los 3 índices parciales (`user_id`; `session_id`; `(session_id, seq)`) y crea el único índice compuesto `(user_id, session_id, seq)` que matchea el patrón real de queries del store. El `downgrade` recrea los 3 originales (round-trip limpio). |
| `20260619_1200_add_is_admin_and_admin_audit.py` | `f3a9c1d27e84` | `b7e2f4a16c9d` | Agrega `is_admin` a `users` (`server_default=false`, no rompe filas existentes) + crea la tabla **operativa** `admin_audit` (audit de acciones del operador del panel `/v1/admin/*`; NO es `audit_log`, que es sagrada e inmutable). `downgrade` simétrico (dropea solo la columna y la tabla). |
| `20260620_2200_index_operational_date_columns.py` | `d1c2b3a49e87` | `f3a9c1d27e84` | Índices btree **aditivos** sobre tablas **operativas**: `sessions.started_at` y `users.created_at` (el panel admin filtra/agrupa por fecha en casi todos sus endpoints; sin índice = sequential scans crecientes). `downgrade` simétrico. |
| `20260622_1200_calendar_events_table.py` | `e5d9f2a73c1b` | `d1c2b3a49e87` | Tabla **operativa** `calendar_events` (dominio Agenda, ADR-023) + enum `event_status_enum` + FK a `users` (`ON DELETE CASCADE`) + índices en `user_id` y `start_at`. NO toca `mode_enum` (ya existe; `mode` lo reusa con `create_type=False`). `downgrade` dropea índices + tabla + el enum (round-trip limpio). |
| `20260622_1400_tasks_table.py` | `c3dcbf9ab7d9` | `e5d9f2a73c1b` | Tabla **operativa** `tasks` (dominio TAREAS, Fase D1, espejo de Agenda) + enum `task_status_enum` (pending/done) + FK a `users` (`ON DELETE CASCADE`) + índice en `user_id`. `scheduled_at` / `duration_min` NULLABLE (una prioridad puede no tener horario). El alta la hace el agente (`task.create_task`); el CRUD HTTP expone GET + PATCH (toggle de estado). `downgrade` dropea índice + tabla + el enum (round-trip limpio, simétrico). |
| `20260623_1200_index_episodic_occurred_at.py` | `e5f1a2b3c4d6` | `c3dcbf9ab7d9` | Índice btree **aditivo** sobre la tabla **SAGRADA** `episodic_memory` (`occurred_at`, regla #3): el panel admin lista la episódica reciente con `ORDER BY occurred_at DESC LIMIT N` sin filtro de `user_id` → seq-scan + sort de toda la tabla; un btree ascendente sirve el DESC por backward scan. NO destruye datos; `downgrade` simétrico (dropea solo el índice). |
| `20260624_1200_index_memory_created_at.py` | `b8e4f2a1c3d6` | `e5f1a2b3c4d6` | Índices btree **aditivos** sobre las 3 tablas **SAGRADAS** de memoria (`semantic_memory`/`episodic_memory`/`procedural_memory`, `created_at`, regla #3): las métricas de crecimiento/moat del panel admin (`admin_metrics.py`) corren `COUNT WHERE created_at < start` + `date_trunc('day', created_at)` cross-user → seq-scan + sort por request. NO destruye datos; `downgrade` simétrico (dropea solo los 3 índices, orden inverso). |
| `20260624_1400_index_tasks_user_id_scheduled_at.py` | `c1d2e3f4a5b6` | `b8e4f2a1c3d6` | **HEAD.** Índice btree **aditivo** sobre la tabla **operativa** `tasks` (`(user_id, scheduled_at)`, ALB-04): el listado del dashboard "Hoy" filtra por `user_id` y ordena por `scheduled_at` → el compuesto acota el scan al user y sirve el orden sin sort. NO toca `ix_tasks_user_id` (FK). `downgrade` simétrico. |

## Migraciones peligrosas

Drops, renames, type changes con data — documentar en el commit + tener
plan de rollback escrito en el PR.

**Índices a escala (`CREATE INDEX` sin `CONCURRENTLY`):** las migraciones de
índices (`20260620`, `20260623`, `20260624_*`) usan `CREATE INDEX` simple, que
toma un lock de escritura sobre la tabla mientras construye el índice. Para el MVP
las tablas son chicas y el build es instantáneo, así que es seguro. **A escala**
(tablas de memoria con millones de filas) un `CREATE INDEX` bloquearía las
escrituras durante el build: migrar esos índices a `CREATE INDEX CONCURRENTLY`
(que NO bloquea, pero NO puede correr dentro de una transacción → `op.create_index(...,
postgresql_concurrently=True)` + `op.get_context().autocommit_block()` o una
migración fuera de transacción). Decisión consciente, no olvido (auditoría SEC-R4-02).

## Cómo crear

```sh
cd apps/backend
uv run alembic revision --autogenerate -m "descripcion corta"
```

Revisar el archivo generado. **Casi siempre hay que editarlo a
mano** — `autogenerate` se equivoca con índices vectoriales, tipos
custom, etc.

## Cómo aplicar

```sh
uv run alembic upgrade head     # aplicar hasta el último
uv run alembic upgrade +1       # aplicar solo la siguiente
```

## Cómo rollback

```sh
uv run alembic downgrade -1     # bajar uno
uv run alembic downgrade <rev>  # bajar a revisión específica
```

## Verificar antes de mergear

> ⚠️ El roundtrip `downgrade` **destruye datos**: corré estos comandos SOLO contra
> una DB de tests (`TEST_DATABASE_URL`, p.ej. `localhost:5433/ynara_test`), **nunca**
> contra el `DATABASE_URL` de dev. Por default ese `DATABASE_URL` apunta a la DB
> **local** (`localhost:5433/ynara_dev`); el riesgo de tocar prod aplica solo si se
> cambió manualmente a la Supabase de prod (OPCION B del `.env.example`). `env.py`
> apunta el roundtrip a `TEST_DATABASE_URL` justamente para evitarlo en cualquier caso.

```sh
uv run alembic check            # ¿el modelo coincide con la última migración?
uv run alembic upgrade head     # ¿corre sin errores?
uv run alembic downgrade -1     # ¿el downgrade corre sin errores?
uv run alembic upgrade head     # subir de nuevo
```

## Nota Supabase (fase MVP)

Durante la fase MVP, las migraciones se aplican contra Supabase.

- Antes de la primera migración con embeddings, verificar que
  Supabase tenga la extensión `pgvector` habilitada en el dashboard
  (Database → Extensions → vector).
- `gen_random_uuid()` requiere la extensión `pgcrypto`. Habilitarla
  desde el dashboard o crearla en una migración inicial:
  `op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')`.
- Supabase tiene un límite de conexiones (~15 en free tier). Usar
  `DATABASE_POOL_SIZE` razonable y considerar usar el pooler
  transaccional para producción.

En V2 (Postgres self-hosted), estas notas dejan de aplicar.

## Convención de imports en migraciones

- Importar `op` y `sa` siempre.
- Importar `pgvector.sqlalchemy.Vector` cuando se use.
- **No** importar modelos del proyecto desde migraciones — las
  migraciones tienen que ser estables aunque cambien los modelos.

## Index HNSW

Para columnas `VECTOR(...)`, índice HNSW:

```python
op.execute("""
    CREATE INDEX semantic_memory_embedding_hnsw_idx
    ON semantic_memory
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
""")
```

`m` y `ef_construction` son tunables; los valores arriba son un
default razonable para hasta unos cientos de miles de vectores.
