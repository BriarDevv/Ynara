# CODEX.md — Adapter para OpenAI Codex

> **La fuente canónica de las reglas del repo es [`AGENTS.md`](./AGENTS.md).**
> Este archivo solo contiene atajos y comportamientos específicos de
> Codex que complementan el contrato general.

## Antes de hacer cualquier cosa

1. Leer `AGENTS.md` y respetar las 10 reglas no negociables.
2. Si tu tarea toca un app específico, leer el `AGENTS.md` de ese app
   (`apps/web/AGENTS.md`, `apps/mobile/AGENTS.md`,
   `apps/backend/AGENTS.md`).
3. Si la tarea es arquitectónica, leer los ADRs en
   `docs/architecture/adrs/`.

## Comandos específicos de Codex

<!-- TODO: completar cuando armemos comandos propios -->

Los comandos locales viven en `.codex/commands/`. Cualquier agregado
requiere PR.

## Comportamientos Codex-specific

### Prohibido
- Modificar archivos sin pasar por la confirmación humana cuando
  apliquen las reglas #1 a #5 de `AGENTS.md`.
- Resolver merges sin entender los dos lados del cambio.

### Recomendado
- Para refactors grandes: dividir en commits chicos atómicos antes
  de proponer el PR.
- Antes de tocar el backend, leer `apps/backend/docs/MODELS.md` y
  `apps/backend/docs/ENDPOINTS.md` para entender qué ya existe.

## Tono

Rioplatense conversacional con el usuario; inglés solo para
identificadores de código.

## Adapters hermanos

- `CLAUDE.md` — adapter para Claude Code.
- `GEMINI.md` — adapter para Gemini Code Assist.
