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
- `core` / `shared-types` / `shared-schemas` / `ui` / `config` — packages
- `architecture` / `product` / `ops` / `conventions` — docs
- `infra` — `infra/`
- `llm` — capa LLM dentro de backend
- `memory` — capa de memoria dentro de backend
- `db` — migraciones Alembic / DDL dentro de backend
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

El comparador de embeddings in-house tenía threshold muy laxo.
Subimos el threshold a 0.92 y agregamos un test que evita la
regresión que vimos en el incident del 2026-04-12.
```

## Breaking changes

Agregar `!` después del tipo + footer `BREAKING CHANGE:`:

```
feat(backend)!: cambiar esquema de procedural_memory

BREAKING CHANGE: la tabla procedural_memory ahora usa JSONB en vez de
TEXT. Requiere migración alembic 20260518_1430_procedural_jsonb.py.
```

## Commits atómicos

**Bloqueante (regla #7 de `AGENTS.md`)**: un commit = un cambio lógico.
No mezclar refactor con feature ni feature con docs. PR rechazado si
llega como commit monolítico.

### Cuándo splitear

Si tu PR cumple **alguna** de estas:

- Más de ~200 líneas modificadas en total.
- Más de 3 archivos tocados en áreas distintas (modelos + schemas +
  docs + refactor en un solo commit = NO).
- Toca tablas sagradas (`semantic_memory`, `episodic_memory`,
  `procedural_memory`): el commit que las define **siempre** va
  aislado, para que la aprobación humana de la regla #3 inspeccione
  un commit específico, no busque el cambio enterrado en uno grande.
- Mezcla `feat` + `refactor` + `docs` + `test`: cada tipo es un
  cambio lógico distinto, va en commit propio.

### Cómo splitear (workflow)

Antes del primer `git add`:

```bash
git status --short
# Mirar la lista, agrupar mentalmente por "porqué" lógico.
# Si hay >1 grupo, son >1 commit.
```

Si ya hiciste el commit monolítico y no pusheaste todavía:

```bash
git reset --soft HEAD~1     # desarmar el commit, archivos quedan staged
git reset HEAD .            # unstage todo, vuelven a working tree
# Ahora git add + git commit en grupos chicos.
```

Si ya pusheaste a una feature branch (no main), force-push después
de reescribir está OK:

```bash
git reset --soft HEAD~N     # N = cantidad de commits a reescribir
git reset HEAD .
# git add + commit en grupos chicos.
git push --force-with-lease origin <feature-branch>
```

**Nunca force-push a `main`** (branch protection lo bloquea + regla #1
prohíbe modificar `main` fuera del flow de PR).

### Ejemplos

**Mal — commit monolítico (real, PR #15 versión 1)**:

```
feat(backend): definir modelos SQLAlchemy + schemas Pydantic de memoria

  13 files changed, 860 insertions(+), 69 deletions(-)
```

Mezcla: enums nuevos + refactor del router + 4 modelos SQLAlchemy +
4 schemas Pydantic + docs MODELS.md. Imposible de reviewar atómico, el
commit que toca tablas sagradas (regla #3) queda enterrado.

**Bien — mismo PR, decomposición atómica (PR #15 versión 2)**:

```
docs(backend): completar MODELS.md con detalle de tablas + enums + ADR-007
feat(backend): schemas Pydantic mirror de user, session, memory, audit
feat(backend): exportar modelos en app.models package
feat(backend): AuditLog inmutable para operaciones de memoria
feat(backend): tablas sagradas — SemanticMemory + EpisodicMemory + ProceduralMemory
feat(backend): modelo SQLAlchemy ChatSession
feat(backend): modelo SQLAlchemy User
feat(backend): agregar enums compartidos cross-domain
```

8 commits, cada uno con un porqué claro. Commit de tablas sagradas
aislado para la aprobación humana de la regla #3. Blame útil, revert
quirúrgico, review por grupos lógicos.

### Squashear vs no squashear

- **Sí squashear**: commits "wip", "fix", "fix 2", "intento N",
  "ahora sí". Esos no aportan al historial — limpiar con
  `git rebase -i` antes de mergear.
- **No squashear**: commits chicos atómicos donde cada uno tiene
  sentido propio (caso del PR #15 versión 2 arriba). El historial
  lineal con rebase merge preserva los commits individuales —
  perderlos es perder contexto.

### Antes de pushear, último check

```bash
git log --oneline origin/main..HEAD
# Si ves commits gigantes o mensajes vagos, parar y reescribir antes
# del push. Es mas barato que un force-push o un PR rechazado.
```
