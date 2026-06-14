# Ynara

> Asistente personal adaptativo con memoria propia. On-prem, en
> rioplatense, para estudiantes y profesionales jóvenes de LATAM.

[![Web: Next.js 16](https://img.shields.io/badge/Web-Next.js%2016-black)](./apps/web)
[![Mobile: Expo 53+](https://img.shields.io/badge/Mobile-Expo%2053%2B-1B1F23)](./apps/mobile)
[![Backend: FastAPI + Pydantic v2](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Pydantic%20v2-009688)](./apps/backend)
[![LLM: vLLM (Gemma+Qwen)](https://img.shields.io/badge/LLM-vLLM%20(Gemma%2BQwen)-ff6b6b)](./infra/vllm)
[![DB: Postgres 16 + pgvector](https://img.shields.io/badge/DB-Postgres%2016%20%2B%20pgvector-4169E1)](./docs/architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md)
[![AI-friendly](https://img.shields.io/badge/AI--friendly-Claude%20%C2%B7%20Codex%20%C2%B7%20Gemini-8e44ad)](./AGENTS.md)
[![Phase: MVP](https://img.shields.io/badge/Phase-MVP-yellow)](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red)](./LICENSE)

Cinco modos (productividad, estudio, bienestar, vida, memoria) sobre dos
modelos propios (Gemma 4 12B + Qwen 3.5-9B), memoria semántica +
episódica + procedural sobre Postgres + pgvector, todo on-prem. Sin datos
de usuario saliendo del perímetro, sin lock-in a big tech.

- **Humanos**: empezá por [Quick Start](#quick-start) y después
  [`docs/operations/LOCAL-DEV.md`](./docs/operations/LOCAL-DEV.md).
- **Agentes IA**: leer primero [`AGENTS.md`](./AGENTS.md). Es bloqueante.
- **Solo frontend**: [`apps/web/README.md`](./apps/web/README.md) o
  [`apps/mobile/README.md`](./apps/mobile/README.md).
- **Solo backend**: [`apps/backend/README.md`](./apps/backend/README.md) +
  [`apps/backend/docs/`](./apps/backend/docs/).
- **Diseño / producto**: [`IDENTITY.md`](./IDENTITY.md) +
  [`docs/product/`](./docs/product/).

## Repo snapshot

| Métrica | Valor actual |
| --- | --- |
| Modos del producto | 5 (productividad, estudio, bienestar, vida, memoria) |
| Modelos LLM | 2 (Gemma 4 12B conversacional + Qwen 3.5-9B agente) |
| Capas de memoria | 3 (semántica, episódica, procedural) |
| Tools del agente Qwen | 8 (calendar×2, reminder×2, memory×4) |
| Apps | 3 (web Next.js 16, mobile Expo 53+, backend FastAPI) |
| Packages compartidos | 4 (shared-types, shared-schemas, ui, config) |
| ADRs aprobados | 10 |
| Skills reutilizables | 6 |
| Archivos tracked | ~500 |
| CODEOWNERS | 3 (@MateoGs013, @BriarDevv, @querques20) |

## Los 5 modos

| Modo | Para qué sirve | Modelo | Tools | Capas de memoria |
| --- | --- | --- | --- | --- |
| **Productividad** | Agendar, recordar, ejecutar | Qwen 3.5-9B (agente) | calendar, reminder, memory | semántica, episódica |
| **Estudio** | Tutoría, explicar, procesar textos | Gemma 4 12B | — | episódica, procedural |
| **Bienestar** | Descarga emocional, acompañar | Gemma 4 12B | — | procedural, semántica |
| **Vida** | Charla casual, recomendaciones | Gemma 4 12B | — | procedural |
| **Memoria** | Recall explícito de conversaciones | Qwen 3.5-9B (agente) | memory | las 3 capas |

Detalle de cada modo en [`docs/product/MODES.md`](./docs/product/MODES.md).
Configuración canónica en [`ynara.config.json`](./ynara.config.json).

## Quick Start

> **Antes de instalar deps**: leer [`AGENTS.md`](./AGENTS.md). Regla #1
> pide OK humano para `pnpm install` y `uv sync`. El script `init.sh`
> no instala nada — solo verifica que tengas las herramientas y copia
> los `.env.example` a `.env`.

### 1. Clonar y verificar entorno

```bash
git clone https://github.com/BriarDevv/Ynara.git
cd Ynara
bash scripts/init.sh
```

`init.sh` verifica `node`, `pnpm`, `python3`, `uv` y `docker`, y copia
los `.env.example` que falten. Si algo no está, instalá:

| Herramienta | Instalación |
| --- | --- |
| Node 20+ | https://nodejs.org |
| pnpm 10+ | `corepack enable && corepack prepare pnpm@latest --activate` |
| Python 3.12+ | https://python.org |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | https://docker.com |

### 2. Crear proyecto Supabase (fase MVP)

1. Crear proyecto en [supabase.com](https://supabase.com).
2. Habilitar extensiones en Dashboard → Database → Extensions: activar
   `vector` y `pgcrypto`.
3. Copiar la connection string desde Settings → Database → URI a la
   variable `DATABASE_URL` en `apps/backend/.env`.

En V2 esto se reemplaza por Postgres self-hosted; el resto del flujo
no cambia (ver [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md)).

### 3. Instalar dependencias (requiere OK humano por regla #1)

```bash
pnpm install                                    # frontend + monorepo
cd apps/backend && uv sync && cd -              # backend Python
```

### 4. Levantar stack local

```bash
make docker-dev-up                              # Redis local
cd apps/backend && uv run alembic upgrade head  # migrar contra Supabase
make dev-backend                                # FastAPI :8080
make dev-web                                    # Next.js :3000 (otra terminal)
make dev-mobile                                 # Expo (opcional)
```

### 5. (Opcional) Levantar vLLM local

Si tenés la 4080 Super o GPU NVIDIA con CUDA 12.x:

```bash
./infra/vllm/start-vllm.sh                      # Gemma :8000 + Qwen :8001
```

Sin GPU, el backend corre con Fakes (`FakeLlmClient`) por defecto. Para
apuntar a Ollama/vLLM real, setear `LLM_PRIMARY_BASE_URL` /
`LLM_SECONDARY_BASE_URL` (+ `LLM_TOPOLOGY`) en `apps/backend/.env`.

Guía paso a paso completa: [`docs/operations/INSTALL.md`](./docs/operations/INSTALL.md).
Flujo de desarrollo diario: [`docs/operations/LOCAL-DEV.md`](./docs/operations/LOCAL-DEV.md).

## Daily usage

| Comando | Qué hace |
| --- | --- |
| `make dev` | Stack completo (web + mobile + backend) vía Turbo |
| `make dev-web` | Solo Next.js (`:3000`) |
| `make dev-mobile` | Solo Expo |
| `make dev-backend` | Solo FastAPI con hot reload (`:8080`) |
| `make docker-dev-up` | Redis local en Docker |
| `make docker-dev-down` | Bajar Redis local |
| `make test` | Tests JS/TS (Turbo) + Python (pytest) |
| `make lint` | Biome (JS/TS) + Ruff (Python) |
| `make format` | Auto-fix de lint en ambos lenguajes |
| `make migrate-create m="texto"` | Nueva migración Alembic |
| `make migrate-up` | Aplicar migraciones pendientes |
| `make migrate-down` | Rollback de la última migración |
| `make reset-memory` | Borra memoria de un usuario (dev, destructivo) |
| `make export-user-data` | Exporta memoria + sesiones de un usuario |

Atajos completos en [`Makefile`](./Makefile).

## Stack

| Capa | Tecnología |
| --- | --- |
| Web | Next.js 16, TypeScript strict, Tailwind v4 (CSS-first), shadcn/ui, GSAP, Lenis, TanStack Query v5, Zustand v5, React Hook Form + Zod, Auth.js v5 |
| Mobile | Expo SDK 53+, Expo Router (file-based), NativeWind, TanStack Query, Zustand, expo-secure-store, expo-notifications |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, Celery 5.4+, uv, Ruff |
| LLM | vLLM (prod), Ollama (dev), Unsloth + QLoRA (fine-tuning), LlamaIndex (orquestación) |
| DB (MVP) | Supabase como Postgres 16 gestionado + pgvector, Redis (Upstash o Docker) |
| DB (V2) | Postgres 16 self-hosted + pgvector, Redis self-hosted |
| Monorepo | pnpm 10+, Turborepo 2.x, Biome 2.x |
| Deploy | Vercel (web), EAS (mobile), Cloudflare Tunnel + R2 (backend) |

## Modelos (dual-stack)

| Modelo | Rol | Lee memoria | Escribe memoria | Llama tools | Endpoint |
| --- | --- | --- | --- | --- | --- |
| **Gemma 4 12B** (dense) | Conversacional | Sí | No | No | `:8000/v1` |
| **Qwen 3.5-9B** | Agente | Sí | Sí | Sí | `:8001/v1` |

Razonamiento: [`ADR-002`](./docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md).
Ambos corren cuantizados (Q4/Q5) en una RTX 4080 Super 16GB vía vLLM.

## Memoria (3 capas)

| Capa | Qué guarda | Store | Quién escribe |
| --- | --- | --- | --- |
| **Semántica** | Hechos persistentes sobre el usuario | Postgres + pgvector + bge-m3 (1024-dim), engine in-house (ADR-010) | Qwen (async Celery) |
| **Episódica** | Resúmenes de sesiones pasadas con embedding | Postgres + pgvector + JSONB metadata | Qwen al cerrar sesión |
| **Procedural** | Preferencias y patrones | Postgres + JSONB | Qwen + heurísticas |

Tablas sagradas — cualquier migración requiere tests + 1 aprobación
humana explícita (regla #3 de [`AGENTS.md`](./AGENTS.md)). Derechos del usuario
(export, borrado, pausa, audit log) en
[`docs/product/MEMORY.md`](./docs/product/MEMORY.md).

## Flujo de un mensaje

```
Cliente (web/mobile)
  -> POST /v1/chat {text, mode}
  -> Auth JWT + rate limit
  -> Router LLM (decide modelo según modo)
  -> memory.search (capas activas del modo)
  -> Modelo (Gemma o Qwen)
       Qwen agente: tool calls en loop -> tools (calendar/reminder/memory)
  -> Respuesta al cliente
  -> Celery worker: consolida memoria (async, fuera del path)
```

Diagrama completo:
[`docs/architecture/diagrams/flow-mensaje.md`](./docs/architecture/diagrams/flow-mensaje.md).

## Estructura del repo

```
ynara/
├── AGENTS.md                # Contrato del repo — leer primero (humanos e IAs)
├── CLAUDE.md                # Adapter Claude Code         -> AGENTS.md
├── CODEX.md                 # Adapter OpenAI Codex        -> AGENTS.md
├── GEMINI.md                # Adapter Gemini Code Assist  -> AGENTS.md
├── DESIGN.md                # Sistema visual (vacío hasta aprobación)
├── IDENTITY.md              # 4 pilares de marca + voz
├── README.md                # Este archivo
├── ynara.config.json        # 5 modos + 2 modelos + memoria + infra
│
├── apps/
│   ├── web/                 # Next.js 16 + Tailwind v4 + shadcn/ui
│   ├── mobile/              # Expo SDK 53+ + NativeWind
│   └── backend/             # FastAPI + LLM + memoria
│       ├── app/
│       │   ├── api/v1/      # rutas HTTP
│       │   ├── core/        # config, security, deps
│       │   ├── models/      # SQLAlchemy
│       │   ├── schemas/     # Pydantic v2
│       │   ├── services/    # lógica de negocio (sin framework)
│       │   ├── llm/         # router + prompts + tools
│       │   ├── memory/      # 3 capas (semántica, episódica, procedural)
│       │   ├── workers/     # Celery
│       │   └── workflows/   # consolidación async
│       ├── alembic/         # migraciones (políticas + plantilla async)
│       └── docs/            # MODELS, ENDPOINTS, TOOLS, MIGRATIONS
│
├── packages/
│   ├── shared-types/        # types TS compartidos web/mobile
│   ├── shared-schemas/      # Zod schemas (mirror de Pydantic)
│   ├── ui/                  # componentes UI compartidos
│   └── config/              # tsconfig.base + biome + eslint
│
├── docs/
│   ├── architecture/        # 10 ADRs + 3 diagramas Mermaid
│   ├── product/             # VISION, MODES, MEMORY, TONE-OF-VOICE
│   ├── operations/          # INSTALL, LOCAL-DEV, DEPLOY, RUNBOOK, MIGRATION
│   └── conventions/         # COMMITS, GLOSSARY, AI-GUIDELINES, CODE-STYLE
│
├── infra/
│   ├── docker/              # docker-compose dev/prod + Dockerfile.backend
│   ├── vllm/                # start-vllm.sh para Gemma + Qwen
│   └── prod/                # systemd, Cloudflare Tunnel, backups (TODO)
│
├── skills/                  # 6 SKILL.md reutilizables
│   ├── add-new-mode/        # agregar un modo al producto
│   ├── add-llm-tool/        # agregar una tool al agente Qwen
│   ├── add-memory-type/     # agregar una capa de memoria (proceso pesado)
│   ├── adr-create/          # crear un ADR
│   └── create-ui-component/ # crear un componente UI
│
├── scripts/                 # init, seed, reset-memory, export-user-data
├── tests/e2e/               # Playwright (TODO configurar)
├── .github/                 # workflows, CODEOWNERS, PR/issue templates
├── .claude/ .codex/ .gemini/  # adapters por herramienta IA (sin contenido propio)
└── .omc/                    # local del dev (gitignored)
```

**Golden rule**: `AGENTS.md` y `docs/` son fuente de verdad.
`.claude/`, `.codex/`, `.gemini/` son adapters — nunca contenido propio.

## Para agentes IA

Si sos un agente IA (Claude Code, OpenAI Codex, Gemini Code Assist, Cursor,
Copilot, etc.) trabajando en este repo:

1. **Leer [`AGENTS.md`](./AGENTS.md)** — contrato del repo, 10 reglas no
   negociables.
2. **Leer el adapter de tu herramienta** —
   [`CLAUDE.md`](./CLAUDE.md), [`CODEX.md`](./CODEX.md),
   [`GEMINI.md`](./GEMINI.md).
3. **Leer el `AGENTS.md` del app que vayas a tocar** —
   [`apps/web/AGENTS.md`](./apps/web/AGENTS.md),
   [`apps/mobile/AGENTS.md`](./apps/mobile/AGENTS.md),
   [`apps/backend/AGENTS.md`](./apps/backend/AGENTS.md).
4. **Si es cambio arquitectónico**: leer los ADRs relevantes en
   [`docs/architecture/adrs/`](./docs/architecture/adrs/).

### Reglas duras (resumen, no negociables)

- OK humano antes de `pnpm install`, `uv sync`, `git commit`, `git push`,
  cambios en `.md` raíz, cambios en `ynara.config.json`, migraciones
  Alembic.
- Datos de usuario nunca fuera del perímetro: prohibido enviar a APIs de
  OpenAI, Anthropic, Google, etc. Toda inferencia es vLLM/Ollama local.
- Cliente JavaScript de Supabase prohibido desde el frontend. Todo
  acceso a datos pasa por la API de FastAPI.
- Tablas `semantic_memory`, `episodic_memory`, `procedural_memory` son
  sagradas: tests + 1 aprobación humana explícita para cualquier migración.
- Conventional Commits en español imperativo:
  `feat(web): agregar modo bienestar`,
  `fix(backend): corregir extracción episódica`.

Reglas completas: [`AGENTS.md`](./AGENTS.md). Reglas extendidas (15 más):
[`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Fase MVP → V2

Hoy estamos en **fase MVP**. La DB es Supabase como Postgres gestionado
para levantar rápido. La migración a Postgres self-hosted está planeada
para V2 post-validación de producto.

| Fase | DB | Cache | Inferencia | Por qué |
| --- | --- | --- | --- | --- |
| **MVP** (hoy) | Supabase (Postgres 16 + pgvector) | Upstash o Docker | vLLM on-prem | Velocidad sin DevOps inicial |
| **V2** (post-PMF) | Postgres 16 self-hosted | Redis self-hosted | vLLM on-prem | Alineado a "infra propia" |

**Reglas que hacen la migración trivial**:

- Cliente JS de Supabase prohibido en frontend.
- Supabase Auth, Storage, Realtime, Edge Functions, RLS: todos prohibidos.
- Toda autorización vive en FastAPI.
- La única referencia a Supabase es `DATABASE_URL` en variables del backend.

Razonamiento: [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md).
Plan de cutover: [`docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`](./docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md).

## Posicionamiento

Producto comercial self-hosted. La ventaja defensiva es **infra propia**:

- **Modelos propios** — no dependemos de OpenAI, Anthropic, Google.
- **Memoria propia** — el dato vive donde nosotros lo ponemos, no en SaaS de terceros.
- **Tono y lengua** — rioplatense específico, no traducido a escala global.
- **Soberanía** — los datos del usuario no salen del perímetro.

Visión completa: [`docs/product/VISION.md`](./docs/product/VISION.md).
Identidad de marca: [`IDENTITY.md`](./IDENTITY.md).

## Read Next

| Querés... | Leer |
| --- | --- |
| Mapa completo de docs | [`docs/README.md`](./docs/README.md) |
| Entender el contrato de IA | [`AGENTS.md`](./AGENTS.md) |
| Empezar a desarrollar | [`docs/operations/INSTALL.md`](./docs/operations/INSTALL.md) → [`docs/operations/LOCAL-DEV.md`](./docs/operations/LOCAL-DEV.md) |
| Trabajar en frontend web | [`apps/web/README.md`](./apps/web/README.md) + [`apps/web/AGENTS.md`](./apps/web/AGENTS.md) |
| Trabajar en mobile | [`apps/mobile/README.md`](./apps/mobile/README.md) + [`apps/mobile/EAS.md`](./apps/mobile/EAS.md) |
| Trabajar en backend | [`apps/backend/README.md`](./apps/backend/README.md) + [`apps/backend/docs/`](./apps/backend/docs/) |
| Agregar una tool al agente | [`skills/add-llm-tool/SKILL.md`](./skills/add-llm-tool/SKILL.md) |
| Agregar un modo nuevo | [`skills/add-new-mode/SKILL.md`](./skills/add-new-mode/SKILL.md) |
| Crear un ADR | [`skills/adr-create/SKILL.md`](./skills/adr-create/SKILL.md) |
| Crear migración Alembic | [`apps/backend/docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md) |
| Deploy | [`docs/operations/DEPLOY.md`](./docs/operations/DEPLOY.md) + [`docs/operations/RUNBOOK.md`](./docs/operations/RUNBOOK.md) |
| Entender la voz del producto | [`IDENTITY.md`](./IDENTITY.md) + [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md) |
| Glosario interno | [`docs/conventions/GLOSSARY.md`](./docs/conventions/GLOSSARY.md) |
| Política de seguridad | [`SECURITY.md`](./SECURITY.md) |
| Cómo contribuir | [`CONTRIBUTING.md`](./CONTRIBUTING.md) |

## Equipo

3 CODEOWNERS del repo:
[@MateoGs013](https://github.com/MateoGs013),
[@BriarDevv](https://github.com/BriarDevv),
[@querques20](https://github.com/querques20).
Responsabilidades por path en [`.github/CODEOWNERS`](./.github/CODEOWNERS).

## Licencia

Propietaria. Ver [`LICENSE`](./LICENSE).
