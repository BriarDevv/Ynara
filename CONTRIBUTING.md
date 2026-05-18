# CONTRIBUTING.md — Cómo contribuir a Ynara

> **Antes de nada**: leer [`AGENTS.md`](./AGENTS.md). Es el contrato
> del repo y aplica para humanos y para IAs.

## Flujo de trabajo

1. **Crear branch desde `main`**.
   - Naming: `feat/<scope>-<descripcion-corta>`,
     `fix/<scope>-<descripcion>`, `docs/<descripcion>`,
     `chore/<descripcion>`.
   - Ejemplo: `feat/web-modo-bienestar`,
     `fix/backend-extraccion-episodica`.

2. **Commits**: Conventional Commits en español, imperativo.
   - `feat(web): agregar modo bienestar`
   - `fix(backend): corregir extracción episódica`
   - `docs(architecture): agregar ADR-006`
   - `chore(infra): actualizar versión de Redis en compose`
   - `refactor(shared-types): renombrar UserMemory a MemoryRecord`
   - `test(backend): cubrir consolidación de memoria episódica`
   - Detalle completo en
     [`docs/conventions/COMMITS.md`](./docs/conventions/COMMITS.md).

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
   - El bot de review automática (Claude) va a postear un
     comentario con hallazgos. No bloquea el merge, pero conviene
     resolverlos antes de pedir review humana. Ver
     [`docs/operations/CLAUDE-REVIEW.md`](./docs/operations/CLAUDE-REVIEW.md).

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
