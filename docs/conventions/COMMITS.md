# COMMITS.md — Conventional Commits en español

Conventional Commits adaptado: tipo en inglés (estándar global), pero
la descripción en español, imperativo, sin punto final.

## Formato

```
<tipo>(<scope>): <descripción imperativa>

[body opcional, multi-línea, contexto y porqué]

[footer opcional: refs a issues, breaking changes]
```

## Tipos

| Tipo | Para qué |
|------|----------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `refactor` | Cambio interno sin afectar comportamiento |
| `docs` | Solo documentación |
| `chore` | Tooling, configs, deps |
| `test` | Agregar o corregir tests |
| `perf` | Mejora de performance |
| `style` | Cambios de estilo/format que no afectan semántica |
| `build` | Cambios en build system o deps de build |
| `ci` | Cambios en pipelines CI/CD |
| `revert` | Revertir un commit anterior |

## Scopes válidos

- `web` — `apps/web/`
- `mobile` — `apps/mobile/`
- `backend` — `apps/backend/`
- `shared-types` / `shared-schemas` / `ui` / `config` — packages
- `architecture` / `product` / `operations` / `conventions` — docs
- `infra` — `infra/`
- `llm` — capa LLM dentro de backend
- `memory` — capa de memoria dentro de backend
- `tools` — tools del agente

Sin scope solo para cambios cross-cutting reales (ej: cambiar
`pnpm` major en el monorepo entero).

## Ejemplos

Buenos:
- `feat(web): agregar layout base del modo bienestar`
- `fix(backend): corregir extracción episódica que duplicaba hechos`
- `docs(architecture): agregar ADR-006 sobre LangGraph`
- `refactor(memory): renombrar consolidator a memory-worker`
- `chore: actualizar pnpm a 10.1`
- `test(backend): cubrir caso de memoria vacía al iniciar sesión`

Malos:
- `Update files` (sin tipo, sin descripción)
- `feat: stuff` (sin scope, descripción inútil)
- `Fix: Bug in chat` (mayúsculas, no imperativo, no español)
- `feat(web): added new component.` (pasado + punto final)

## Body

Explicar **por qué**, no qué (eso ya está en el diff). 72 columnas
máximo por línea.

```
feat(backend): agregar deduplicación de hechos semánticos

Mem0 default permite duplicados con threshold muy laxo. Subimos el
threshold a 0.92 y agregamos un test que evita la regresión que
vimos en el incident del 2026-04-12.
```

## Breaking changes

Agregar `!` después del tipo + footer `BREAKING CHANGE:`:

```
feat(backend)!: cambiar esquema de procedural_memory

BREAKING CHANGE: la tabla procedural_memory ahora usa JSONB en vez de
TEXT. Requiere migración alembic 20260518_1430_procedural_jsonb.py.
```

## Commits atómicos

- Un commit = un cambio lógico.
- No mezclar refactor con feature ni feature con docs.
- Si un PR tiene 10 commits y cada uno tiene sentido por separado,
  bárbaro. Si los commits son "wip", "fix", "fix 2", squashear antes
  de mergear.
