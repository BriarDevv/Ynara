# AGENTS.md — Contrato del repo Ynara

Ynara es un asistente personal adaptativo con IA, memoria propia y
arquitectura on-prem. Este archivo es la fuente canónica de las reglas
que debe respetar cualquier persona o agente que trabaje sobre el repo.

> Si sos una IA (Claude, Codex, Gemini, Cursor, Copilot, etc.):
> **leé este archivo primero, antes de tocar cualquier cosa**. Es el
> único contrato que tenés que respetar sin excepción.

## Golden Rule

Los archivos `.md` raíz (`AGENTS.md`, `CLAUDE.md`, `CODEX.md`,
`GEMINI.md`, `DESIGN.md`, `IDENTITY.md`, `README.md`, `SECURITY.md`,
`CONTRIBUTING.md`) y la carpeta `docs/` son la **fuente de verdad** del
proyecto.

Las carpetas `.claude/`, `.codex/`, `.gemini/` son **adapters** para
los distintos IDEs/CLIs de IA: nunca deben contener contenido propio,
solo punteros y atajos específicos de cada herramienta.

Si hay un conflicto entre lo que dice un adapter y lo que dice
`AGENTS.md` / `docs/`, gana la fuente canónica.

## Las 10 reglas no negociables

1. **Confirmación humana obligatoria** antes de:
   - `git commit`, `git push`, `git rebase`, `git tag`
   - `pnpm add`, `pnpm install`, `uv add`, `uv sync`
   - Cambios en archivos `.md` raíz
   - Cambios en `ynara.config.json`
   - Cambios en migraciones Alembic (`apps/backend/alembic/versions/`)
   - Severidad: **bloqueante**.

2. **Nunca tocar secrets**. Está prohibido leer, copiar, mover o
   commitear `.env`, claves API, tokens, certificados o cualquier
   credencial. Si detectás un secret expuesto en el código, alertá
   inmediatamente al humano y no toques nada.
   - Severidad: **bloqueante**.

3. **Las tablas de memoria son sagradas**. Nunca modificar
   `semantic_memory`, `episodic_memory`, `procedural_memory` (ni sus
   esquemas Pydantic / SQLAlchemy) sin tests pasando y review humano
   explícito. Cualquier migración Alembic que las toque requiere dos
   aprobaciones.
   - Severidad: **bloqueante**.

4. **Datos de usuario nunca salen del perímetro**. Está prohibido
   enviar datos de usuario (mensajes, memoria, audios, contactos) a
   APIs externas: OpenAI, Anthropic, Google, Cohere, Mistral, etc.
   Toda la inferencia es on-prem (vLLM / Ollama).
   - Severidad: **bloqueante**.

5. **Cliente Supabase prohibido en el frontend**. Durante la fase MVP,
   Supabase se usa **exclusivamente como Postgres gestionado**.
   Prohibido importar `@supabase/supabase-js` en `apps/web/` o
   `apps/mobile/`. Prohibido Supabase Auth, Storage, Realtime, Edge
   Functions, RLS como autorización primaria. Todo el acceso a datos
   pasa por la API de FastAPI.
   - Severidad: **bloqueante**.
   - Ver: `docs/architecture/adrs/ADR-005-supabase-mvp-postgres-selfhosted-v2.md`

6. **Conventional Commits en español, imperativo**. Formato:
   `tipo(scope): descripción`. Ejemplos: `feat(web): agregar modo
   bienestar`, `fix(backend): corregir extracción episódica`,
   `docs(architecture): agregar ADR-006`.
   - PR rechazado si no se cumple.

7. **Commits atómicos**. Un commit = un cambio lógico. No mezclar
   refactor con feature, ni feature con docs.
   - Recomendado fuerte.

8. **Scope obligatorio** para cambios en apps o packages:
   `feat(web):`, `fix(backend):`, `chore(mobile):`,
   `docs(architecture):`, `refactor(shared-types):`. Sin scope solo se
   permite en cambios cross-cutting reales.
   - PR rechazado si falta.

9. **Rioplatense conversacional** en todo el contenido orientado al
   usuario y en docs. Voseo, argentinismos cuando el contexto lo
   permite, evitar peninsular (vosotros, ordenador, vale, móvil por
   "celular"). Nombres de variables y funciones siempre en inglés;
   comentarios, docstrings y docs en español.
   - Review obligatorio.

10. **Antes de tocar código nuevo**:
    1. Leer este `AGENTS.md`.
    2. Leer el `README.md` y `AGENTS.md` del package o app específico.
    3. Leer los ADRs relevantes en `docs/architecture/adrs/`.
    4. Si no entendés algo, **preguntá**. Mejor preguntar que inventar.
    - Recomendado fuerte.

Las reglas extendidas (15 adicionales sobre estilo, arquitectura,
tooling y voz) viven en `docs/conventions/AI-GUIDELINES.md`.

## Stack (resumen)

| Capa | Tecnología |
|------|------------|
| Web | Next.js 16, TypeScript strict, Tailwind v4, shadcn/ui, GSAP, Lenis, TanStack Query v5, Zustand v5, Auth.js v5 |
| Mobile | Expo SDK 53+, Expo Router, NativeWind, TanStack Query v5, Zustand v5 |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Celery 5.4+, uv, Ruff |
| LLM | vLLM (prod), Ollama (dev), Unsloth + QLoRA, LlamaIndex, Mem0 OSS v2 |
| DB (MVP) | Supabase como Postgres 16 gestionado + pgvector, Redis (Upstash o Docker) |
| DB (V2) | Postgres 16 self-hosted + pgvector, Redis self-hosted |
| Monorepo | pnpm 10+, Turborepo 2.x, Biome 2.x |
| Deploy | Vercel (web), EAS (mobile), Cloudflare Tunnel + R2 (backend) |

## Read Next — según tu tarea

| Querés hacer... | Leé esto |
|-----------------|----------|
| Trabajar en el frontend web | `apps/web/AGENTS.md` + `DESIGN.md` |
| Trabajar en mobile | `apps/mobile/AGENTS.md` + `apps/mobile/EAS.md` |
| Trabajar en el backend | `apps/backend/AGENTS.md` + `apps/backend/docs/` |
| Agregar una tool al agente Qwen | `apps/backend/docs/TOOLS.md` + `skills/add-llm-tool/SKILL.md` |
| Agregar un modo nuevo | `docs/product/MODES.md` + `skills/add-new-mode/SKILL.md` |
| Tocar memoria | `docs/product/MEMORY.md` + `apps/backend/app/memory/` |
| Crear una migración | `apps/backend/docs/MIGRATIONS.md` |
| Crear un ADR | `docs/architecture/adrs/` + `skills/adr-create/SKILL.md` |
| Entender el tono | `docs/product/TONE-OF-VOICE.md` + `IDENTITY.md` |
| Deploy | `docs/operations/DEPLOY.md` + `docs/operations/RUNBOOK.md` |

## Adapters por herramienta

- **Claude Code** → `CLAUDE.md` y `.claude/`
- **OpenAI Codex** → `CODEX.md` y `.codex/`
- **Gemini Code Assist** → `GEMINI.md` y `.gemini/`

Todos apuntan a este archivo como fuente canónica.

## Cuando algo no esté claro

Pedir aclaración humana siempre es preferible a inventar. El proyecto
todavía está en fase temprana y muchas decisiones están abiertas. Si
ves un `TODO`, un placeholder, o algo ambiguo, **preguntá**.
