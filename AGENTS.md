# AGENTS.md — Contrato del repo Ynara

> Contrato AI-neutral para trabajar en este repo. Cualquier agente IA (Claude Code, OpenAI Codex, Gemini Code Assist, Cursor, Copilot) **lee este archivo primero**. Los adapters específicos por herramienta viven en [`CLAUDE.md`](./CLAUDE.md), [`CODEX.md`](./CODEX.md), [`GEMINI.md`](./GEMINI.md) y solo contienen punteros + atajos: la fuente canónica es esta.

## Quickstart 30s

Ynara es un asistente personal adaptativo on-prem con memoria propia. Stack: Next.js 16 (web) + Expo 53+ (mobile) + FastAPI + Pydantic v2 + SQLAlchemy 2 async (backend) + vLLM con dual stack Gemma 4 26B-A4B (conversacional) + Qwen 3.5-9B (agente) + Mem0 OSS v2 + Postgres 16 + pgvector.

**Reglas más críticas**: (1) OK humano antes de commit/push/install/migraciones; (2) datos del usuario nunca fuera del perímetro; (3) cliente Supabase prohibido en frontend; (4) tablas de memoria sagradas (2 aprobaciones).

**Antes de cada PR**: `bash scripts/ynara-doctor.sh` debe `exit 0`.

## Golden rule

Los archivos `.md` raíz (este, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `DESIGN.md`, `IDENTITY.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`) y la carpeta `docs/` son **fuente de verdad**.

Las carpetas `.claude/`, `.codex/`, `.gemini/` son **adapters** para los IDEs/CLIs de IA: solo punteros y atajos específicos de cada herramienta. Si hay un conflicto entre adapter y fuente canónica, gana la fuente canónica.

## Read Order

### Always first

1. Este archivo (`AGENTS.md`).
2. [`README.md`](./README.md).

### Then choose by task

| Tarea | Leer en este orden |
| --- | --- |
| Onboarding al repo | `README.md`<br>→ [`docs/README.md`](./docs/README.md)<br>→ [`docs/conventions/GLOSSARY.md`](./docs/conventions/GLOSSARY.md) |
| Agregar o modificar un modo | [`docs/product/MODES.md`](./docs/product/MODES.md)<br>→ [`ynara.config.json`](./ynara.config.json)<br>→ `apps/backend/app/llm/router.py`<br>→ [`skills/add-new-mode/SKILL.md`](./skills/add-new-mode/SKILL.md) |
| Agregar una tool al agente Qwen | [`apps/backend/docs/TOOLS.md`](./apps/backend/docs/TOOLS.md)<br>→ `apps/backend/app/llm/tools/`<br>→ [`skills/add-llm-tool/SKILL.md`](./skills/add-llm-tool/SKILL.md) |
| Tocar memoria (lectura) | [`docs/product/MEMORY.md`](./docs/product/MEMORY.md)<br>→ `apps/backend/app/memory/` (wrappers) |
| Tocar memoria (esquema o migración) | [`ADR-003`](./docs/architecture/adrs/ADR-003-mem0-vs-letta.md)<br>→ [`ADR-004`](./docs/architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md)<br>→ [`docs/MODELS.md`](./apps/backend/docs/MODELS.md)<br>→ [`docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md)<br>→ **2 aprobaciones humanas** |
| Endpoint HTTP nuevo | [`docs/ENDPOINTS.md`](./apps/backend/docs/ENDPOINTS.md)<br>→ `apps/backend/app/api/v1/`<br>→ `apps/backend/app/services/`<br>→ schema en `apps/backend/app/schemas/` |
| Modelo SQLAlchemy nuevo | [`docs/MODELS.md`](./apps/backend/docs/MODELS.md)<br>→ `apps/backend/app/models/`<br>→ migración Alembic con tests |
| Migración Alembic | [`docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md)<br>→ `apps/backend/alembic/env.py`<br>→ plantilla `script.py.mako` |
| Workflow Celery nuevo | `apps/backend/app/workflows/`<br>→ `apps/backend/app/workers/celery_app.py` |
| Cambio arquitectónico (stack, infra, deps mayores) | [`docs/architecture/adrs/`](./docs/architecture/adrs/)<br>→ [`skills/adr-create/SKILL.md`](./skills/adr-create/SKILL.md)<br>→ **ADR aprobado antes del PR de implementación** |
| Frontend web | [`apps/web/AGENTS.md`](./apps/web/AGENTS.md)<br>→ [`apps/web/README.md`](./apps/web/README.md)<br>→ [`DESIGN.md`](./DESIGN.md) (placeholder)<br>→ `apps/web/src/app/globals.css` |
| Mobile | [`apps/mobile/AGENTS.md`](./apps/mobile/AGENTS.md)<br>→ [`apps/mobile/EAS.md`](./apps/mobile/EAS.md)<br>→ `apps/mobile/app.json` |
| Migración Supabase → self-hosted | [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md)<br>→ [`docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`](./docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md) |
| Deploy o incidente | [`docs/operations/DEPLOY.md`](./docs/operations/DEPLOY.md)<br>→ [`docs/operations/RUNBOOK.md`](./docs/operations/RUNBOOK.md) |
| Entender la voz del producto | [`IDENTITY.md`](./IDENTITY.md)<br>→ [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md)<br>→ tono por modo en `MODES.md` |
| Convenciones de commits | [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) |
| Reglas extendidas (estilo, anti-patterns) | [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md)<br>+ [`docs/conventions/CODE-STYLE.md`](./docs/conventions/CODE-STYLE.md) |
| Crear un skill nuevo | [`skills/README.md`](./skills/README.md)<br>→ cualquier `skills/*/SKILL.md` como plantilla |
| Histórico o por qué se decidió X | [`docs/architecture/adrs/`](./docs/architecture/adrs/) (inmutables, ordenados por número) |

