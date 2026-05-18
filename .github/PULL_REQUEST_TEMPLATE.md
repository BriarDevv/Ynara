<!--
Template inspirado en los PRs del equipo (ej: #1, #2).
Borrá las secciones que no apliquen — la idea es contar el cambio,
no llenar campos.
-->

## Resumen

<!--
Qué cambia y por qué, en 2-3 líneas. Si el PR es parte de un plan o
sesión, linkear acá (issue, PR padre, archivo del plan).
-->

## Commits

<!--
Lista numerada de los commits atómicos del PR. Cada uno con el
mensaje en bold + 1 línea de contexto.

Ejemplo:
1. **`chore(deps): pinear next-auth a 5.0.0-beta.31 (ADR-006)`** —
   v5 sigue en beta. Pin exacto + ADR documentando la decisión.
2. **`feat(web): sistema visual base — tokens, fonts y primitives`** —
   tokens canónicos en globals.css, primitives Button/Card/YnaraMark.
-->

## Cambios mayores

<!--
Sub-secciones por área del cambio. Bullets con detalle, no prosa larga.

### Identidad visual
- ...

### Primitives
- ...
-->

## Verificación local

- [ ] `bash scripts/ynara-doctor.sh` verde
- [ ] Tests pasando (`pnpm test` o `uv run pytest` según scope)
- [ ] Lint verde (`pnpm biome check .` o `uv run ruff check .`)
- [ ] Typecheck verde (`pnpm typecheck`)

## Compliance con reglas no negociables

<!--
Marcar SOLO lo que aplica al PR. Si una regla no se toca, dejar sin
marcar o eliminar la línea. No marcar a la ligera — el bot de review
chequea esto contra el diff.
-->

- [ ] Sin secrets commiteados (regla #2)
- [ ] No toca tablas sagradas (regla #3) — o tiene 2 aprobaciones humanas confirmadas
- [ ] Sin imports de APIs externas de IA en backend (regla #4)
- [ ] Sin `@supabase/supabase-js` en frontend (regla #5)
- [ ] Conventional Commits en español, imperativo (regla #9)
- [ ] Si agregó / cambió deps: OK humano antes del install (regla #1)

## Conocido fuera de scope

<!--
Cosas que sabés que faltan o son sub-óptimas pero que no van en este
PR. Con razón. Ej: "biome.json root anidado bajo packages/config —
fix en PR separado con biome migrate --write".
-->

## Reviewer ask

<!--
Pedidos específicos por reviewer. No relleno — solo si querés foco en
algo. Si el PR es self-explanatory, omitir esta sección.

- **@MateoGs013**: validar X (sos CODEOWNER de Y).
- **@BriarDevv**: validar Z (foundations técnicas).
- **@querques20**: validar W (alineación con el prototipo).
-->

## Test plan

<!--
Pasos manuales para validar el cambio en el entorno objetivo.
Checkboxes para que el reviewer pueda confirmar.
-->

- [ ]

## Próximo PR

<!--
Si este PR es parte de una serie (sesión del plan, fase de migración),
qué viene después. Linkear el branch o el plan.
-->
