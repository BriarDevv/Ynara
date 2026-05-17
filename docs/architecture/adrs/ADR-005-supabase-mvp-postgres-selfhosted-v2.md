# ADR-005: Supabase en MVP, Postgres self-hosted en V2

## Estado
Aceptado

## Fecha
2026-05-XX  <!-- TODO: fecha exacta cuando se apruebe en PR -->

## Contexto

Ynara necesita una base de datos PostgreSQL con extensión pgvector
desde el día uno. Hay dos opciones:

1. Supabase como Postgres gestionado (rápido de levantar, free tier
   generoso, pgvector preinstalado).
2. Postgres self-hosted desde día uno (alineado al posicionamiento
   "infra propia" del producto, más DevOps inicial).

## Decisión

Usar Supabase **únicamente como Postgres gestionado** durante la fase
MVP. Migrar a Postgres self-hosted en la fase V2 (post-validación de
producto).

## Reglas que hacen la migración trivial

1. **Prohibido** usar el cliente JavaScript de Supabase desde el
   frontend (web o mobile). Todo acceso a datos pasa por la API de
   FastAPI.
2. **Prohibido** usar Supabase Auth, Storage, Realtime, Edge
   Functions.
3. **Prohibido** usar Row Level Security (RLS) de Supabase como
   mecanismo de autorización primario. La autorización vive en
   FastAPI.
4. La única referencia a Supabase en el código es el connection
   string en variables de entorno del backend (`DATABASE_URL`).

Estas reglas son **bloqueantes** y forman parte de la regla #5 de
`AGENTS.md`.

## Consecuencias positivas

- Día uno productivo sin invertir en DevOps.
- Free tier de Supabase alcanza para el MVP completo.
- Backups automáticos incluidos.
- pgvector preinstalado.
- Migración futura es solo cambiar `DATABASE_URL`.

## Consecuencias negativas

- Dependencia de un servicio externo durante MVP (mitigado por las
  reglas anteriores).
- Aparente contradicción con el posicionamiento "infra propia" hasta
  V2 (documentado y comunicado al equipo internamente; no se
  comunica como "uso Supabase" hacia afuera porque a efectos del
  contrato con el usuario nunca lo es).

## Plan de migración a V2

Ver `docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`.

## Alternativas descartadas

- **Postgres self-hosted desde día 1**: DevOps inicial demasiado alto
  para velocidad de validación que necesitamos.
- **Neon / Railway / otros gestionados**: mismo argumento que
  Supabase, pero sin la ventaja del free tier amplio y pgvector
  preinstalado.
