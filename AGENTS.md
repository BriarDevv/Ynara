# AGENTS.md — Contrato del repo Ynara

> Contrato AI-neutral para trabajar en este repo. Cualquier agente IA (Claude Code, OpenAI Codex, Gemini Code Assist, Cursor, Copilot) **lee este archivo primero**. Los adapters específicos por herramienta viven en [`CLAUDE.md`](./CLAUDE.md), [`CODEX.md`](./CODEX.md), [`GEMINI.md`](./GEMINI.md) y solo contienen punteros + atajos: la fuente canónica es esta.

## Quickstart 30s

**Qué es Ynara**: asistente personal adaptativo on-prem con memoria propia.

**Stack**: Next.js 16 (web) + Expo 53+ (mobile) + FastAPI + Pydantic v2 + SQLAlchemy 2 async (backend) + vLLM con dual stack Gemma 4 26B-A4B (conversacional) + Qwen 3.5-9B (agente) + memoria in-house (3 stores semantic/episodic/procedural, AES-256-GCM per-user — ADR-010) + Postgres 16 + pgvector.

**Reglas más críticas**:

1. OK humano antes de commit / push / install / migraciones.
2. Datos del usuario nunca fuera del perímetro.
3. Cliente Supabase prohibido en frontend.
4. Tablas sagradas: memoria + `audit_log` (1 aprobación humana + tests).

**Antes de cada PR**: `bash scripts/ynara-doctor.sh` debe `exit 0`.

## Golden rule

Los archivos `.md` raíz (este, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, `DESIGN.md`, `IDENTITY.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`) y la carpeta `docs/` son **fuente de verdad**.

Las carpetas `.claude/`, `.codex/`, `.gemini/` son **adapters** para los IDEs/CLIs de IA: solo punteros y atajos específicos de cada herramienta. Si hay un conflicto entre adapter y fuente canónica, gana la fuente canónica.

## Read Order

### Always first (obligatorio antes de cualquier PR)

