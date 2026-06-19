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
| 003 | Mem0 vs Letta para memoria | Superseded by ADR-010 |
| 004 | Postgres + pgvector vs Pinecone | Aceptado |
| 005 | Supabase en MVP, Postgres self-hosted en V2 | Aceptado |
| 006 | Pinear next-auth a 5.0.0-beta.31 hasta release estable | Aceptado |
| 007 | Políticas operacionales de memoria (decay, retention diferenciada, encriptación a nivel campo) | Aceptado |
| 008 | Modelo de embedding — BAAI bge-m3 (1024-dim, on-prem) | Aceptado |
| 009 | Topología de serving vLLM y parsers de tool-calling | Aceptado — refinado por ADR-013/ADR-014 |
| 010 | Arquitectura de memoria v2 — engine in-house sobre storage cifrado propio (supersede ADR-003) | Aceptado |
| 011 | Auth permanece layer-split — criterio de feature-packages vs dominios ordinarios | Aceptado — refinado por ADR-015 |
| 012 | Modelo conversacional Gemma 4 12B y topología single_process co-residente en 16 GB | Aceptado |
| 013 | Config de serving LLM explícita (endpoints → served models) | Aceptado — refinado por ADR-014 |
| 014 | Motor de serving local = Ollama/GGUF en 16 GB (vLLM reservado para 24 GB+) | Aceptado |
| 015 | Librería JWT = PyJWT (sale python-jose); bcrypt directo (sale passlib) | Aceptado |
| 016 | Código compartido web/mobile vía packages/core (ex-ADR-012) | Aceptado |
| 017 | App de administración interna (apps/admin): observabilidad y control plane | Propuesto |

> Hay 17 ADRs lógicos (ADR-001..017, sin huecos): el ADR-016 era un
> segundo ADR-012 duplicado y se renumeró para garantizar números únicos.

## Cómo crear un ADR nuevo

Ver `skills/adr-create/SKILL.md`. En resumen:

1. Copiar la plantilla base (cualquiera de los ADRs existentes sirve).
2. Numerar consecutivo (ADR-006, ADR-007, ...).
3. Llenar contexto, decisión, consecuencias.
4. PR con review humano. Cuando el ADR queda en "Aceptado", no se
   modifica más: si la decisión cambia, se crea un ADR nuevo que
   marca al anterior como "Superseded by ADR-XXX".
