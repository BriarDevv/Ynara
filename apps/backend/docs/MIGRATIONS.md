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
| `20260615_0200_drop_redundant_conversation_turns_indexes.py` | `b7e2f4a16c9d` | `c4e8a1d50b93` | **HEAD.** Tabla **operativa** `conversation_turns`: dropea los 3 índices parciales (`user_id`; `session_id`; `(session_id, seq)`) y crea el único índice compuesto `(user_id, session_id, seq)` que matchea el patrón real de queries del store. El `downgrade` recrea los 3 originales (round-trip limpio). |

## Migraciones peligrosas

Drops, renames, type changes con data — documentar en el commit + tener
plan de rollback escrito en el PR.

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