1. Este archivo (`AGENTS.md`).
2. [`README.md`](./README.md).
3. [`CONTRIBUTING.md`](./CONTRIBUTING.md) — flujo de trabajo, branches, commits, PR, review, merge strategy (rebase merge). Es la guía operativa diaria del repo.
4. [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) — formato de commits + cómo splitear en atómicos (regla #7 es bloqueante).

### Then choose by task

Para tareas con un solo archivo, va inline. Para tareas con múltiples pasos, cada paso es un item de la lista numerada.

**Onboarding al repo**

1. [`README.md`](./README.md)
2. [`docs/README.md`](./docs/README.md)
3. [`docs/conventions/GLOSSARY.md`](./docs/conventions/GLOSSARY.md)

**Agregar o modificar un modo**

1. [`docs/product/MODES.md`](./docs/product/MODES.md)
2. [`ynara.config.json`](./ynara.config.json)
3. `apps/backend/app/llm/router.py`
4. [`skills/add-new-mode/SKILL.md`](./skills/add-new-mode/SKILL.md)

**Agregar una tool al agente Qwen**

1. [`apps/backend/docs/TOOLS.md`](./apps/backend/docs/TOOLS.md)
2. `apps/backend/app/llm/tools/`
3. [`skills/add-llm-tool/SKILL.md`](./skills/add-llm-tool/SKILL.md)

**Tocar memoria (lectura)**

1. [`docs/product/MEMORY.md`](./docs/product/MEMORY.md)
2. `apps/backend/app/memory/` (wrappers)

**Tocar memoria (esquema o migración)**

1. [`ADR-010`](./docs/architecture/adrs/ADR-010-memory-architecture-v2.md) — arquitectura vigente (supersede ADR-003)
2. [`ADR-003`](./docs/architecture/adrs/ADR-003-mem0-vs-letta.md) — histórico
3. [`ADR-004`](./docs/architecture/adrs/ADR-004-postgres-pgvector-vs-pinecone.md)
4. [`apps/backend/docs/MODELS.md`](./apps/backend/docs/MODELS.md)
5. [`apps/backend/docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md)
6. **1 aprobación humana obligatoria** (regla #3).

**Endpoint HTTP nuevo**

1. [`apps/backend/docs/ENDPOINTS.md`](./apps/backend/docs/ENDPOINTS.md)
2. `apps/backend/app/api/v1/`
3. `apps/backend/app/services/`
4. Schema en `apps/backend/app/schemas/`

**Modelo SQLAlchemy nuevo**

1. [`apps/backend/docs/MODELS.md`](./apps/backend/docs/MODELS.md)
2. `apps/backend/app/models/`
3. Migración Alembic con tests.

**Migración Alembic**

1. [`apps/backend/docs/MIGRATIONS.md`](./apps/backend/docs/MIGRATIONS.md)
2. `apps/backend/alembic/env.py`
3. Plantilla `apps/backend/alembic/script.py.mako`

**Workflow Celery nuevo**

1. `apps/backend/app/workflows/`
2. `apps/backend/app/workers/celery_app.py`

**Cambio arquitectónico (stack, infra, deps mayores)**

1. [`docs/architecture/adrs/`](./docs/architecture/adrs/)
2. [`skills/adr-create/SKILL.md`](./skills/adr-create/SKILL.md)
3. **ADR aprobado antes del PR de implementación.**

**Frontend web**

1. [`apps/web/AGENTS.md`](./apps/web/AGENTS.md)
2. [`apps/web/README.md`](./apps/web/README.md)
3. [`DESIGN.md`](./DESIGN.md) (placeholder)
4. `apps/web/src/app/globals.css`

**Mobile**

1. [`apps/mobile/AGENTS.md`](./apps/mobile/AGENTS.md)
2. [`apps/mobile/EAS.md`](./apps/mobile/EAS.md)
3. `apps/mobile/app.json`

**Migración Supabase → self-hosted**

1. [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md)
2. [`docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md`](./docs/operations/MIGRATION-SUPABASE-TO-SELFHOSTED.md)

**Deploy o incidente**

1. [`docs/operations/DEPLOY.md`](./docs/operations/DEPLOY.md)
2. [`docs/operations/RUNBOOK.md`](./docs/operations/RUNBOOK.md)

**Entender la voz del producto**

1. [`IDENTITY.md`](./IDENTITY.md)
2. [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md)
3. Tono por modo en [`docs/product/MODES.md`](./docs/product/MODES.md).

**Antes de tu primer PR** (humano o IA)

1. [`CONTRIBUTING.md`](./CONTRIBUTING.md) — flujo de trabajo, branches, review, tono.
2. [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) — formato de commits.
3. `bash scripts/ynara-doctor.sh` — debe salir con `exit 0`.

**Review un PR** (humano o IA)

1. [`skills/pr-review/SKILL.md`](./skills/pr-review/SKILL.md) — workflow completo: setup, verificaciones mecánicas, análisis cualitativo, estructura del comentario.
2. Invocación: `/pr-review <PR_NUMBER>` desde Claude Code (ver [`.claude/commands/pr-review.md`](./.claude/commands/pr-review.md)).
3. Output: un solo comentario vía `gh pr comment`. No mergear, no aprobar formalmente.

**Tareas con un solo archivo**

- **Convenciones de commits** — [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md)
- **Reglas extendidas (estilo, anti-patterns)** — [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md) + [`docs/conventions/CODE-STYLE.md`](./docs/conventions/CODE-STYLE.md)
- **Cómo contribuir (humano)** — [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- **Política de seguridad** — [`SECURITY.md`](./SECURITY.md)
- **Crear un skill nuevo** — [`skills/README.md`](./skills/README.md)
- **Histórico o por qué se decidió X** — [`docs/architecture/adrs/`](./docs/architecture/adrs/) (inmutables, ordenados por número)

## Repo Map

| Path | Por qué te importa |
| --- | --- |
| `AGENTS.md` | Este archivo — contrato del repo, leer primero |
| `CLAUDE.md` / `CODEX.md` / `GEMINI.md` | Adapters por IDE — solo punteros, sin contenido propio |
| `IDENTITY.md` | 4 pilares de marca + voz: qué es Ynara y qué no es |
| `DESIGN.md` | Sistema visual — placeholder hasta aprobación del equipo |
| `CONTRIBUTING.md` | Flujo de trabajo para humanos: branches, PRs, review, tono |
| `SECURITY.md` | Política de seguridad, reporte de vulnerabilidades, principios |
| `ynara.config.json` | Configuración canónica: 5 modos, 2 modelos, capas de memoria, fase de infra |
| `apps/web/` | Next.js 16 + Tailwind v4 CSS-first (sin `tailwind.config.ts`) + shadcn/ui |
| `apps/mobile/` | Expo 53+ + Expo Router + NativeWind (todavía sobre Tailwind 3) |
| `apps/backend/app/api/v1/` | Rutas HTTP, un módulo por dominio |
| `apps/backend/app/core/` | Settings, security (JWT implementado), deps de FastAPI |
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
| `docs/architecture/adrs/` | 10 ADRs inmutables (ADR-001 a ADR-010). Cambio arquitectónico nuevo = ADR nuevo |
| `docs/conventions/AI-GUIDELINES.md` | 15 reglas extendidas + landmines aprendidas |
| `infra/vllm/` | `start-vllm.sh` para Gemma + Qwen en la RTX 4080 |
| `infra/docker/` | docker-compose dev (solo Redis) y prod |
| `skills/*/SKILL.md` | 6 procedimientos reutilizables para humanos e IAs |
| `.claude/commands/` | Slash commands locales (ej: `/pr-review`). Adapter Claude Code |
| `scripts/ynara-doctor.sh` | Validaciones pre-PR — exit 0 obligatorio |

## Las 10 reglas no negociables

1. **Confirmación humana** antes de `git commit`, `git push`, `git rebase`, `git tag`, `pnpm add`, `pnpm install`, `uv add`, `uv sync`, cambios en `.md` raíz, cambios en `ynara.config.json` y cambios en migraciones Alembic. **Toda actualización de `main` ocurre exclusivamente vía PR mergeado en GitHub** — prohibido `git push origin main` directo, `git merge` local hacia `main` y su push, force-push a `main`, o borrar `main`, aunque haya OK humano para los comandos individuales. Flujo completo en [`CONTRIBUTING.md`](./CONTRIBUTING.md#flujo-de-trabajo). **Severidad: bloqueante.**

2. **Nunca tocar secrets.** Prohibido leer, copiar, mover o commitear `.env`, claves API, tokens, certificados. Si detectás un secret expuesto, alertá inmediatamente y no toques nada. **Severidad: bloqueante.**

3. **Tablas sagradas.** Las tablas de memoria (`semantic_memory`, `episodic_memory`, `procedural_memory`) y el audit trail inmutable (`audit_log`) no se modifican sin tests pasando y **1 aprobación humana explícita** (review formal aprobada en el PR, no solo el OK del operador que abrió el PR). Cubre sus modelos (`app/models/{memory,audit}.py`), schemas (`app/schemas/{memory,audit}.py`), wrappers (`app/memory/`) y las migraciones Alembic que las afecten. **Severidad: bloqueante.**

4. **Datos de usuario nunca fuera del perímetro.** Prohibido enviar mensajes, memoria, metadata o cualquier dato a APIs externas (OpenAI, Anthropic, Google, Cohere, Mistral). Toda inferencia es on-prem (vLLM en prod, Ollama en dev). **Severidad: bloqueante.**

5. **Cliente Supabase prohibido en el frontend.** En fase MVP, Supabase es solo Postgres gestionado. Prohibido `@supabase/supabase-js` en `apps/web/` o `apps/mobile/`. Prohibido Supabase Auth, Storage, Realtime, Edge Functions, RLS como autorización primaria. Todo dato pasa por FastAPI. **Severidad: bloqueante.** Ver [`ADR-005`](./docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md).

6. **Conventional Commits en español.** Formato `tipo(scope): descripción`. La descripción va en **imperativo** (`agregar`, `corregir`, `actualizar`) **o noun-phrase** que nombra el artefacto agregado (`modelo SQLAlchemy User`, `schemas Pydantic de auth`): cualquiera de las dos es válida, incluso mezcladas en un mismo PR si cada commit es coherente con su cambio. **Nunca gerundio** (`agregando`) **ni pasado** (`agregado`). Ejemplo: `feat(web): agregar modo bienestar`. **PR rechazado si no se cumple.** Ver [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md).

7. **Commits atómicos.** Un commit = un cambio lógico. No mezclar refactor con feature ni feature con docs. Si tu PR tiene más de ~200 líneas o toca más de 3 archivos de áreas distintas, **splitealo en commits chicos antes de pushear** — uno por cambio lógico. Tablas sagradas (regla #3) siempre en commit propio para que la aprobación humana de la regla #3 tenga un commit específico a inspeccionar. Detalle en [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md). **Severidad: bloqueante. PR rechazado si llega como commit monolítico.**

8. **Scope obligatorio** para cambios en apps o packages (`feat(web):`, `fix(backend):`, etc.). Sin scope solo en cambios cross-cutting reales. **PR rechazado si falta.**

9. **Rioplatense conversacional** en docs y contenido de usuario. Voseo, evitar peninsular (vosotros, ordenador, vale). Nombres de variables y funciones en inglés; comentarios y docs en español. **Review obligatorio.**

10. **Antes de tocar código nuevo**: leer este archivo, después el `AGENTS.md` del app/package, después los ADRs relevantes. Si no entendés algo, **preguntá**. Mejor preguntar que inventar. **Recomendado fuerte.**

Reglas extendidas (15 más + landmines del scaffold): [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Routing LLM y memoria

| Modo | Modelo | Capas de memoria | Tools |
| --- | --- | --- | --- |
| productividad | Qwen 3.5-9B (agente) | semantic + episodic | calendar, reminder, memory |
| estudio | Gemma 4 26B-A4B | episodic + procedural | — |
| bienestar | Gemma 4 26B-A4B | procedural + semantic | — |
| vida | Gemma 4 26B-A4B | procedural | — |
| memoria | Qwen 3.5-9B (agente) | las 3 capas | memory |

- **Gemma solo lee memoria.** No escribe, no llama tools.
- **Qwen lee y escribe.** Llama tools. Toda escritura va asíncrona vía Celery.
- **Único punto de entrada**: `apps/backend/app/llm/router.py`. No hay otra ruta válida al LLM.
- Razonamiento: [`ADR-002`](./docs/architecture/adrs/ADR-002-gemma-qwen-dual-stack.md).

## Editing conventions — landmines aprendidas

Cosas que ya nos hicieron tropezar (o que sabemos que van a hacerlo). No las re-introduzcas.

**`.gitignore` con `models/` sin slash inicial.** Matchea cualquier carpeta `models/` del árbol y oculta `apps/backend/app/models/` (módulo Python legítimo). Mantener `/models/` y `/checkpoints/` anclados a root.

**`tailwind.config.ts` en `apps/web`.** Tailwind v4 es CSS-first. Los tokens viven en `apps/web/src/app/globals.css` con `@theme`; las sources extra con `@source`. Si aparece el archivo, borralo.

**NativeWind 4 sobre Tailwind 4.** NativeWind todavía corre sobre Tailwind 3. `apps/mobile/package.json` mantiene `tailwindcss ^3.4`. No subir hasta que NativeWind soporte v4.

**Services con imports de framework.** `apps/backend/app/services/` recibe deps por argumento; no importa de FastAPI ni de SQLAlchemy directo. Esto los hace testeables sin levantar nada.

**Escritura de memoria sincrónica.** Toda escritura va vía Celery, **fuera del path de respuesta** al usuario. Si necesitás sincrónica, parar y discutir.

**Zod divergente de Pydantic.** Pydantic es fuente de verdad. Zod (`packages/shared-schemas/`) es mirror manual. Si divergen, corregir Zod en el mismo PR.

**`core/security.py` está implementado.** JWT/bcrypt completos (`create_access_token`, `verify_access_token`, `create_refresh_token`, `verify_token`, `hash_password`, `verify_password`). Los endpoints `/v1/auth/register`, `/v1/auth/token`, `/v1/auth/me`, `/v1/auth/refresh` y `/v1/auth/logout` están activos. `refresh` y `logout` se implementaron en #63: refresh single-use (rota el `jti` consumido), logout vía blocklist Redis por `jti`, rate-limit en token/register, todo sobre el singleton `app.state.redis` (con fail-open si Redis cae).

**CI con `push`/`pull_request` antes de los lockfiles.** CI hoy es solo `workflow_dispatch`. Reactivar `push`/`pull_request` recién cuando existan `pnpm-lock.yaml` y `apps/backend/uv.lock`.

**Crear ramas nuevas sin verificar la base.** `git checkout -b nueva-rama` ramifica desde HEAD actual, no desde `main` automáticamente. Si recién hiciste `gh pr checkout <N>` o `git fetch origin pull/<N>/head:<rama>` para revisar un PR ajeno y no volviste a `main`, la rama nueva hereda los commits de ese PR. Cuando esa rama nueva se mergea con fast-forward, GitHub arrastra los commits ajenos a `main` por inercia (incident PR #13 — los commits de PR #3 y PR #9 entraron a `main` sin click de merge real). **Antes de cualquier `git checkout -b`, correr `bash scripts/ynara-doctor.sh`** (check 10/10 valida que la rama actual deriva del tip de `origin/main`). Si no, primero `git checkout main && git pull --ff-only`.

Detalle de cada landmine con código de bien/mal: [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).

## Commit conventions

Conventional Commits en español. Tipo en inglés; descripción en español, imperativa o noun-phrase del artefacto (ver regla #6).

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
- Imperativo o noun-phrase del artefacto, sin gerundio ni pasado, sin punto final (regla #6).
- Cuerpo explica **por qué**, no qué (el diff ya dice qué).
- 72 columnas máximo por línea del cuerpo.
- `Co-Authored-By:` trailer cuando hay co-autor humano o IA.

Detalle y más ejemplos: [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md).

## Validation expectations

Correr según el tipo de cambio antes de abrir o actualizar PR.

**Cualquier PR** (siempre):

```bash
bash scripts/ynara-doctor.sh
# debe exit 0
```

**Backend (código)**:

```bash
cd apps/backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

**Frontend (código)**:

```bash
pnpm biome check .
pnpm turbo run typecheck
pnpm turbo run test
```

**Migración Alembic**:

```bash
cd apps/backend
uv run alembic check
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

**Toca tablas sagradas**: lo anterior + tests específicos de la capa + **1 aprobación humana explícita** (regla #3).

**Solo docs**: verificar que los links internos no estén rotos.

## Health check — Ynara doctor

```bash
bash scripts/ynara-doctor.sh
# o:
make doctor
```

Valida en un solo comando:

- `.env.example` presentes en root y en cada app.
- Ningún `.env` real commiteado.
- Sin `@supabase/supabase-js` en `apps/web` ni `apps/mobile` (regla #5).
- Sin imports de IA externa en `apps/backend/app` (regla #4).
- `ynara.config.json` parseable.
- Adapters CLAUDE / CODEX / GEMINI referencian `AGENTS.md`.
- Alerta si el PR toca tablas sagradas (regla #3).
- Lockfiles trackeados si existen.
- Sin `tailwind.config.ts` en `apps/web` (Tailwind v4 es CSS-first).

**Exit 0 obligatorio antes de cualquier PR.** Cuando configuremos `pre-commit install`, los hooks de `pre-push` lo van a invocar automáticamente.

## Adapters por herramienta

| Herramienta | Adapter | Carpeta |
| --- | --- | --- |
| Claude Code | [`CLAUDE.md`](./CLAUDE.md) | `.claude/` |
| OpenAI Codex | [`CODEX.md`](./CODEX.md) | `.codex/` |
| Gemini Code Assist | [`GEMINI.md`](./GEMINI.md) | `.gemini/` |

Cualquier adapter es solo puntero + atajos específicos de su IDE. Si un adapter dice algo distinto a este `AGENTS.md`, **gana este**.

## Cuando algo no esté claro

Pedir aclaración humana siempre es preferible a inventar. El proyecto está en fase temprana; muchas decisiones siguen abiertas (TODOs, placeholders, `NotImplementedError`). Si encontrás una ambigüedad, preguntá. Mejor que inventar y meter una decisión sin discusión.
