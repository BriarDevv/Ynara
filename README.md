# Ynara

Asistente personal adaptativo con IA, memoria propia y arquitectura
on-prem. Pensado para estudiantes y profesionales de 18 a 30 años en
LATAM, con arranque en Argentina.

> ¿Sos una IA leyendo este repo? **Empezá por
> [`AGENTS.md`](./AGENTS.md)**. Es el contrato del proyecto y las 10
> reglas no negociables.

## ¿Qué hace Ynara?

Cinco modos, una sola identidad:

| Modo | Para qué sirve | Modelo |
|------|----------------|--------|
| **Productividad** | Agendar, recordar, ejecutar acciones | Qwen 3.5-9B (agente) |
| **Estudio** | Tutoría, explicaciones, procesamiento de textos | Gemma 4 26B-A4B |
| **Bienestar** | Descarga emocional, acompañamiento | Gemma 4 26B-A4B |
| **Vida** | Charla casual, recomendaciones cotidianas | Gemma 4 26B-A4B |
| **Memoria** | Recall explícito de conversaciones pasadas | Qwen 3.5-9B (agente) |

Detalle en [`docs/product/MODES.md`](./docs/product/MODES.md).

## Stack en una mirada

- **Web**: Next.js 16, TypeScript strict, Tailwind v4, shadcn/ui, GSAP, Lenis.
- **Mobile**: Expo SDK 53+, NativeWind, TanStack Query.
- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery.
- **LLM**: vLLM en prod, Ollama en dev, Unsloth + QLoRA para fine-tuning, LlamaIndex para orquestación, Mem0 OSS v2 para memoria semántica.
- **DB**: Supabase como Postgres 16 gestionado + pgvector (MVP) → Postgres self-hosted (V2). Ver [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md).
- **Monorepo**: pnpm + Turborepo + Biome.

## Estructura del repo

```
ynara/
├── apps/
│   ├── web/        # Next.js 16
│   ├── mobile/     # Expo
│   └── backend/    # FastAPI + LLM + memoria
├── packages/
│   ├── shared-types/
│   ├── shared-schemas/
│   ├── ui/
│   └── config/
├── infra/          # Docker, vLLM, prod
├── docs/           # Arquitectura, producto, operaciones, convenciones
├── skills/         # Skills reutilizables para IAs (formato Anthropic)
└── scripts/        # Shells de utilidad
```

## Empezar

Antes de instalar nada, leer:

1. [`AGENTS.md`](./AGENTS.md) — contrato del repo.
2. [`docs/operations/INSTALL.md`](./docs/operations/INSTALL.md) — instalación local.
3. [`docs/operations/LOCAL-DEV.md`](./docs/operations/LOCAL-DEV.md) — flujo de desarrollo.

## Posicionamiento

Ynara es un producto comercial self-hosted. La ventaja defensiva es
**infraestructura propia**: modelos propios, memoria propia, deploy
propio. Los datos del usuario nunca salen del perímetro. La fase MVP
usa Supabase como Postgres gestionado por velocidad de arranque; la
fase V2 migra a Postgres self-hosted alineado al posicionamiento.

## Estado

Fase inicial: scaffold. Ver issues abiertas para roadmap.

## Licencia

Propietaria. Ver [`LICENSE`](./LICENSE).
