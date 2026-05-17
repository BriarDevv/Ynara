# ADR-004: Postgres + pgvector vs vector DB dedicada

## Estado
Aceptado

## Fecha
2026-05-XX  <!-- TODO: fecha exacta cuando se apruebe en PR -->

## Contexto

Memoria semántica de Ynara necesita búsqueda por similitud sobre
embeddings (bge-m3, 1024-dim). Opciones:

1. **Postgres + pgvector** — extensión oficial, índices HNSW e IVF,
   transaccional con el resto de las tablas.
2. **Pinecone** — vector DB hosted, performance premium, vendor
   lock-in.
3. **Qdrant / Weaviate self-hosted** — vector DB OSS dedicada,
   stack separado del relacional.

## Decisión

Postgres 16 + pgvector como única DB para todo: relacional y
embeddings. Mismo stack en MVP (sobre Supabase, ADR-005) y en V2
(self-hosted).

## Consecuencias positivas

- **Un solo stack de DB**: simplifica ops, backups, monitoring.
- Joins entre tablas relacionales y embeddings en una sola query.
- Transaccionalidad ACID sobre escrituras de memoria.
- pgvector con HNSW es performante hasta varios millones de vectores.
- Alineado al posicionamiento "infra propia": en V2 corre on-prem
  100%.

## Consecuencias negativas

- Para datasets gigantes (>50M vectores), las vector DBs dedicadas
  escalan mejor. No es nuestro caso a corto/mediano plazo.
- Ops de Postgres con pgvector requiere conocer tuning específico
  (work_mem, parallel workers, índices HNSW).

## Mitigaciones

- En MVP, Supabase preinstala pgvector y resuelve la ops.
- En V2, runbook de Postgres self-hosted incluye guía de tuning.
- Si en algún futuro lejano hace falta dedicado, se evalúa Qdrant
  self-hosted (no Pinecone, por regla #4 — no datos en SaaS de
  terceros).

## Alternativas descartadas

- **Pinecone**: viola regla #4 (datos en SaaS externo).
- **Qdrant / Weaviate**: stack extra para mantener sin beneficio
  claro en el rango de escala esperado.
- **Mongo + Atlas Vector Search**: introduce un stack relacional
  paralelo, complica todo.
