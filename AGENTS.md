# AGENTS.md — Contrato del repo Ynara

> Contrato AI-neutral para trabajar en este repo. Cualquier agente IA
> (Claude Code, OpenAI Codex, Gemini Code Assist, Cursor, Copilot)
> **lee este archivo primero**. Los adapters específicos por herramienta
> viven en [`CLAUDE.md`](./CLAUDE.md), [`CODEX.md`](./CODEX.md),
> [`GEMINI.md`](./GEMINI.md) y solo contienen punteros + atajos: la
> fuente canónica es esta.

## Quickstart 30s

Ynara es un asistente personal adaptativo on-prem con memoria propia.
Stack: Next.js 16 (web) + Expo 53+ (mobile) + FastAPI + Pydantic v2 +
SQLAlchemy 2 async (backend) + vLLM con dual stack Gemma 4 26B-A4B
(conversacional) + Qwen 3.5-9B (agente) + Mem0 OSS v2 + Postgres 16 +
pgvector. **Reglas más críticas**: (1) OK humano antes de
commit/push/install/migraciones; (2) datos del usuario nunca fuera
del perímetro; (3) cliente Supabase prohibido en frontend; (4) tablas
de memoria sagradas (2 aprobaciones). **Antes de cada PR**:
`bash scripts/ynara-doctor.sh` debe `exit 0`.

## Golden rule

