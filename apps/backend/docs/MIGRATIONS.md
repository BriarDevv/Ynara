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
- `users`

Esto es regla #3 de [`AGENTS.md`](../../../AGENTS.md).

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
> contra el `DATABASE_URL` de dev — que resuelve a la **Supabase de prod**. `env.py`
> apunta el roundtrip a `TEST_DATABASE_URL` justamente por esto.

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
