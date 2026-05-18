# Review automatica con Claude

Workflow de GitHub Actions que corre Claude Code en cada PR para
dejar una review automatica. Usa la suscripcion **Pro/Max** del
equipo (no API credits) via OAuth token.

Base oficial: [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action).

## Que hace

Dos workflows separados en `.github/workflows/`.

### `claude-pr-review.yml` — review automatica

- **Trigger:** `pull_request: opened, synchronize, reopened, ready_for_review`.
- **Proposito:** review automatica en cada PR nuevo o actualizado.
  Postea un unico comentario con veredicto, hallazgos por
  severidad (blocker / mayor / menor) citando `file:line`,
  compliance contra las 10 reglas no negociables, deuda explicita
  y cosas bien hechas.

### `claude-mention.yml` — respuesta a menciones

- **Trigger:** `issue_comment`, `pull_request_review_comment`,
  `pull_request_review`, `issues` — solo si el body contiene
  `@claude`.
- **Proposito:** respuesta a menciones explicitas. Util para
  deep-dive, preguntas, profundizar una review ya hecha o
  asistencia interactiva.

Ambos workflows usan **Sonnet 4.6** por default. El modelo se
cambia editando `claude_args: --model ...` en cada workflow.

## Setup inicial (una vez)

1. **Generar el OAuth token** desde tu Claude Code local:
   ```bash
   claude setup-token
   ```
   El token esta atado a tu cuenta Pro/Max y consume tu cuota.

2. **Agregar el secret al repo**:
   - GitHub → `BriarDevv/Ynara` → Settings → Secrets and variables →
     Actions → New repository secret.
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`.
   - Value: el token del paso 1.

3. **Instalar la GitHub App**:
   - https://github.com/apps/claude → Configure → seleccionar
     `Ynara` → Install. Requiere ser admin del repo.
   - Permisos requeridos: Contents (read), Issues (read & write),
     Pull requests (read & write).

4. **Verificar** abriendo un PR trivial. La action deberia
   disparar en menos de 90 segundos.

## Cuando revisar este workflow

Lista de triggers operativos. Cualquiera amerita un PR de
actualizacion al workflow o a los docs.

### Triggers tecnicos

- **El bot deja una review claramente equivocada** (y no es por
  estado divergente de git entre `main` local y remoto).
  Tweak al `prompt` del workflow. Si el patron se repite, abrir
  issue.

- **Anthropic publica `claude-code-action@v2`** con breaking
  changes. Migrar siguiendo el
  [migration guide](https://github.com/anthropics/claude-code-action/blob/main/docs/migration-guide.md).

- **`claude-sonnet-4-6` se marca como deprecated.** Cambiar el
  `--model` al modelo vigente. Verificar en
  [docs.claude.com/en/docs/about-claude/models](https://docs.claude.com/en/docs/about-claude/models).

- **El token OAuth expira** (workflow falla con `401
  Unauthorized`). Regenerar local con `claude setup-token` y
  actualizar el secret `CLAUDE_CODE_OAUTH_TOKEN`.

### Triggers de proyecto

- **`AGENTS.md` raiz cambia sustancialmente** — se agregan o
  renumeran reglas no negociables. Sanity check del `prompt`:
  sigue referenciando las reglas correctas?

- **Llegan PRs grandes** (>20 archivos) o migrations Alembic
  regularmente, y Sonnet se queda corto. Considerar opt-in
  explicito a Opus para esos paths: workflow separado con `path:`
  filter + `--model claude-opus-4-7`.

- **El repo abre la puerta a contribuciones externas** (forks).
  Migrar a `pull_request_target` con security review. Hoy el
  workflow no funciona con PRs desde forks.

### Triggers de team

- **El team se queja de quemar cuota Pro/Max** por las reviews.
  Revisar `--max-turns`, agregar path filters para saltar PRs
  doc-only, considerar opt-out por label.

- **El team se queja de comentarios muy largos o irrelevantes.**
  Acortar el `prompt` o ajustar la seccion "REGLAS DEL
  COMENTARIO".

### Trigger de cadencia

- **Pasaron 6 meses sin tocar nada.** Audit ligero: leer 5
  reviews recientes del bot y ver si el prompt sigue alineado con
  como evoluciono el repo.

## Limitaciones conocidas

1. **No funciona con PRs desde forks.** El evento `pull_request`
   no tiene permisos de escritura para forks por seguridad. Para
   habilitarlo habria que usar `pull_request_target`, que tiene
   implicancias de seguridad (un fork malicioso podria modificar
   el workflow). Mientras el repo sea privado entre los 3 owners,
   no aplica.
2. **No diferencia PRs triviales de PRs grandes.** Un PR que
   cambia 1 linea de un README recibe la misma review profunda
   que un PR que cambia 17 archivos. Eso quema cuota innecesaria.
   Mitigacion futura: path filters en el `on:` o un step previo
   que detecte tamano y redirija a un modelo mas liviano.
3. **El prompt es opinionado y pesado** (~3.5k caracteres). Esto
   inyecta muchos input tokens en cada review. Para volumen bajo
   (5-10 PRs por semana) esta bien; en repos enormes habria que
   aligerarlo.
4. **No persiste contexto entre reviews del mismo PR.** Cada
   `synchronize` gatilla una review desde cero. El bot no se
   acuerda de lo que dijo antes; el reviewer humano puede ver el
   historial pero el bot no lo procesa. Si esto se vuelve
   molesto, considerar `concurrency` mas permisivo + lectura
   manual de comments previos en el prompt.
5. **Sonnet 4.6 puede saltearse sutilezas arquitectonicas** que
   Opus captaria. Si el PR es critico (security, migrations,
   ADR), mejor pedir review humana o invocar `@claude` con
   instrucciones explicitas de profundizacion.

## Como desactivar temporalmente

### Para un PR especifico

- Marcarlo como **draft** — el workflow saltea drafts por el
  filtro `if:` de `pull_request.draft == false`.
- Alternativa rapida: el bot ya postea, pero ignoras el
  comentario.
- A futuro: implementar respeto por label `skip-claude-review`
  en el `if:` del job (hoy no esta implementado, issue
  pendiente).

### Para toda una racha

Ejemplo: semana de refactor donde no queres ruido del bot.

- Editar `claude-pr-review.yml` y comentar el bloque `on:` con
  `# `. Push. Cuando termines, descomentar.
