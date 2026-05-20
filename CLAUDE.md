# CLAUDE.md — Adapter para Claude Code

> **La fuente canónica de las reglas del repo es [`AGENTS.md`](./AGENTS.md).**
> Este archivo solo contiene atajos y comportamientos específicos de
> Claude Code que complementan el contrato general.

## Antes de hacer cualquier cosa

1. Leer `AGENTS.md` y respetar las 10 reglas no negociables.
2. Leer [`CONTRIBUTING.md`](./CONTRIBUTING.md) y
   [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) —
   flujo operativo + cómo splitear commits en atómicos.
   **Obligatorio**, no opcional.
3. Si tu tarea toca un app específico, leer el `AGENTS.md` de ese app
   (`apps/web/AGENTS.md`, `apps/mobile/AGENTS.md`,
   `apps/backend/AGENTS.md`).
4. Si la tarea es arquitectónica, leer los ADRs en
   `docs/architecture/adrs/`.

## Slash commands específicos de Claude Code

<!-- TODO: completar a medida que definamos comandos del equipo -->

Los slash commands locales viven en `.claude/commands/`. Cualquier
agregado requiere PR.

- `/init` — usar el comando nativo para refrescar memoria de proyecto.
- `/review` — review de PR antes de pedir review humano.
- `/security-review` — pasada de seguridad en cambios pendientes.

## Sub-agents específicos

<!-- TODO: completar cuando definamos sub-agents propios -->

Los sub-agents personalizados viven en `.claude/agents/`. Por ahora
usar los sub-agents nativos (`explore`, `executor`, `verifier`,
`code-reviewer`, `tracer`, etc.) según corresponda.

## Comportamientos Claude-specific

### Prohibido
- Usar `--dangerously-skip-permissions`. Siempre operar bajo el modo
  de permisos del usuario, especialmente para cambios en migraciones
  Alembic, archivos `.env`, y archivos `.md` raíz.
- Hacer `git commit` o `git push` sin confirmación humana explícita
  (regla #1 de `AGENTS.md`).
- Pushear directo a `main`, mergear local hacia `main`, o
  force-pushear a `main`. Toda actualización de `main` va por PR
  mergeado en GitHub (regla #1 ampliada en `AGENTS.md`; flujo
  completo en [`CONTRIBUTING.md`](./CONTRIBUTING.md#flujo-de-trabajo)).
- Tocar `apps/backend/app/memory/` o `apps/backend/alembic/versions/`
  sin 1 aprobación humana explícita en el PR (regla #3).
- Auto-aprobarte en el mismo contexto: la pasada de review siempre
  va en un agente separado (`code-reviewer` o `verifier`).

### Recomendado
- Para tareas complejas: planificar primero con un sub-agent
  `planner` o `architect`, después delegar la ejecución a `executor`.
- Para búsquedas amplias en el repo: usar el sub-agent `explore`
  antes de empezar a editar.
- Mantener commits chicos y atómicos; agrupar cambios solo si tienen
  un mismo "porqué".
- Cuando pides confirmación humana, explicar **qué** vas a hacer y
  **por qué**, no solo el comando.

## Tono

Rioplatense conversacional cuando hables con el usuario en chat.
Inglés técnico para nombres de variables, funciones, ramas y commits
(el sufijo en inglés del Conventional Commit), pero el cuerpo del
mensaje en español.

## Adapters hermanos

- `CODEX.md` — adapter para OpenAI Codex.
- `GEMINI.md` — adapter para Gemini Code Assist.

Todos apuntan a `AGENTS.md` como fuente canónica.
