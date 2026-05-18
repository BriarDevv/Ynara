# docs/architecture/ — Arquitectura técnica de Ynara

Acá vive el "porqué" detrás de las decisiones técnicas del proyecto.

## Subcarpetas

- `adrs/` — Architecture Decision Records, uno por decisión
  significativa. Inmutables una vez aprobados.
- `diagrams/` — Diagramas del sistema en Mermaid + assets exportados.
- `informe-tecnico.pdf` — informe técnico fundacional del proyecto
  (Mayo 2026). Documenta el porqué de cada decisión (modelos,
  memoria, infra) y trae al final una bitácora de actualizaciones
  de versión. Las versiones puntuales se actualizan en el PDF + en
  los manifests; los cambios de decisión arquitectónica van por ADR.

## ADRs actuales

| # | Título | Estado |
|---|--------|--------|
| 001 | Monorepo vs multirepo | Aceptado |
| 002 | Gemma + Qwen dual stack | Aceptado |
| 003 | Mem0 vs Letta para memoria | Aceptado |
| 004 | Postgres + pgvector vs Pinecone | Aceptado |
| 005 | Supabase en MVP, Postgres self-hosted en V2 | Aceptado |

## Cómo crear un ADR nuevo

Ver `skills/adr-create/SKILL.md`. En resumen:

1. Copiar la plantilla base (cualquiera de los ADRs existentes sirve).
2. Numerar consecutivo (ADR-006, ADR-007, ...).
3. Llenar contexto, decisión, consecuencias.
4. PR con review humano. Cuando el ADR queda en "Aceptado", no se
   modifica más: si la decisión cambia, se crea un ADR nuevo que
   marca al anterior como "Superseded by ADR-XXX".