- O directamente borrar el secret `CLAUDE_CODE_OAUTH_TOKEN`. La
  action va a fallar pero no postea nada (excepto el error log en
  la pestana Actions).

## Como debuggear un run que fallo

Comandos `gh` utiles:

```bash
# Ver los ultimos runs del workflow de PR review
gh run list --workflow=claude-pr-review.yml --limit 5

# Ver el log completo de un run especifico
gh run view <RUN_ID> --log

# Ver solo los steps que fallaron
gh run view <RUN_ID> --log-failed
```

### Errores frecuentes

- **`401 Unauthorized` en el step de Claude.** El token OAuth
  expiro o se rompio. Regenerar con `claude setup-token` y
  actualizar el secret `CLAUDE_CODE_OAUTH_TOKEN`.

- **`Rate limit exceeded`.** Quemaste tu cuota Pro/Max del
  periodo. Esperar al reset, pasar temporalmente a Sonnet 4.5
  (menos consumo) o configurar una API key como fallback.

- **`Could not find pull request`.** El evento que dispara no es
  de PR (ej. comentario en issue puro). Verificar el `if:` del
  job.

- **Timeout a los 15 minutos.** El `prompt` o `--max-turns` estan
  exagerados, o el repo es enorme. Bajar `--max-turns`, acortar
  el prompt.

- **El job no se dispara en absoluto.** Filtro `if:` o trigger
  mal configurado. Revisar `gh run list` para confirmar que el
  evento llego al runner.

## Para agentes IA

Si estas leyendo esto desde un agente que esta editando los
workflows:

1. **No hardcodees el token** en el workflow. Siempre via secret.
2. **No saques el filtro `if:`** del mention workflow — sin el,
   cualquier comentario en el repo gatillaria la action,
   quemando cuota.
3. **Si cambias el modelo**, actualizar tambien esta
   documentacion en el mismo PR.
4. **Si cambias el prompt sustantivamente**, postear un comment
   en el PR explicando que cambio y por que. El prompt es la
   pieza con mas impacto sobre la calidad de las reviews.

## Referencias

- [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions)
- [anthropics/claude-code-action README](https://github.com/anthropics/claude-code-action)
- [Setup guide oficial](https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md)
- [Usage guide](https://github.com/anthropics/claude-code-action/blob/main/docs/usage.md)
- [Solutions / use cases](https://github.com/anthropics/claude-code-action/blob/main/docs/solutions.md)
