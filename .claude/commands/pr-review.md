---
description: Review estructurada de un PR de Ynara aplicando las 10 reglas no negociables
argument-hint: <PR_NUMBER>
---

Ejecutá la skill [`skills/pr-review/SKILL.md`](../../skills/pr-review/SKILL.md) sobre el PR número **$ARGUMENTS**.

## Pasos resumidos

1. Leé `skills/pr-review/SKILL.md` entera. Es la fuente de verdad de cómo se hace una review en este repo.
2. Aplicá el paso a paso al PR #$ARGUMENTS:
   - **Fase 1 — Setup y contexto**: `gh pr view`, leer `AGENTS.md` raíz + `AGENTS.md` del app afectado + `docs/conventions/AI-GUIDELINES.md`.
   - **Fase 2 — Verificaciones mecánicas**: `bash scripts/ynara-doctor.sh`, grep por reglas #1 a #5, landmines del scaffold.
   - **Fase 3 — Análisis cualitativo**: compliance arquitectónico, coherencia con `ynara.config.json`, tests, file size, tipos, tono.
   - **Fase 4 — Output**: generar comentario con la estructura canónica (veredicto, hallazgos por severidad con `file:line`, cierre de hallazgos previos, deuda explícita, compliance table, cosas bien hechas).
3. Guardá el body del comentario en `/tmp/pr-$ARGUMENTS-review.md` y posteá:
   ```bash
   gh pr comment $ARGUMENTS --body-file /tmp/pr-$ARGUMENTS-review.md
   ```
4. **NO mergees el PR**, **NO lo cierres**, **NO lo apruebes formalmente**. Solo dejá el comentario.

## Reglas duras de tono (recordatorio)

- Rioplatense conversacional, código en inglés, sin emojis salvo que el repo ya use.
- Sin sicofancia. Sin "great job" ni "excelente trabajo".
- Citar `archivo:línea` en cada hallazgo o el hallazgo no es accionable.
- Si no hay hallazgos blocker / mayor, decirlo explícito — no inventar.

## Higiene de rama (CRÍTICO)

Antes y después de cualquier `gh pr checkout <N>` o `git fetch origin pull/<N>/head:<rama>` durante este review: confirmar que HEAD está en `main` y sincronizada con `origin/main` (`git status` + `git log -1`). Al terminar, volver a `main` antes de crear cualquier rama nueva. Si no, `git checkout -b` deriva del tip del PR ajeno y el siguiente merge fast-forward arrastra esos commits a `main` por inercia (incident PR #13). Detalle en `skills/pr-review/SKILL.md` sección "Higiene post-review (obligatorio)".

## Self-review (autor del PR = operador)

Si sos autor del PR o los commits están co-authored con Claude, **no parar**. Delegá la Fase 3 (análisis cualitativo) a un sub-agent `code-reviewer` con prompt self-contained y agregá el banner obligatorio al principio del comentario:

> **Review delegada a sub-agent `code-reviewer`** — autor del PR coincide con el operador. Análisis hecho en sesión nueva con contexto fresco; la pasada humana sigue siendo recomendable antes de mergear.

El sub-agent corre en sesión nueva, sin la historia de las decisiones que tomaste cuando escribiste el código — eso cumple el espíritu de la regla de `CLAUDE.md` ("la pasada de review siempre va en un agente separado").

Detalle completo en la sección [Self-review](../../skills/pr-review/SKILL.md#self-review--autor-del-pr-es-el-operador) de `skills/pr-review/SKILL.md`, incluyendo cuándo SÍ parar (PR mergeado, trivial, doctor falla) y cuándo conviene delegar también a `security-reviewer` o `verifier` en paralelo.
