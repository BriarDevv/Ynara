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

## Auto-revisión prohibida

Si el PR es propio (sos el autor o tu agente sub creó los commits), **parar**. No auto-aprobarte en el mismo contexto (regla de `CLAUDE.md`). Pedile a otro reviewer humano o agente que lo haga.
