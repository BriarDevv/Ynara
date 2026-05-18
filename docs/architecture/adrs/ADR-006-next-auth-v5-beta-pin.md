# ADR-006: Pinear next-auth a 5.0.0-beta.31 hasta release estable

## Estado
Aceptado

## Fecha
2026-05-18

## Contexto

El [`apps/web/package.json`](../../../apps/web/package.json) declaraba originalmente:

```json
"next-auth": "^5.0.0"
```

Al intentar `pnpm install`, la resolución falla con:

```
ERR_PNPM_NO_MATCHING_VERSION  No matching version found for next-auth@^5.0.0
The latest release of next-auth is "4.24.14".
Other releases include: beta: 5.0.0-beta.31
```

next-auth v5 (rebranded como **Auth.js**) sigue en beta channel. El rango semver `^5.0.0` **no matchea pre-releases** salvo opt-in explícito. El install completo del monorepo queda bloqueado.

Este blocker se descubrió al arrancar la Sesión 1 del [plan de frontend MVP](../../planning/FRONTEND-ONBOARDING-PLAN.md), donde la Sesión 3 explícitamente prevé usar Auth.js v5 mockeado para el step de Auth del onboarding.

## Decisión

Pinear a versión **exacta** `5.0.0-beta.31`:

```json
"next-auth": "5.0.0-beta.31"
```

Sin caret (`^`) ni tilde (`~`). Cada upgrade a una beta posterior es una decisión manual, no automática.

## Alternativas consideradas

### A. Bajar a `next-auth@4.24.14` (estable)

- **Pro**: API estable, sin riesgo de breaking changes entre patches.
- **Contra**: la API de v4 es significativamente distinta a v5/Auth.js. El plan de onboarding describe patrones de v5 (App Router-first, `auth()` helper, providers como funciones). Migrar a v5 después implicaría reescribir el step de Auth y todo el flujo de sesión.

### B. Rango beta `^5.0.0-beta.31` o `next-auth@beta`

- **Pro**: pickea automáticamente betas nuevas.
- **Contra**: cada nueva beta puede traer breaking changes silenciosos. El equipo perdería control sobre cuándo y cómo se incorporan esos cambios.

### C. Remover `next-auth` de `package.json` hasta Sesión 3

- **Pro**: scope chico, sin compromiso prematuro.
- **Contra**: pospone el problema sin resolverlo. Cuando Sesión 3 llegue, vuelve a aparecer y bloquea trabajo.

### D. (Elegida) Pin exacto a `5.0.0-beta.31`

- **Pro**: install pasa, alineado al plan, control total del equipo sobre upgrades.
- **Contra**: dependemos de una versión beta para auth productivo eventual.

## Reglas

1. **No usar features marcados "experimental"** en los docs de Auth.js v5. Limitarse a la API estable de la beta.
2. **Smoke test obligatorio** antes de upgradear a una nueva beta: levantar `/onboarding/auth`, signup mockeado y login mockeado deben funcionar. Si rompen, no se mergea el upgrade.
3. **Migración a `5.0.0` estable** apenas se publique. La migración cierra este ADR y crea uno nuevo que lo supersede si requiere decisiones adicionales.
4. **El upgrade de beta se commitea solo**: nunca bundleado con cambios funcionales de auth, para que el diff de auth sea aislable si rompe.

## Consecuencias positivas

- Destraba `pnpm install` y la Sesión 1 del plan de frontend.
- Alineado con la decisión arquitectónica original del repo (v5 en `package.json`).
- App Router-first auth desde el día 1 (la API que vamos a usar en producción).
- Pin exacto da control total sobre cuándo se incorporan cambios.

## Consecuencias negativas

- **API beta puede romper en upgrades.** Mitigado por: pin exacto + smoke test + commit aislado por upgrade.
- **Sin garantías de soporte** del equipo de Auth.js para una beta específica.
- **Bugs propios de la beta** (si aparecen) son nuestros para mitigar hasta el release estable.

## Triggers de revisión

- Release de `next-auth@5.0.0` estable → migrar y reemplazar este ADR.
- Si no hay nueva beta en 6 meses → revaluar si conviene volver a v4 o esperar.
- Si una beta posterior trae security fix crítico → upgrade obligatorio con smoke test.

## Implementación inmediata

Cambio puntual en [`apps/web/package.json`](../../../apps/web/package.json):

```diff
-    "next-auth": "^5.0.0",
+    "next-auth": "5.0.0-beta.31",
```

Sin cambios adicionales en el resto del monorepo (Auth.js v5 está dentro de `apps/web` únicamente).

**Verificación de la versión elegida**:
- Confirmado que `5.0.0-beta.31` es la última beta disponible al momento de redactar este ADR (`pnpm view next-auth versions --json` lista las betas, mensaje de error de `pnpm install` reportaba `beta: 5.0.0-beta.31` como tag actual del registry).
- `pnpm install` exitoso con la versión pineada (45.3s, monorepo completo).

**Aprobación humana del install (regla #1)**:
Este pin destrabó `pnpm install` que requiere OK humano explícito por regla #1 de `AGENTS.md`. La aprobación se otorgó en la conversación de pair-programming del 2026-05-18 (@MateoGs013), inmediatamente antes del primer `pnpm install` del repo. Se documenta acá para auditoría futura.

## Referencias

- [Auth.js v5 migration guide](https://authjs.dev/getting-started/migrating-to-v5) — patrones que vamos a usar.
- [`docs/planning/FRONTEND-ONBOARDING-PLAN.md`](../../planning/FRONTEND-ONBOARDING-PLAN.md) — Sesión 3 implementa el step de Auth con esta lib.
- [`apps/web/AGENTS.md`](../../../apps/web/AGENTS.md) — reglas del frontend web.

## Aprobación

Cambios a este ADR requieren PR con review de @MateoGs013 (CODEOWNER técnico). Cuando este ADR se reemplace por uno nuevo, marcar el estado a "Supersedido por ADR-XXX".
