# SKILL: Review estructurada de un PR de Ynara

Formaliza el workflow de review de PRs aplicando las 10 reglas no
negociables de [`AGENTS.md`](../../AGENTS.md), las 15 reglas
extendidas de
[`docs/conventions/AI-GUIDELINES.md`](../../docs/conventions/AI-GUIDELINES.md)
y los criterios de tono y formato que el equipo viene usando en
las reviews reales (referencias: PR #1, PR #2, PR #5).

El output siempre es **un solo comentario** posteado en el PR vía
`gh pr comment`. No se aprueba ni se mergea ni se cierra.

## Cuándo usar

- Antes de pedir review humana en un PR — para autochequear que
  las reglas mecánicas pasen y los hallazgos críticos estén
  marcados.
- Deep dive en un PR ya abierto cuando un humano quiere una
  segunda opinión estructurada.
- Validar compliance con reglas duras antes de mergear.

## Cuándo NO usar

- En un PR ya mergeado o cerrado — no tiene sentido reviewar lo
  que ya entró.
- "Drive-by reviews" sin haber leído `AGENTS.md` y el `AGENTS.md`
  del app afectado.
- PRs triviales (1-2 líneas de typo o config). Un comentario
  manual rápido alcanza.

> **Self-review (autor = operador):** **no es razón para parar**.
> Cuando el operador es autor del PR o los commits están
> co-authored con Claude, la skill delega la Fase 3 a un
> sub-agent `code-reviewer` en sesión nueva con prompt
> self-contained, y agrega un banner obligatorio en el comentario.
> Ver sección [Self-review](#self-review--autor-del-pr-es-el-operador).

## Pre-requisitos

- `gh` autenticado: `gh auth status`.
- Estar en el repo de Ynara.
- Working tree limpio (vas a hacer reads y posiblemente
  `gh pr checkout`).
- Tener corrido `bash scripts/ynara-doctor.sh` recientemente
  sobre `main`.
- **HEAD en `main` y sincronizada con `origin/main`** antes de
  empezar (`git status` + `git log -1` para confirmar SHA).
  Crítico para no contaminar la base de futuras ramas. Ver
  landmine "Ramas nuevas derivadas de un PR ajeno" en
  [`docs/conventions/AI-GUIDELINES.md`](../../docs/conventions/AI-GUIDELINES.md).

## Higiene post-review (obligatorio)

Después de cualquier `git fetch origin pull/<N>/head:<rama>` o
`gh pr checkout <N>` que hagas durante el review, **volver a
`main` antes de hacer cualquier otra cosa**:

```bash
git checkout main
git pull --ff-only origin main
# Borrar la rama local del PR ajeno (opcional):
git branch -D pr-<N>-review
```

Si no volvés a `main` y después corrés `git checkout -b nueva-rama`,
esa rama va a heredar los commits del PR ajeno como ancestros. Cuando
se mergee con fast-forward, GitHub arrastra esos commits a `main` por
inercia (incident PR #13). El check `[10/10]` de `ynara-doctor.sh`
detecta esto antes del PR — corrélo siempre antes de abrir uno nuevo.

## Invocación

Desde Claude Code, en una sesión activa sobre el repo:

- **Slash command:** `/pr-review <PR_NUMBER>` (ver
  [`.claude/commands/pr-review.md`](../../.claude/commands/pr-review.md)).
- **Manual:** "Aplica `skills/pr-review/SKILL.md` al PR #N".

## Paso a paso

### Fase 0 — Git state fresco (obligatorio)

Antes de cualquier comparación, asegurate de estar viendo el estado
actual del repo. Las comparaciones `main..pr-branch` son confiables
**solo si `main` local matchea `origin/main`**.

```bash
git fetch origin
git log --oneline origin/main..main      # debe estar vacío
git log --oneline main..origin/main      # debe estar vacío
```

Si local main diverge de origin/main, **frená**. Cualquier diff
contra `main` local va a mezclar tu estado con el del PR y generar
falsos positivos. Sincronizar primero:

```bash
git checkout main
git pull --ff-only origin main
```

> **Lección histórica**: en la review de PR #1, un critic agent
> reportó un hallazgo BLOQUEANTE falso porque comparó contra `main`
> local desactualizado y vio cambios en `CODEOWNERS` que estaban en
> el remoto, no en el PR. Esta fase elimina ese tipo de FP.

### Fase 1 — Setup y contexto

1. **Metadata del PR:**
   ```bash
   gh pr view <N> --json title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,files,commits
   ```

2. **Leer el contexto que aplica:**
   - `AGENTS.md` raíz — las 10 reglas no negociables y el Repo
     Map.
   - El `AGENTS.md` del app afectado:
     - `apps/web/AGENTS.md` si toca `apps/web/**`.
     - `apps/mobile/AGENTS.md` si toca `apps/mobile/**`.
     - `apps/backend/AGENTS.md` si toca `apps/backend/**`.
   - `docs/conventions/AI-GUIDELINES.md` — 15 reglas extendidas
     + landmines.
   - Si el PR cita un ADR, leerlo. Si toca arquitectura sin ADR
     citado, flag como hallazgo mayor (regla extendida #6).

3. **Comentarios previos del PR:**
   ```bash
   gh pr view <N> --comments
   ```
   Si hay reviews previas, notarlas para cerrarlas explícitamente
   en el comentario final.

### Fase 2 — Verificaciones mecánicas

Correr los chequeos automatizables antes de leer el diff. Cada
uno corresponde a una regla del repo.

1. **Doctor:**
   ```bash
   bash scripts/ynara-doctor.sh
   ```
   Si falla, eso ya es hallazgo blocker en el comentario.

2. **Diff del PR (guardado para análisis):**
   ```bash
   gh pr diff <N> > /tmp/pr-<N>.diff
   gh pr diff <N> --name-only > /tmp/pr-<N>.files
   ```

3. **Regla #1 — Confirmación humana** para deps, md raíz, config:
   ```bash
   grep -E '^(pnpm-lock\.yaml|apps/backend/uv\.lock|[A-Z_]+\.md|ynara\.config\.json)$' /tmp/pr-<N>.files
   ```
   Si aparece algo, el PR debe tener evidencia (commit body o PR
   description) del OK humano explícito.

4. **Regla #2 — Secrets:**
   ```bash
   grep -iE '(AKIA|sk-[a-z0-9]{20,}|ghp_[a-zA-Z0-9]{30,}|password\s*=\s*["'\''][^"'\'']{8,}|aws_secret|api[_-]?key\s*=\s*["'\''])' /tmp/pr-<N>.diff
   ```
   Cualquier hit = blocker inmediato.

5. **Regla #3 — Tablas sagradas:**
   ```bash
   grep -E '^(apps/backend/app/memory/|apps/backend/alembic/versions/)' /tmp/pr-<N>.files
   ```
   Cualquier hit requiere 1 aprobación humana explícita (review formal
   en el PR, además del operador autor) + tests. Flagear como blocker
   hasta que esté visible.

6. **Regla #4 — APIs externas de IA en backend:**
   ```bash
   grep -E '^\+\s*(import|from)\s+(openai|anthropic|google\.generativeai|cohere|mistralai)\b' /tmp/pr-<N>.diff
   ```
   Cualquier hit = blocker.

7. **Regla #5 — Cliente Supabase en frontend:**
   ```bash
   grep '@supabase/supabase-js' /tmp/pr-<N>.diff
   ```
   Si aparece bajo `apps/web/` o `apps/mobile/` o `packages/`,
   blocker.

8. **Regla #6 — Conventional Commits en español:**
   ```bash
   gh pr view <N> --json commits --jq '.commits[].messageHeadline'
   ```
   Verificar formato `tipo(scope): descripción` y verbo en
   imperativo español (`agregar`, `corregir`, `actualizar`, no
   `agregando` ni `agregado`).

9. **Regla #8 — Scope obligatorio:** cada commit debe tener
   scope `(web)`, `(mobile)`, `(backend)`, `(deps)`, etc., salvo
   cambios cross-cutting reales.

10. **Landmines del scaffold:**
    - `apps/web/tailwind.config.ts` o `.js` no deben aparecer
      (Tailwind v4 es CSS-first):
      ```bash
      grep -E 'apps/web/tailwind\.config\.(ts|js)$' /tmp/pr-<N>.files
      ```
    - `apps/mobile/package.json` no debe upgradear `tailwindcss`
      a `^4` (NativeWind sigue en v3).
    - Patrones de `.gitignore`: `models/` y `checkpoints/` deben
      quedar anclados con `/...` (no atrapan módulos Python
      legítimos).

### Fase 3 — Análisis cualitativo

Una vez pasadas las verificaciones mecánicas, leer el diff y
analizar.

1. **Compliance arquitectónico:**
   - Respeta los ADRs vigentes (`docs/architecture/adrs/`)?
   - Si introduce algo nuevo (dep mayor, framework, DB), hay
     ADR citado?
   - Modelos: Gemma solo lee, Qwen lee y escribe (ADR-002).
   - DB: solo Postgres + pgvector (ADR-004).
   - Auth: en FastAPI, no en RLS (ADR-005).

2. **Coherencia con configuración canónica:**
   - Modos referenciados matchean `ynara.config.json`?
   - Si toca `apps/web/src/app/globals.css`, alineado con
     `DESIGN.md`?
   - Tokens CSS no hardcoded en componentes (regla extendida
     #13)?

3. **Tests:**
   - Código nuevo tiene tests asociados (regla extendida #11)?
   - Memoria y migraciones obligatorios.

4. **File size:**
   - Archivos cerca de 300 líneas → flag menor.
   - Archivos sobre 500 líneas → mayor (refactor obligatorio).

5. **Tipos:**
   - TS: `any` sin comentario justificándolo → menor.
   - Python: `Any` en signatures sin comentario → menor.

6. **Tono y rioplatense:**
   - Docs y user-facing content: voseo, evitar peninsular.
   - Comentarios en código: español; identificadores en inglés.

7. **Cross-referencias obligatorias** — esto es lo que separa una
   review superficial de una review real. Para cada uno, abrir
   los archivos y verificar contra el estado actual del repo:

   - **Claims del PR description vs. archivos reales.** Si el PR
     body dice "pineo X a Y" o "agrego Z en el archivo W", abrir
     el archivo y confirmar. **No tomar el PR body como
     evidencia**.
     ```bash
     # Ejemplo: PR dice "pineo next-auth a 5.0.0-beta.31"
     grep '"next-auth"' apps/web/package.json
     ```

   - **Doc ↔ código alineados.** Si el PR toca docs y código del
     mismo área, verificar que queden consistentes.
     - PR agrega un token en `globals.css`? Chequear si
       `DESIGN.md` lo documenta.
     - `DESIGN.md` menciona un valor pero `globals.css` no lo
       implementa (o viceversa)? Flag.
     - PR menciona un ADR? Leer el ADR y verificar que la
       implementación matchee la decisión documentada.

   - **Valores duplicados** — hex codes, version pins, model
     names, paths. Cuando el mismo valor aparece en múltiples
     archivos, hay que confirmar que matchean.
     ```bash
     # Hex de paleta usado en varios lugares
     grep -rn "#2f5aa6" --include="*.css" --include="*.tsx" --include="*.md"

     # Pin de version en package.json vs README/ADR
     grep -rn "5\.0\.0-beta\.31" --include="*.json" --include="*.md"

     # Nombre de modelo en config vs router
     grep -rn "claude-sonnet-4-6\|gemma-4-26b-a4b" --include="*.py" --include="*.json"
     ```
     Si un valor diverge entre archivos, **siempre es un hallazgo**
     (mínimo menor, mayor si afecta runtime).

   - **Cierre de reviews previas.** Si hay reviews anteriores en
     este PR o en PRs predecesores del mismo plan, verificar uno
     por uno cuáles hallazgos están cerrados. **Citar el comment
     URL original como evidencia.**

   - **Templates ↔ archivos referenciados.** Si el PR agrega un
     archivo que un template menciona (ej:
     `PULL_REQUEST_TEMPLATE.md` linkea a `CLAUDE-REVIEW.md`),
     verificar que el archivo existe y que el link no está roto.

8. **Verbatim sobre paráfrasis.** Cuando reportes un hallazgo,
   citá el contenido exacto del archivo en bloque de código con
   sintaxis. **No parafrasees** lo que el código hace.
   - Mal: "el componente hardcodea un color azul".
   - Bien:
     ````
     `apps/web/src/app/globals.css:316` tiene `#2f5aa6` literal:
     ```css
     box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px #2f5aa6;
     ```
     ````

### Fase 4 — Output: comentario en el PR

Estructura canónica (ver PR #1 y PR #2 como referencia viva):

```md
## Review @<tu-handle> — <foco si aplica>

**Veredicto**: approve | approve con cambios menores | request changes | block

### Hallazgos accionables

#### 1. <Severidad> — `<archivo>:<línea>`: <título corto>

Descripción del problema. Por qué rompe (citar la regla
correspondiente). Fix sugerido en 1-3 líneas o código.

#### 2. ...

### Cierre de hallazgos de reviews previas

(Opcional. Si hubo reviews anteriores en este PR o en PRs
predecesores del mismo plan. Tabla con # / Estado / Evidencia.)

| # | Estado | Evidencia |
|---|---|---|
| #N | ✅ Cerrado / ❌ Abierto / ⏸ Aplazado | ... |

### Deuda explícita (opcional, máx 3)

Cosas que el PR introduce y conviene trackear como issue
separado, pero no bloquean este merge.

### Compliance con reglas no negociables

| Regla | Estado |
|---|---|
| #1 OK humano para deps / md root / config | OK / WARN / FAIL |
| #2 sin secrets | OK / FAIL |
| #3 tablas sagradas | OK / 1 aprobación humana explícita requerida |
| #4 sin APIs externas de IA en backend | OK / FAIL |
| #5 sin `@supabase/supabase-js` en frontend | OK / FAIL |
| #6 Conventional Commits en español | OK / FAIL |
| #8 scope obligatorio en commits | OK / FAIL |

### Cosas bien hechas (opcional, máx 3)

Solo si hay decisiones notables que valen la pena reforzar. Sin
sicofancia ni relleno.
```

Postear:
```bash
gh pr comment <N> --body-file /tmp/pr-<N>-review.md
```

**No mergees, no cierres, no apruebes formalmente** — solo
comentar.

## Definición de severidades

- **blocker** — rompe regla no negociable. Filtración de
  secret, dato de usuario a API externa, `@supabase/supabase-js`
  en frontend, modificación a tabla sagrada sin la aprobación humana
  explícita (regla #3), install de dep sin OK humano, falla del
  doctor. **Bloquea el merge.**

- **mayor** — viola regla extendida o decisión arquitectónica
  documentada. Tipos `any` injustificados en código central,
  archivo >500 líneas sin refactor, tests faltantes en código
  crítico, ADR no citado para cambio arquitectónico.
  **No bloquea pero hay que abordar.**

- **menor** — limpieza, consistencia, naming, comentarios. Hex
  hardcoded duplicado, file:line que ayudaría agregar, wording
  en docs. **Mergeable, pero suma deuda.**

## Reglas de tono del comentario

- **Rioplatense conversacional**, con voseo natural. Sin
  peninsular (vosotros, ordenador, vale).
- **Código y nombres técnicos en inglés** (variables, paths,
  funciones, librerías).
- **Sin emojis** en el comentario, salvo que el repo ya use en
  docs (a hoy, no usa).
- **Sin sicofancia**: no "great job", no "excelente trabajo",
  no relleno de cortesía. Si no hay cosas bien hechas
  notables, omitir la sección.
- **No inventar hallazgos** para llenar tabla. Si no hay
  hallazgos blocker / mayor, decirlo explícitamente.
- **Siempre citar `archivo:línea`** cuando se reporta un
  hallazgo. Sin file:line, no es accionable.
- **Verbatim sobre interpretación**: si citás contenido del
  diff, usar bloque de código con sintaxis. Si interpretás
  intención, decir "asumo que...".

## Self-review — autor del PR es el operador

Cuando el operador es autor del PR (o los commits están
co-authored con Claude), la skill **no para**. Lo que cumple el
espíritu de la regla "no auto-aprobarte en el mismo contexto" no
es bloquear la review, es **garantizar que la pasada de análisis
ocurra en una sesión nueva, con contexto fresco y mindset
adversarial**.

### Cómo proceder

1. **Delegar la Fase 3 (análisis cualitativo) a un sub-agent
   `code-reviewer`** con prompt self-contained que incluya:
   - Las 10 reglas no negociables (`AGENTS.md`).
   - El `AGENTS.md` del app afectado (web / mobile / backend).
   - El diff del PR y la metadata (`gh pr view --json ...`).
   - Las landmines del scaffold relevantes al diff.
   - Foco específico del review (bugs, a11y, security, etc.).

   El sub-agent corre en sesión nueva, sin la historia de las
   decisiones que tomó el operador cuando escribió el código.
   Eso es lo que evita el sesgo de confirmación y la
   contaminación de contexto.

2. **Banner obligatorio al principio del comentario del PR**.
   Antes del veredicto, agregar la línea visible:

   ```md
   > **Review delegada a sub-agent `code-reviewer`** — autor del PR
   > coincide con el operador. Análisis hecho en sesión nueva con
   > contexto fresco; la pasada humana sigue siendo recomendable
   > antes de mergear.
   ```

3. **Postear igual con `gh pr comment`**. La estructura del
   comentario (veredicto, hallazgos por severidad, compliance
   table, etc.) se mantiene idéntica. Solo cambia el banner
   inicial.

4. **Cierre humano recomendado** para cambios sensibles: tablas
   sagradas (regla #3), migraciones Alembic, deps del lockfile,
   `.md` raíz, `ynara.config.json`. El sub-agent cubre el chequeo
   mecánico + cualitativo, pero el humano cierra el loop de
   accountability.

### Por qué esto cumple la regla

La regla de `CLAUDE.md` dice *"la pasada de review siempre va en
un agente separado"*. La palabra clave es **separado**, no **otro
modelo**. Un sub-agent `code-reviewer` invocado con prompt
self-contained corre en sesión independiente, sin acceso a la
conversación donde se escribió el código. Eso ya cumple el
espíritu — el reviewer ve el código, no las racionalizaciones del
autor.

Los dos riesgos que la regla original busca evitar:

- **Sesgo de confirmación** — el mismo contexto que escribió el
  código tiende a justificar decisiones en lugar de cuestionarlas.
  El sub-agent fresh no tiene esas decisiones cargadas, las ve
  como hechos del diff.
- **Contaminación de contexto** — los trade-offs y supuestos del
  operador no se filtran al review. El sub-agent solo ve lo que
  llega en el prompt self-contained.

### Cuándo SÍ parar (incluso siendo self-review)

- PR ya mergeado o cerrado.
- PR trivial (1-2 líneas de typo) — un comentario manual alcanza.
- Working tree del operador sucio y la skill no puede hacer
  `gh pr checkout` limpio.
- `gh` no autenticado.
- `bash scripts/ynara-doctor.sh` falla irrecuperablemente sobre
  `main` (Fase 0 — sin doctor verde no hay baseline confiable).

### Sub-agentes alternativos según foco

`code-reviewer` es el default. Para PRs con foco específico vale
usar el sub-agent más afilado:

- **Seguridad fuerte** (auth, secrets, env, fetcher, headers):
  delegar también a `security-reviewer` en paralelo.
- **Verificación de claims del PR contra el código real**: usar
  `verifier`.
- **Causal tracing de un bug existente**: `tracer`.

Si invocás dos sub-agents en paralelo, consolidá los findings en
un único comentario antes de postear — no dos comentarios
separados sobre el mismo PR.

## Anti-patterns del review

- Review sin haber leído `AGENTS.md` raíz primero.
- "LGTM" sin justificación.
- Aprobar PRs con hallazgos blocker sin explicitar el bloqueo.
- Hallazgos sin `archivo:línea`.
- Comentar el mismo hallazgo en múltiples lugares.
- Inventar hallazgos para llenar las secciones del template.
- Re-revisar un PR cerrado o mergeado.
- Tono sicofántico o moralizante.
- Modificar archivos del repo durante la review (solo lectura
  + `gh pr comment`).
- **Comparar el diff contra `main` local sin `git fetch origin`
  previo** — riesgo de FP por estado divergente. Ver Fase 0.
- **Tomar el PR description como evidencia** sin verificar contra
  los archivos reales. El PR body cuenta intenciones, los
  archivos cuentan hechos.
- **Parafrasear código** en un hallazgo en vez de citar verbatim
  con bloque de código.

## Checklist final antes de postear

- [ ] `git fetch origin` corrido. Local `main` matchea
      `origin/main` (Fase 0).
- [ ] Doctor corrió OK (o el fallo está como hallazgo blocker).
- [ ] Las 5 reglas mecánicas (#1, #2, #3, #4, #5) chequeadas
      con grep.
- [ ] Claims del PR description verificadas contra los archivos
      reales (Fase 3.7).
- [ ] Doc ↔ código verificado consistente cuando ambos cambian
      (Fase 3.7).
- [ ] Valores duplicados (hex / version / model / path)
      cross-checked con grep (Fase 3.7).
- [ ] Cada hallazgo tiene severidad + `archivo:línea` + fix.
- [ ] Hallazgos citados verbatim, no parafraseados (Fase 3.8).
- [ ] Veredicto explícito al principio del comentario.
- [ ] Sin emojis.
- [ ] Sin sicofancia ni relleno.
- [ ] Tabla de compliance presente y con OK / WARN / FAIL.
- [ ] Body guardado en `/tmp/pr-<N>-review.md` antes de
      `gh pr comment --body-file`.
- [ ] No se mergeó, ni cerró, ni aprobó formalmente.

## Links

- [`AGENTS.md`](../../AGENTS.md) — 10 reglas no negociables,
  Repo Map.
- [`docs/conventions/AI-GUIDELINES.md`](../../docs/conventions/AI-GUIDELINES.md)
  — 15 reglas extendidas + landmines.
- [`docs/conventions/CODE-STYLE.md`](../../docs/conventions/CODE-STYLE.md)
  — estilo por lenguaje.
- [`docs/conventions/COMMITS.md`](../../docs/conventions/COMMITS.md)
  — Conventional Commits en español.
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — flujo de PRs.
- [`scripts/ynara-doctor.sh`](../../scripts/ynara-doctor.sh)
  — validaciones pre-PR.

## Histórico — referencias de reviews reales

- PR #1: https://github.com/BriarDevv/Ynara/pull/1#issuecomment-4481972122
- PR #2: https://github.com/BriarDevv/Ynara/pull/2#issuecomment-4482182163