Los archivos `.md` raíz (este, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`,
`DESIGN.md`, `IDENTITY.md`, `README.md`, `SECURITY.md`,
`CONTRIBUTING.md`) y la carpeta `docs/` son **fuente de verdad**.

Las carpetas `.claude/`, `.codex/`, `.gemini/` son **adapters** para
los IDEs/CLIs de IA: solo punteros y atajos específicos de cada
herramienta. Si hay un conflicto entre adapter y fuente canónica,
gana la fuente canónica.

## Read Order

### Always first

1. Este archivo (`AGENTS.md`).
2. [`README.md`](./README.md).

### Then choose by task

| Tarea | Leer en este orden |
| --- | --- |
| Onboarding al repo | `README.md` → [`docs/README.md`](./docs/README.md) → [`docs/conventions/GLOSSARY.md`](./docs/conventions/GLOSSARY.md) |
| Agregar / modificar un modo | [`docs/product/MODES.md`](./docs/product/MODES.md) → [`ynara.config.json`](./ynara.config.json) → `apps/backend/app/llm/router.py` → [`skills/add-new-mode/SKILL.md`](./skills/add-new-mode/SKILL.md) |
| Agregar una tool al agente Qwen | [`apps/backend/docs/TOOLS.md`](./apps/backend/docs/TOOLS.md) → `apps/backend/app/llm/tools/` → [`skills/add-llm-tool/SKILL.md`](./skills/add-llm-tool/SKILL.md) |
| Tocar memoria (lectura) | [`docs/product/MEMORY.md`](./docs/product/MEMORY.md) → `apps/backend/app/memory/` (wrappers) |
| Tocar memoria (esquema o migración) | [`ADR-003`](./docs/architecture/adrs/ADR-003-mem0-vs-letta.md) → [`ADR-004`](./docs/architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md) → [`docs/MODELS.md`](./apps/backend/docs/MODELS.md) → [`docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md) → **2 aprobaciones humanas** |
| Endpoint HTTP nuevo | [`docs/ENDPOINTS.md`](./apps/backend/docs/ENDPOINTS.md) → `apps/backend/app/api/v1/` → `apps/backend/app/services/` → schema en `apps/backend/app/schemas/` |
| Modelo SQLAlchemy nuevo | [`docs/MODELS.md`](./apps/backend/docs/MODELS.md) → `apps/backend/app/models/` → migración Alembic con tests |
| Migración Alembic | [`docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md) → `apps/backend/alembic/env.py` → plantilla `script.py.mako` |
| Workflow Celery nuevo | `apps/backend/app/workflows/` → `apps/backend/app/workers/celery_app.py` |
| Cambio arquitectónico (stack, infra, deps mayores) | [`docs/architecture/adrs/`](./docs/architecture/adrs/) → [`skills/adr-create/SKILL.md`](./skills/adr-create/SKILL.md) → **ADR aprobado antes del PR de implementación** |
| Frontend web | [`apps/web/AGENTS.md`](./apps/web/AGENTS.md) → [`apps/web/README.md`](./apps/web/README.md) → [`DESIGN.md`](./DESIGN.md) (placeholder) → `apps/web/src/app/globals.css` |
| Mobile | [`apps/mobile/AGENTS.md`](./apps/mobile/AGENTS.md) → [`apps/mobile/EAS.md`](./apps/mobile/EAS.md) → `apps/mobile/app.json` |
| Migración Supabase → self-hosted | [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md) → [`docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`](./docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md) |
| Deploy o incidente | [`docs/operations/DEPLOY.md`](./docs/operations/DEPLOY.md) → [`docs/operations/RUNBOOK.md`](./docs/operations/RUNBOOK.md) |
| Entender la voz del producto | [`IDENTITY.md`](./IDENTITY.md) → [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md) → tono por modo en `MODES.md` |
| Convenciones de commits | [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) |
| Reglas extendidas (estilo, anti-patterns) | [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md) + [`docs/conventions/CODE-STYLE.md`](./docs/conventions/CODE-STYLE.md) |
| Crear un skill nuevo | [`skills/README.md`](./skills/README.md) → cualquier `skills/*/SKILL.md` como plantilla |
| Histórico / por qué se decidió X | [`docs/architecture/adrs/`](./docs/architecture/adrs/) (inmutables, ordenados por número) |

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

1. **Confirmación humana obligatoria** antes de:
   - `git commit`, `git push`, `git rebase`, `git tag`.
   - `pnpm add`, `pnpm install`, `uv add`, `uv sync`.
   - Cambios en archivos `.md` raíz.
   - Cambios en `ynara.config.json`.
   - Cambios en migraciones Alembic (`apps/backend/alembic/versions/`).
   - Severidad: **bloqueante**.

2. **Nunca tocar secrets.** Prohibido leer, copiar, mover o commitear
   `.env`, claves API, tokens, certificados. Si detectás un secret
   expuesto, alertá inmediatamente y no toques nada.
   - Severidad: **bloqueante**.

3. **Tablas de memoria sagradas.** `semantic_memory`, `episodic_memory`,
   `procedural_memory` no se modifican sin tests pasando y **2
   aprobaciones humanas**. Idem para migraciones Alembic que las
   afecten.
   - Severidad: **bloqueante**.

4. **Datos de usuario nunca fuera del perímetro.** Prohibido enviar
   mensajes, memoria, metadata o cualquier dato a APIs externas:
   OpenAI, Anthropic, Google, Cohere, Mistral, etc. Toda inferencia
   es on-prem (vLLM en prod, Ollama en dev).
   - Severidad: **bloqueante**.

5. **Cliente Supabase prohibido en el frontend.** En fase MVP Supabase
   se usa **solo como Postgres gestionado**. Prohibido importar
   `@supabase/supabase-js` en `apps/web/` o `apps/mobile/`. Prohibido
   Supabase Auth, Storage, Realtime, Edge Functions, RLS como
   autorización primaria. Todo dato pasa por la API de FastAPI.
   - Severidad: **bloqueante**.
   - Ver [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md).

6. **Conventional Commits en español imperativo.** Formato:
   `tipo(scope): descripción`. Ejemplos: `feat(web): agregar modo
   bienestar`, `fix(backend): corregir extracción episódica`.
   - PR rechazado si no se cumple. Ver [`COMMITS.md`](./docs/conventions/COMMITS.md).

7. **Commits atómicos.** Un commit = un cambio lógico. No mezclar
   refactor con feature, ni feature con docs.
   - Recomendado fuerte.

8. **Scope obligatorio** para cambios en apps o packages:
   `feat(web):`, `fix(backend):`, `chore(mobile):`,
   `docs(architecture):`, `refactor(shared-types):`. Sin scope solo
   en cambios cross-cutting reales.
   - PR rechazado si falta.

9. **Rioplatense conversacional** en todo el contenido orientado al
   usuario y en docs. Voseo, argentinismos cuando contexto lo
   permite, evitar peninsular (vosotros, ordenador, vale). Nombres
   de variables y funciones en inglés; comentarios, docstrings y
   docs en español.
   - Review obligatorio.

10. **Antes de tocar código nuevo**: leer este `AGENTS.md` → leer el
    `AGENTS.md` del app/package → leer los ADRs relevantes. Si no
    entendés algo, **preguntá**. Mejor preguntar que inventar.
    - Recomendado fuerte.

Reglas extendidas (15 más): [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

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
- **Único punto de entrada**: `apps/backend/app/llm/router.py`. No
  hay otra ruta válida al LLM.
- Razonamiento: [`ADR-002`](./docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md).

## Editing conventions — landmines aprendidas

Cosas que ya nos hicieron tropezar (o que sabemos que van a hacerlo).
No las re-introduzcas:

- **`/models/` y `/checkpoints/` en `.gitignore` están anclados a
  root.** Sin slash inicial, matchea cualquier carpeta `models` del
  árbol y oculta `apps/backend/app/models/` (módulo Python legítimo
  con los SQLAlchemy Base + mixins). Si tocás `.gitignore`, mantené el
  ancla.
- **Tailwind v4 es CSS-first.** No agregar `tailwind.config.ts` a
  `apps/web/`. Los tokens viven en `apps/web/src/app/globals.css`
  con `@theme`. Para escanear `packages/ui`, usar `@source` desde el
  CSS.
- **NativeWind 4 corre sobre Tailwind 3, no v4.**
  `apps/mobile/package.json` mantiene `tailwindcss ^3.4`. No subir
  a 4 hasta que NativeWind soporte.
- **Services en `apps/backend/app/services/` no importan de FastAPI
  ni de SQLAlchemy directamente.** Reciben dependencias por
  argumento. Esto los hace testeables sin framework.
- **Consolidación de memoria siempre async vía Celery.** Nunca en el
  path de respuesta al usuario. Si necesitás escribir memoria
  sincrónica, parar y discutir.
- **Schemas Pydantic son la fuente de verdad.** Los Zod de
  `packages/shared-schemas` son mirror manual. Si divergen, gana
  Pydantic; corregir Zod en el mismo PR.
- **`apps/backend/app/core/security.py` está en
  `NotImplementedError`.** Las funciones de JWT/bcrypt son esqueletos
  hasta que cerremos auth en un PR enfocado. No las uses; no las
  completes parcialmente.
- **CI corre solo manualmente (`workflow_dispatch`)** hasta que
  existan `pnpm-lock.yaml` y `apps/backend/uv.lock`. Cuando se corra
  `pnpm install` y `uv sync` por primera vez, reactivar `push` y
  `pull_request` en `.github/workflows/ci.yml`.

Detalle extendido + 15 reglas adicionales:
[`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Commit conventions

Conventional Commits en español imperativo. Tipo en inglés (estándar),
descripción en español:

```
feat(web): agregar layout del modo bienestar
fix(backend): corregir extracción episódica que duplicaba hechos
docs(architecture): agregar ADR-006 sobre LangGraph
refactor(memory): renombrar consolidator a memory-worker
chore(infra): actualizar version de Redis en compose
test(backend): cubrir consolidación de memoria episódica
```

Reglas duras:

- Tipos válidos: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`,
  `perf`, `style`, `build`, `ci`, `revert`.
- Scope obligatorio para cambios en apps o packages. Sin scope solo
  para cambios cross-cutting reales (cambiar pnpm major, etc.).
- Imperativo, sin punto final.
- Cuerpo explica **por qué**, no qué (el diff ya dice qué).
- 72 columnas máximo por línea del cuerpo.
- `Co-Authored-By:` trailer cuando hay co-autor humano o IA.

Detalle completo y más ejemplos:
[`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md).

## Validation expectations

Antes de abrir o actualizar un PR, correr según el tipo de cambio:

| Tipo de cambio | Comandos |
| --- | --- |
| **Cualquier PR** | `bash scripts/ynara-doctor.sh` (debe exit 0) |
| Backend (código) | `cd apps/backend && uv run ruff check . && uv run ruff format --check . && uv run pytest` |
| Frontend (código) | `pnpm biome check . && pnpm turbo run typecheck && pnpm turbo run test` |
| Migración Alembic | `cd apps/backend && uv run alembic check && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` |
| Toca tablas sagradas | Lo anterior + tests específicos de la capa + **2 aprobaciones humanas** |
| Solo docs | Verificar links internos no rotos |

## Health check — Ynara doctor

```bash
bash scripts/ynara-doctor.sh
# o:
make doctor
```

Valida en un solo comando:

- `.env.example` presentes en root + cada app.
- Ningún `.env` real commiteado.
- Sin import de `@supabase/supabase-js` en `apps/web` ni `apps/mobile`
  (regla #5).
- Sin imports de `openai`, `anthropic`, `google.generativeai`,
  `cohere` en `apps/backend/app` (regla #4).
- `ynara.config.json` parseable.
- Adapters CLAUDE/CODEX/GEMINI referencian `AGENTS.md`.
- Alerta si el PR toca tablas sagradas (regla #3).
- Lockfiles trackeados si existen.

**Exit 0 obligatorio antes de cualquier PR.** Cuando configuremos
`pre-commit install`, los hooks de `pre-push` lo van a invocar
automáticamente.

## Adapters por herramienta

| Herramienta | Adapter (markdown) | Carpeta de comandos / agents |
| --- | --- | --- |
| Claude Code | [`CLAUDE.md`](./CLAUDE.md) | `.claude/` |
| OpenAI Codex | [`CODEX.md`](./CODEX.md) | `.codex/` |
| Gemini Code Assist | [`GEMINI.md`](./GEMINI.md) | `.gemini/` |

Cualquier adapter es solo puntero + atajos específicos de su IDE.
Si un adapter dice algo distinto a este `AGENTS.md`, **gana este**.

## Cuando algo no esté claro

Pedir aclaración humana siempre es preferible a inventar. El proyecto
está en fase temprana; muchas decisiones siguen abiertas (TODOs,
placeholders, `NotImplementedError`). Si encontrás una ambigüedad,
preguntá. Mejor que inventar y meter una decisión sin discusión.
