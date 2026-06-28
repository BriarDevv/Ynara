# ADR-026: Contrato de intake del onboarding (señales → operativo vs memoria)

## Estado
Propuesto

## Fecha
2026-06-28

## Contexto

El onboarding quedó igualado web↔mobile (6 pasos: `auth → nombre → dia → modos
→ sobre-vos → a11y`, ver [`onboarding-web-mobile-aligned`] / PRs #419–#427) y
**captura** estas señales del usuario:

| Señal | Origen (step) | Hoy queda en |
|---|---|---|
| `display_name` | nombre | tabla `users` ✅ |
| `interested_modes` | modos | `useUserStore` (localStorage) ❌ |
| `a11y` (`text_size`/`high_contrast`/`motion`) | a11y | `useA11yStore` (localStorage) ❌ |
| `mood` + `mood_free_text` | dia | `useUserStore` ❌ |
| sobre-vos (`dedication`/`study_what`/`work_what`/`purpose`/`interests`) | sobre-vos | `useOnboardingStore`→`useUserStore` ❌ |

Al completar, el front solo manda `{ display_name, onboarding_completed: true }`
a `PATCH /v1/users/me` (`UserUpdate`, `extra='forbid'`, ver
[`apps/backend/app/schemas/user.py`](../../../apps/backend/app/schemas/user.py)).
**Todo lo demás se valida con `OnboardRequestSchema` y se descarta del lado
servidor** — se queda client-side.

Consecuencias del statu quo:

1. **El onboarding no alimenta nada.** `mood`, modos, prefs y "sobre vos" (la
   señal más rica: a qué se dedica, qué estudia/trabaja, para qué usa Ynara) no
   cruzan al backend, así que no pueden sembrar memoria ni personalización.
2. **Primeras recomendaciones vacías.** `GET /v1/suggestions` y `GET /v1/recap`
   se derivan **solo de la tabla `tasks`**
   ([`app/services/today.py`](../../../apps/backend/app/services/today.py)), sin
   leer memoria ni prefs → un usuario recién onboardeado y sin tareas ve
   `items=[]`.
3. **Contrato huérfano.** `OnboardRequestSchema`
   ([`packages/shared-schemas/src/user.ts`](../../../packages/shared-schemas/src/user.ts))
   describe el payload rico pero **no hay endpoint que lo reciba** (no existe
   `/v1/onboard`); se usa solo como gate de validación local en el FE.

Antes de tocar `apps/backend` (columnas nuevas + migración Alembic + memoria
SAGRADA) hace falta **congelar el contrato**: qué viaja, por qué endpoint, y
—la decisión de fondo— **dónde aterriza cada señal**. Es un cambio de contrato
compartido web + mobile + backend que sobrevive a la etapa, por eso va por ADR
(AGENTS regla #6; CONTRIBUTING "cambios arquitectónicos").

## Decisión

### 1. Endpoint dedicado `POST /v1/onboarding`

Un endpoint nuevo que recibe el intake completo, en vez de estirar
`PATCH /v1/users/me`. Razones:

- El intake mezcla **prefs operativas** (modos, a11y) con **contenido
  memory-bound** (mood, sobre-vos). Un recurso `users` con `extra='forbid'` no
  es el lugar para orquestar un seed de memoria.
- Un endpoint dedicado hace **una sola llamada idempotente** que: persiste las
  prefs operativas, marca `onboarding_completed=true`, y (cuando exista G4)
  dispara el seed de memoria.
- `PATCH /v1/users/me` sigue intacto para edits de perfil sueltos (nombre,
  retención, time_zone).

Auth: usa el **Bearer del draft** (el token del usuario recién registrado en el
step `auth`); requiere autenticación, igual que el `PATCH` actual del cierre.

### 2. Routing de cada señal (la decisión de fondo)

| Señal | Destino | Capa | Gate |
|---|---|---|---|
| `display_name` | `users.display_name` | operativo | ya existe |
| `interested_modes` | `users.preferences` (JSONB) | **operativo** | migración Alembic → aprobación humana |
| `a11y` | `users.preferences` (JSONB) | **operativo** | idem |
| `mood` + `mood_free_text` | `semantic` (hecho free-text: ánimo inicial) | **memoria** | 🔴 SAGRADO (regla #3) |
| sobre-vos (`about`) | `semantic` (hechos: estudia/trabaja/propósito/intereses) + opcional `procedural` (dedicación) | **memoria** | 🔴 SAGRADO (regla #3) |

Criterio: **operativo = "cómo configuro la app para este usuario"** (modo
preferido, tamaño de texto) → tabla `users`. **Memoria = "quién es el usuario"**
(qué le pasa, qué estudia, qué le importa) → stores de memoria, que es de donde
saldrán las recomendaciones memory-aware.

Para las prefs operativas se propone **una columna `preferences` JSONB** en
`users` (no una columna por pref): evita N migraciones a futuro y la forma la
fija el contrato Pydantic, no el schema SQL.

El seed de memoria reusa las **primitivas existentes**
(`ProceduralMemoryStore.upsert`, `SemanticMemoryStore.add`,
`AuditStore.record`), así que **no requiere migración del schema sagrado** —
pero igual toca `app/memory/` y la lógica de memoria, así que es un **PR aparte
con tests + 1 aprobación humana explícita** (regla #3). `source_session_id=NULL`
(no hay `ChatSession`) y un **marcador de origen de audit nuevo** (no `QWEN`, no
owner-edit) para distinguir el seed del onboarding.

### 3. Shape del contrato (Pydantic gana, Zod sigue; snake_case en el wire)

```
POST /v1/onboarding            (auth: Bearer del draft)

OnboardingIntake {
  display_name:      str            (max 40)
  interested_modes:  Mode[]         (>= 1; Mode = enum de @ynara/shared-schemas)
  a11y: {
    text_size:       "sm" | "md" | "lg"
    high_contrast:   bool
    motion:          "auto" | "reduce" | "normal"
  }
  mood:              str[]          (<= 2)
  mood_free_text:    str | null     (<= 160)
  about: {                          # "sobre vos" — null si lo saltó entero
    dedication:      "estudio" | "trabajo" | "ambos" | "otro" | null
    study_what:      str
    work_what:       str
    purpose:         str
    interests:       str
  } | null
}

Response 200: UserOut   (onboarding_completed=true)
              # opcional: + { seeded: { semantic: int, procedural: int } }
```

- El **mirror Pydantic** (fuente de verdad) vive en `apps/backend/app/schemas/`
  (p.ej. `OnboardingIntake`); el **Zod** en `packages/shared-schemas` se realinea
  a este shape (snake_case) y **deprecca** el `OnboardRequestSchema`/`OnboardResponseSchema`
  camelCase huérfano.
- `about` va anidado en el wire (claridad); el FE mapea desde sus campos planos
  del draft (`dedication`/`studyWhat`/…).

### 4. Idempotencia

Re-llamar el endpoint (re-onboarding) hace **upsert** de las prefs operativas y
**no duplica** memoria: `procedural` por `key`, `semantic` con dedupe por hash.
Esto lo garantiza la implementación (G2/G4), el contrato solo lo habilita.

## Consecuencias positivas

- El onboarding deja de tirar datos: las señales cruzan al backend y quedan
  listas para personalización y **primeras recomendaciones** reales.
- Separa lo **operativo** (rápido, no sagrado) de lo de **memoria** (sagrado,
  gateado) → se puede entregar la primera mitad sin esperar la aprobación de la
  segunda.
- Endpoint dedicado e idempotente: re-onboarding y recuperación de errores
  quedan bien definidos, sin estirar `users`.
- Contrato único espejado (Pydantic/Zod) → mata el `OnboardRequestSchema`
  huérfano.

## Consecuencias negativas

- Columna `preferences` nueva + migración Alembic (aprobación humana por
  migración).
- El seed de memoria es **sagrado y no trivial** (dedup, audit con origen nuevo,
  decay) → PR propio, con tests y aprobación.
- Más superficie de API (`POST /v1/onboarding` además del `PATCH`).

## Mitigaciones

- **Fasing**: operativo primero (G2), memoria como PR aparte gateado (G4) — la
  decisión de contrato no fuerza tocar memoria de una.
- El seed reusa primitivas existentes → **sin migración del schema sagrado**.
- Contrato espejado y `Mode` ya compartido (`@ynara/shared-schemas`) → el FE
  cablea contra una sola fuente.

## Alternativas descartadas

- **Estirar `PATCH /v1/users/me`.** Mezcla perfil con contenido memory-bound y
  `extra='forbid'` + un solo recurso no orquesta el seed. Descartada.
- **Una columna por pref (`interested_modes`, `text_size`, …).** Rígido: una
  migración por pref nueva. Se prefiere `preferences` JSONB.
- **Mandar TODO a memoria (incluidos modos y a11y).** Modos/a11y son
  **operativos**, no "quién es el usuario"; meterlos en `semantic` ensucia el
  recall. Descartada.
- **Seguir client-side (statu quo).** No alimenta memoria ni recomendaciones;
  es justamente el problema que este ADR destraba.

## Notas de implementación (fuera del alcance de la decisión)

Este ADR **congela el contrato**, no el orden de ejecución. El roadmap por fases
(de la auditoría web jun-2026, [`web-audit-2026-06-findings`]):

- **G1 (este ADR)** — fija el contrato.
- **G2** — `users.preferences` (JSONB) + `POST /v1/onboarding` que persiste prefs
  operativas y marca `onboarding_completed`. **Migración Alembic → aprobación
  humana.**
- **G3** — hidratar `me` en el FE (cargar prefs/retención reales; hoy `TuView`
  hardcodea retención `365`).
- **G4** — seed de memoria desde el intake (`semantic`/`procedural`). **Toca
  `app/memory/` → regla #3: tests + 1 aprobación humana, PR aparte.**
- **G5** — `suggestions`/`recap` leen prefs/memoria → **primeras
  recomendaciones** aunque no haya tasks.
- **G6** — el FE cablea el intake completo a `POST /v1/onboarding`
  (`useCompleteOnboarding`/`submitOnboarding`, hoy en `@ynara/core`) en vez de
  mandar solo `display_name`.

No se documenta el endpoint en
[`apps/backend/docs/ENDPOINTS.md`](../../../apps/backend/docs/ENDPOINTS.md)
todavía: el endpoint no existe y hay un drift guard de catálogos en CI. Se
agrega cuando G2 lo implemente.