## Repo Map

| Path | Por qué te importa |
| --- | --- |
| `AGENTS.md` | Este archivo — contrato del repo, leer primero |
| `CLAUDE.md` / `CODEX.md` / `GEMINI.md` | Adapters por IDE — solo punteros, sin contenido propio |
| `IDENTITY.md` | 4 pilares de marca + voz: qué es Ynara y qué no es |
| `DESIGN.md` | Sistema visual — placeholder hasta aprobación del equipo |
| `ynara.config.json` | Configuración canónica: 5 modos, 2 modelos, capas de memoria, fase de infra |
| `apps/web/` | Next.js 16 + Tailwind v4 CSS-first (sin `tailwind.config.ts`) + shadcn/ui |
| `apps/mobile/` | Expo 53+ + Expo Router + NativeWind (todavía sobre Tailwind 3) |
| `apps/backend/app/api/v1/` | Rutas HTTP, un módulo por dominio |
| `apps/backend/app/core/` | Settings (Pydantic Settings), security (JWT/bcrypt esqueleto), deps |
| `apps/backend/app/llm/router.py` | Único punto de entrada al LLM. Decide modelo según modo |
| `apps/backend/app/llm/tools/` | Tools que solo Qwen llama (catálogo en `docs/TOOLS.md`) |
| `apps/backend/app/memory/` | Wrappers de las 3 capas. **Tablas sagradas** (regla #3) |
| `apps/backend/app/services/` | Lógica de negocio — no importa de FastAPI ni de ORM directo |
| `apps/backend/app/workers/` | Instancia Celery + autodiscovery de workflows |
| `apps/backend/app/workflows/` | Tasks Celery (consolidación de memoria, resúmenes episódicos) |
| `apps/backend/alembic/` | Migraciones — naming `YYYYMMDD_HHMM_slug`, env async |
| `apps/backend/docs/` | Catálogos vivos: MODELS, ENDPOINTS, TOOLS, MIGRATIONS |
| `packages/shared-types/` | Types TS compartidos web+mobile (mirror manual de Pydantic) |
| `packages/shared-schemas/` | Zod schemas — validación cliente, mirror de Pydantic |
| `packages/ui/` | Componentes UI realmente compartibles entre web y mobile |
| `packages/config/` | tsconfig.base estricto + biome + eslint compartidos |
| `docs/architecture/adrs/` | 5 ADRs inmutables. Cualquier cambio arquitectónico nuevo = ADR |
| `docs/conventions/AI-GUIDELINES.md` | 15 reglas extendidas + landmines aprendidas |
| `infra/vllm/` | `start-vllm.sh` para Gemma + Qwen en la RTX 4080 |
| `infra/docker/` | docker-compose dev (solo Redis) y prod |
| `skills/*/SKILL.md` | 5 procedimientos reutilizables para humanos e IAs |
| `scripts/ynara-doctor.sh` | Validaciones pre-PR — exit 0 obligatorio |

## Las 10 reglas no negociables

| # | Regla | Severidad |
| --- | --- | --- |
| 1 | **Confirmación humana** antes de `git commit`, `git push`, `git rebase`, `git tag`, `pnpm add`, `pnpm install`, `uv add`, `uv sync`, cambios en `.md` raíz, cambios en `ynara.config.json` y cambios en migraciones Alembic. | bloqueante |
| 2 | **Nunca tocar secrets.** Prohibido leer, copiar, mover o commitear `.env`, claves API, tokens, certificados. Si detectás un secret expuesto, alertá inmediatamente y no toques nada. | bloqueante |
| 3 | **Tablas de memoria sagradas.** `semantic_memory`, `episodic_memory`, `procedural_memory` no se modifican sin tests pasando y **2 aprobaciones humanas**. Idem para migraciones Alembic que las afecten. | bloqueante |
| 4 | **Datos de usuario nunca fuera del perímetro.** Prohibido enviar mensajes, memoria, metadata o cualquier dato a APIs externas (OpenAI, Anthropic, Google, Cohere, Mistral). Toda inferencia es on-prem. | bloqueante |
| 5 | **Cliente Supabase prohibido en el frontend.** En fase MVP, Supabase es solo Postgres gestionado. Prohibido `@supabase/supabase-js` en `apps/web/` o `apps/mobile/`. Prohibido Supabase Auth, Storage, Realtime, Edge Functions, RLS como autorización primaria. Todo dato pasa por FastAPI. Ver [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md). | bloqueante |
| 6 | **Conventional Commits en español imperativo.** Formato `tipo(scope): descripción`. Ejemplo: `feat(web): agregar modo bienestar`. Ver [`COMMITS.md`](./docs/conventions/COMMITS.md). | PR rechazado |
| 7 | **Commits atómicos.** Un commit = un cambio lógico. No mezclar refactor con feature ni feature con docs. | recomendado fuerte |
| 8 | **Scope obligatorio** para cambios en apps o packages (`feat(web):`, `fix(backend):`, etc.). Sin scope solo en cambios cross-cutting reales. | PR rechazado |
| 9 | **Rioplatense conversacional** en docs y contenido de usuario. Voseo, evitar peninsular. Nombres de variables y funciones en inglés; comentarios y docs en español. | review obligatorio |
| 10 | **Antes de tocar código nuevo**: leer este archivo → leer el `AGENTS.md` del app/package → leer los ADRs relevantes. Si no entendés algo, **preguntá**. | recomendado fuerte |

Reglas extendidas (15 más + landmines del scaffold): [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Routing LLM y memoria

| Modo | Modelo | Capas de memoria | Tools |
| --- | --- | --- | --- |
| productividad | Qwen 3.5-9B (agente) | semantic + episodic | calendar, reminders, memory |
| estudio | Gemma 4 26B-A4B | episodic + procedural | — |
| bienestar | Gemma 4 26B-A4B | procedural + semantic | — |
| vida | Gemma 4 26B-A4B | procedural | calendar (read) |
| memoria | Qwen 3.5-9B (agente) | las 3 capas | memory |

- **Gemma solo lee memoria.** No escribe, no llama tools.
- **Qwen lee y escribe.** Llama tools. Toda escritura va asíncrona vía Celery.
- **Único punto de entrada**: `apps/backend/app/llm/router.py`. No hay otra ruta válida al LLM.
- Razonamiento: [`ADR-002`](./docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md).

## Editing conventions — landmines aprendidas

Cosas que ya nos hicieron tropezar (o que sabemos que van a hacerlo). No las re-introduzcas.

| Landmine | Detalle corto |
| --- | --- |
| `.gitignore` con `models/` sin slash | Matchea cualquier `models/` del árbol y oculta `apps/backend/app/models/`. Mantener `/models/` y `/checkpoints/` anclados a root. |
| `tailwind.config.ts` en `apps/web` | Tailwind v4 es CSS-first. Tokens en `globals.css` con `@theme`; sources con `@source`. Si aparece el archivo, borralo. |
| NativeWind 4 sobre Tailwind 4 | NativeWind todavía corre sobre Tailwind 3. `apps/mobile/package.json` mantiene `tailwindcss ^3.4`. No subir hasta que NativeWind soporte. |
| Services con imports de framework | `apps/backend/app/services/` recibe deps por argumento; no importa de FastAPI ni de SQLAlchemy directo. Hace los services testeables sin levantar nada. |
| Escritura de memoria sincrónica | Toda escritura va vía Celery, **fuera del path de respuesta**. Si necesitás sincrónica, parar y discutir. |
| Zod divergente de Pydantic | Pydantic es fuente de verdad. Zod (`packages/shared-schemas/`) es mirror manual. Si divergen, corregir Zod en el mismo PR. |
| Completar `security.py` a medias | Las funciones de `core/security.py` están en `NotImplementedError` a propósito. Se cierra en un PR enfocado con tests end-to-end. |
| CI con `push`/`pull_request` antes de los lockfiles | CI hoy es solo `workflow_dispatch`. Reactivar `push`/`pull_request` recién cuando existan `pnpm-lock.yaml` y `apps/backend/uv.lock`. |

Detalle de cada landmine con código de bien/mal: [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Commit conventions

Conventional Commits en español imperativo. Tipo en inglés, descripción en español.

```text
feat(web): agregar layout del modo bienestar
fix(backend): corregir extracción episódica que duplicaba hechos
docs(architecture): agregar ADR-006 sobre LangGraph
refactor(memory): renombrar consolidator a memory-worker
chore(infra): actualizar version de Redis en compose
test(backend): cubrir consolidación de memoria episódica
```

Reglas duras:

- Tipos válidos: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `style`, `build`, `ci`, `revert`.
- Scope obligatorio para cambios en apps o packages. Sin scope solo en cambios cross-cutting reales.
- Imperativo, sin punto final.
- Cuerpo explica **por qué**, no qué (el diff ya dice qué).
- 72 columnas máximo por línea del cuerpo.
- `Co-Authored-By:` trailer cuando hay co-autor humano o IA.

Detalle y más ejemplos: [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md).

## Validation expectations

Correr según el tipo de cambio antes de abrir o actualizar PR.

| Tipo de cambio | Comando |
| --- | --- |
| **Cualquier PR** | `bash scripts/ynara-doctor.sh` (debe exit 0) |
| Backend (código) | `cd apps/backend && uv run ruff check . && uv run ruff format --check . && uv run pytest` |
| Frontend (código) | `pnpm biome check . && pnpm turbo run typecheck && pnpm turbo run test` |
| Migración Alembic | `cd apps/backend && uv run alembic check && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` |
| Toca tablas sagradas | Lo anterior + tests específicos + **2 aprobaciones humanas** |
| Solo docs | Verificar links internos no rotos |

## Health check — Ynara doctor

```bash
bash scripts/ynara-doctor.sh
# o:
make doctor
```

Valida en un solo comando: `.env.example` presentes, ningún `.env` real commiteado, sin `@supabase/supabase-js` en frontend (regla #5), sin imports de IA externa en backend (regla #4), `ynara.config.json` parseable, adapters apuntan a `AGENTS.md`, alerta si el PR toca tablas sagradas (regla #3), lockfiles trackeados si existen, y sin `tailwind.config.ts` en `apps/web`.

**Exit 0 obligatorio antes de cualquier PR.** Cuando configuremos `pre-commit install`, los hooks de `pre-push` lo van a invocar automáticamente.

## Adapters por herramienta

| Herramienta | Adapter (markdown) | Carpeta de comandos / agents |
| --- | --- | --- |
| Claude Code | [`CLAUDE.md`](./CLAUDE.md) | `.claude/` |
| OpenAI Codex | [`CODEX.md`](./CODEX.md) | `.codex/` |
| Gemini Code Assist | [`GEMINI.md`](./GEMINI.md) | `.gemini/` |

Cualquier adapter es solo puntero + atajos específicos de su IDE. Si un adapter dice algo distinto a este `AGENTS.md`, **gana este**.

## Cuando algo no esté claro

Pedir aclaración humana siempre es preferible a inventar. El proyecto está en fase temprana; muchas decisiones siguen abiertas (TODOs, placeholders, `NotImplementedError`). Si encontrás una ambigüedad, preguntá. Mejor que inventar y meter una decisión sin discusión.
