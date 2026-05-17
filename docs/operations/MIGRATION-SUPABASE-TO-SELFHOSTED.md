# Migración Supabase → Postgres self-hosted (Fase V2)

> Plan de cutover para mover la DB de Supabase (fase MVP) a Postgres
> 16 self-hosted (fase V2), según
> [`ADR-005`](../architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md).

## Pre-requisitos

- Producto validado (PMF mínimo alcanzado).
- VPS provisionada con: Postgres 16 + pgvector, recursos suficientes
  para el dataset actual + 12 meses de crecimiento.
- Redis self-hosted en la misma VPS o vecina.
- Backups configurados (pg_dump + cron, encrypted con AES-256, off-site
  en R2).
- Monitoring (CPU, RAM, disk, slow queries).

## Pasos

### 1. Provisionar Postgres self-hosted

- Postgres 16 con `shared_preload_libraries = 'pgvector'`.
- Tuning base: `shared_buffers`, `work_mem`, `maintenance_work_mem`
  según RAM disponible.
- Crear extensión: `CREATE EXTENSION IF NOT EXISTS vector;`.
- Crear usuarios + roles equivalentes a los de Supabase.

### 2. Backups y observabilidad

- Cron `pg_dump` diario + retención 30 días.
- Encripción AES-256 antes de subir a R2.
- Monitoring: pg_stat_statements habilitado.
- Alertas: disk > 80%, connection saturation > 80%.

### 3. Snapshot inicial desde Supabase

```sh
pg_dump --no-owner --no-acl --clean --if-exists \
        --schema=public \
        $SUPABASE_DATABASE_URL > supabase-snapshot-$(date +%F).sql
```

### 4. Restaurar en self-hosted

```sh
psql $SELFHOSTED_DATABASE_URL < supabase-snapshot-$(date +%F).sql
```

### 5. Verificar paridad

- `SELECT COUNT(*) FROM semantic_memory;` en ambos → match exacto.
- Idem para `episodic_memory`, `procedural_memory`, `users`, y
  tablas operativas.
- Verificar índices HNSW (`\d+ semantic_memory` en psql).

### 6. Staging cutover

- Desplegar backend de staging apuntando a self-hosted.
- Smoke tests: login, chat en cada modo, memoria read+write.
- Soak test 24-48hs con tráfico mirrored.

### 7. Cutover de producción

Ventana de mantenimiento anunciada:

1. Pausar Celery workers (no nueva escritura de memoria).
2. Drenar requests en curso (graceful shutdown del backend).
3. Snapshot final de Supabase (delta desde paso 3).
4. Aplicar delta en self-hosted.
5. Cambiar `DATABASE_URL` en variables de entorno del backend.
6. Restart backend + workers.
7. Verificar health + smoke tests.
8. Reactivar tráfico.

Duración estimada: <!-- TODO: estimar cuando tengamos baseline de
tamaño de DB -->.

### 8. Periodo de gracia

- Mantener Supabase activo en read-only durante 30 días.
- Snapshots periódicos por si hay que rollbackear.

### 9. Decomisionado

- Cancelar suscripción Supabase.
- Confirmar borrado de datos del lado de Supabase según su política.

## Open questions

<!-- TODO -->
- ¿Replicación lógica continua durante el periodo de gracia?
- ¿Quién es el dueño operativo del Postgres self-hosted post-cutover?
- Plan de DR (disaster recovery) en self-hosted.
