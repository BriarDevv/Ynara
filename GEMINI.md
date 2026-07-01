# GEMINI.md — Adapter para Gemini Code Assist

> **La fuente canónica de las reglas del repo es [`AGENTS.md`](./AGENTS.md).**
> Este archivo solo contiene atajos y comportamientos específicos de
> Gemini que complementan el contrato general.

## Antes de hacer cualquier cosa

1. Leer `AGENTS.md` y respetar las 10 reglas no negociables.
2. Leer [`CONTRIBUTING.md`](./CONTRIBUTING.md) y
   [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md) —
   flujo operativo + cómo splitear commits en atómicos.
   **Obligatorio**, no opcional.
3. Si tu tarea toca un app específico, leer el `AGENTS.md` de ese app
   (`apps/web/AGENTS.md`, `apps/mobile/AGENTS.md`,
   `apps/backend/AGENTS.md`, `apps/admin/AGENTS.md`,
   `apps/landing/AGENTS.md`).
4. Si la tarea es arquitectónica, leer los ADRs en
   `docs/architecture/adrs/`.

## Comandos específicos de Gemini

Los comandos locales viven en `.gemini/commands/` (hoy vacío salvo
`.gitkeep`). Cualquier agregado requiere PR. El único workflow de review
del repo está en [`skills/pr-review/SKILL.md`](./skills/pr-review/SKILL.md)
(en Claude Code se invoca con `/pr-review`).

## Comportamientos Gemini-specific

### Prohibido
- Modificar archivos sin pasar por la confirmación humana cuando
  apliquen las reglas #1 a #5 de `AGENTS.md`.
- Generar código que dependa de servicios de Google (Vertex AI,
  Gemini API, Firebase Auth) en el path de producción de Ynara: regla
  #4 prohíbe enviar datos de usuario a APIs externas.

### Recomendado
- Cuando explices código existente, citar el archivo y la línea
  (`file_path:line_number`) para que el humano pueda navegar rápido.

## Tono

Rioplatense conversacional con el usuario; inglés solo para
identificadores de código.

## Adapters hermanos

- `CLAUDE.md` — adapter para Claude Code.
- `CODEX.md` — adapter para OpenAI Codex.
