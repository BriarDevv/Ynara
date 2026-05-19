# CONTRIBUTING.md — Cómo contribuir a Ynara

> **Antes de nada**: leer [`AGENTS.md`](./AGENTS.md). Es el contrato
> del repo y aplica para humanos y para IAs.

## Flujo de trabajo

> **Regla del repo — `main` solo se actualiza vía PR mergeado en GitHub.**
>
> **Prohibido**, aunque haya OK humano para el comando individual:
>
> - `git push origin main` directo (sin pasar por PR).
> - `git merge <rama>` local hacia `main` + `git push` del resultado.
> - `git push --force` o cualquier force-push a `main`.
> - Borrar la rama `main` (`git push origin :main`,
>   `git branch -D main` seguido de un push, etc.).
>
> Esta regla complementa la regla #1 de
> [`AGENTS.md`](./AGENTS.md#las-10-reglas-no-negociables): los
> cambios pasan por revisión, CI, traza explícita y posibilidad
> de rollback antes de tocar producción. Branch protection en
> GitHub la hace cumplir técnicamente; si la protection no está
> habilitada todavía, la regla sigue vigente por convención del
> equipo. Para deploy de prod, ver
> [`docs/operations/DEPLOY.md`](./docs/operations/DEPLOY.md).

1. **Crear branch desde `main`**.
   - Naming: `feat/<scope>-<descripcion-corta>`,
     `fix/<scope>-<descripcion>`, `docs/<descripcion>`,
     `chore/<descripcion>`.
   - Ejemplo: `feat/web-modo-bienestar`,
     `fix/backend-extraccion-episodica`.
   - **Verificar HEAD antes de `git checkout -b`**: `git status` +
     `git log -1` deben mostrar que estás en `main` y que el SHA
     matchea `origin/main`. Si no, primero
     `git checkout main && git pull --rebase origin main`. Ver
     landmine "Ramas nuevas derivadas de un PR ajeno" en
     [`docs/conventions/AI-GUIDELINES.md`](./docs/conventions/AI-GUIDELINES.md).
   - **Sync con remote: rebase, no merge**. Usar
     `git pull --rebase origin main` siempre. Configuración global
     recomendada: `git config --global pull.rebase true`. Detalle
     en la sección "Sync con remote: usá rebase, no merge" de
     `AI-GUIDELINES.md`.

2. **Commits**: Conventional Commits en español, imperativo, y
   **atómicos** (un commit = un cambio lógico — regla #7 de
   `AGENTS.md`, bloqueante).
   - `feat(web): agregar modo bienestar`
   - `fix(backend): corregir extracción episódica`
   - `docs(architecture): agregar ADR-006`
   - `chore(infra): actualizar versión de Redis en compose`
   - `refactor(shared-types): renombrar UserMemory a MemoryRecord`
   - `test(backend): cubrir consolidación de memoria episódica`
   - **Cómo splitear PRs grandes en commits chicos** (workflow,
     triggers operativos, ejemplos bien/mal):
     [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md)
     sección "Commits atómicos". Lectura obligatoria antes de tu
     primer PR no trivial.
   - Trigger: si tu PR pasa de ~200 líneas o de 3 archivos en áreas
     distintas, parar y splitear antes de pushear.
   - Tablas sagradas (regla #3): commit propio aislado para que las
     2 aprobaciones humanas inspeccionen un commit específico.

3. **Tests**: antes de pedir review.
   - `pnpm test` en el root corre todo.
   - Por app: `pnpm --filter web test`, `pnpm --filter mobile test`,
     `cd apps/backend && uv run pytest`.

4. **Lint y format**:
   - JS/TS: `pnpm biome check --apply`.
   - Python: `cd apps/backend && uv run ruff check . && uv run ruff format .`.

5. **PR**:
   - Usar el template (`.github/PULL_REQUEST_TEMPLATE.md`). La
     estructura esperada:
     - **Resumen** — qué cambia y por qué, 2-3 líneas.
     - **Commits** — lista numerada de los commits atómicos del PR.
     - **Cambios mayores** — sub-secciones por área con bullets.
     - **Verificación local** — checklist de doctor, tests, lint,
       typecheck corridos antes del push.
     - **Compliance con reglas no negociables** — marcar SOLO lo
       que aplica al PR.
     - **Conocido fuera de scope** — limitaciones explícitas con
       razón.
     - **Reviewer ask** — pedidos específicos por reviewer (omitir
       si el PR es self-explanatory).
     - **Test plan** — pasos manuales para validar.
     - **Próximo PR** — si es parte de una serie, qué viene.
   - PR chico es PR bueno: target <500 líneas o <10 archivos. Si
     es más grande, considerá splitear por sesión.
   - Asignar al menos un CODEOWNER del path afectado.
   - Sin auto-merge.
   - CI verde antes de pedir review.
   - **Merge strategy: rebase merge.** Usar
     `gh pr merge <N> --rebase --delete-branch` (o el botón
     "Rebase and merge" en la UI). Los commits del PR se reaplican
     lineal sobre `main`, sin merge commit. Mantiene la regla #7
     (commits atómicos) y el grafo de `main` queda lineal. Branch
     protection rechaza merge commits explícitamente
     (`required_linear_history: true`).

## Code review

- Cualquier PR que toque migraciones o tablas de memoria requiere **2
  aprobaciones humanas**.
- Cualquier PR que toque archivos `.md` raíz, `ynara.config.json`, o
  `DESIGN.md` requiere aprobación de @MateoGs013.
- IAs pueden hacer pasadas de review (sub-agent `code-reviewer` /
  `verifier`), pero la aprobación final es humana.

## Tono y estilo

- Documentación en **rioplatense**.
- Código en **inglés** (variables, funciones, comentarios técnicos
  cortos), excepto docstrings que pueden ser bilingües si aporta.
- TS strict, Pydantic v2 strict.
- Archivos chicos: target menos de 300 líneas, refactor obligatorio
  si pasan de 500.
- Sin emojis en código ni en docs salvo que un humano lo pida
  explícitamente.

## Cambios arquitectónicos

Cualquier cambio que afecte:
- el stack (cambiar de Next.js a otra cosa, agregar otra DB, etc.),
- la arquitectura de modelos (cambiar el dual-model),
- la arquitectura de memoria,
- el deploy o la topología de infra,

requiere un **ADR nuevo** en `docs/architecture/adrs/` antes del PR de
implementación. Ver `skills/adr-create/SKILL.md`.

## Para IAs

- Leer `AGENTS.md` siempre antes de empezar.
- Respetar las 10 reglas no negociables.
- Pedir confirmación humana cuando aplica (regla #1).
- Si hay un `TODO` o ambigüedad, preguntar — no inventar.
- Tono rioplatense en chat, inglés solo en identificadores.
