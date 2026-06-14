# ADR-012: Código compartido web/mobile vía packages/core

## Estado
Aceptado

## Fecha
2026-06-13

## Contexto

`apps/mobile` existe hoy solo como scaffold (Expo Router + NativeWind,
sin pantallas). `apps/web` (Next.js 16) ya tiene implementadas las
vistas núcleo del producto: onboarding, chat con streaming, hoy,
memoria, búsqueda. El objetivo de esta etapa es llevar esas vistas a
mobile para tener una app usable en un dispositivo real.

El problema no es portar la UI (eso es trabajo de implementación, sin
decisión arquitectónica: la UI web usa HTML/CSS y la mobile usa
primitivos React Native + NativeWind, se reescribe). El problema es la
**lógica no visual**, que hoy vive secuestrada dentro de
`apps/web/src/` y que web y mobile necesitan por igual:

- Stores de Zustand (`stores/user.ts`, `stores/a11y.ts`,
  `features/chat/store.ts`, `features/onboarding/store.ts`).
- Hooks de data con TanStack Query (`features/today/api.ts`,
  `features/onboarding/hooks/*`, lógica de orquestación de
  `features/chat/useChatStream.ts`).
- Cliente HTTP (`lib/api.ts`) y factory de query keys
  (`lib/queryKeys.ts`).

Esta lógica es platform-agnostic en su mayoría, pero está acoplada a
runtimes específicos de web en tres puntos concretos:

1. **Storage del `persist` de Zustand**: usa `localStorage` (web). En
   mobile, los tokens JWT van obligatoriamente a `expo-secure-store`
   (regla #5 de `apps/mobile/AGENTS.md`), no a `localStorage` ni
   `AsyncStorage`.
2. **Token provider del cliente API**: `lib/api.ts` lee el token vía
   `useUserStore.getState().token` (import directo al store de web).
3. **Transporte del streaming SSE del chat**: web usa `fetch` +
   `ReadableStream`; mobile usa `expo/fetch`. El *parser* del wire SSE
   ya está compartido y desacoplado en `packages/shared-schemas`
   (`createSseParser`), con nota explícita de que el transporte difiere
   por plataforma. Lo que falta desacoplar es solo el transporte.

Los packages compartidos que ya existen y están sancionados
(`packages/shared-types`, `packages/shared-schemas`,
`packages/ui`, `packages/config` — ver ADR-001) cubren tipos, schemas
Zod y config de tooling, pero **no** lógica de aplicación (stores,
hooks, cliente HTTP). No hay hoy un lugar bendecido para esa capa.

Hay dos formas de resolverlo, y elegir una es una decisión de
estructura del monorepo que sobrevive a esta etapa, por eso amerita
ADR (AGENTS regla #6 extendida, CONTRIBUTING "cambios
arquitectónicos").

## Decisión

Crear un package nuevo `packages/core` (`@ynara/core`) que aloje la
lógica de aplicación platform-agnostic compartida entre web y mobile.
La asimetría de plataforma se resuelve con **inyección de
dependencias**, no con ramas `if (platform)` adentro de core:

- **Stores**: core exporta *factories* (`createUserStore(storage)`,
  `createA11yStore(storage)`, etc.) que reciben el `StateStorage` de
  Zustand. Web instancia con `localStorage`; mobile con un adapter de
  `expo-secure-store`.
- **Cliente API**: core exporta el cliente con `configureApi({ baseUrl,
  getToken })`. Cada app cablea su `getToken` (web desde su store,
  mobile desde el suyo) y su `baseUrl` (web `NEXT_PUBLIC_API_URL`,
  mobile `EXPO_PUBLIC_API_URL`). Core no importa ningún store.
- **Transporte SSE**: la orquestación del chat (manejo del store,
  estados del mensaje) vive en core; el transporte (`openStream`) se
  inyecta. Web inyecta el de `fetch`/`ReadableStream`, mobile el de
  `expo/fetch`. El parser sigue en `shared-schemas`.

Para no duplicar y para que la web no regrese, **web pasa a
re-exportar desde `@ynara/core`** (ej: `apps/web/src/lib/queryKeys.ts`
queda como `export { qk } from "@ynara/core/query-keys"`). La
migración es incremental, un módulo por commit, con la suite de tests
de web verde después de cada paso como red de seguridad.

`packages/core` depende de `@tanstack/react-query`, `zustand`, `zod`,
`@ynara/shared-types` y `@ynara/shared-schemas`. No depende de Next.js,
React DOM, Expo ni react-native: es el subconjunto que corre en
cualquiera de las dos plataformas.

## Consecuencias positivas

- Una sola fuente de verdad para stores, hooks y cliente HTTP: un bug
  arreglado o un endpoint nuevo sirve a web y mobile en un PR.
- La web no se rompe: re-exporta desde core, los imports `@/lib/...`
  siguen funcionando, los tests de web son la red de seguridad de la
  extracción.
- Respeta las reglas del repo: la lógica de auth/data sigue pegando a
  FastAPI (regla #4/#5), el token va a SecureStore en mobile (regla #5),
  el parser SSE compartido no se duplica.
- Coherente con ADR-001 (monorepo para compartir TS strict sin
  overhead de publicación): `packages/core` es el lugar natural para la
  capa de aplicación compartida que ADR-001 anticipa pero no nombra.

## Consecuencias negativas

- Costo inicial: extraer y re-cablear web antes de escribir una sola
  pantalla de mobile. La inyección de dependencias agrega indirección
  (factories, `configureApi`) frente a imports directos.
- Otro package en el grafo de Turborepo: hay que mantener sus
  `exports`, su `tsconfig` y su lugar en `pnpm-workspace.yaml`.
- Riesgo de meter en core algo platform-specific por descuido (ej: un
  import de `next/navigation`). Mitigación abajo.

## Mitigaciones

- `packages/core` no declara `next`, `react-dom`, `expo` ni
  `react-native` como dependencias: un import de plataforma rompe el
  typecheck del package, lo que actúa de guardia.
- Extracción incremental con `pnpm --filter @ynara/web test &&
  typecheck` verde por commit. Si un módulo no sale limpio, se revierte
  ese commit sin arrastrar al resto.
- La navegación (web `next/navigation`, mobile `expo-router`) NO entra
  a core: se inyecta como callback desde cada app.
- **Boundary-check acotado a `packages/core`**: regla
  `no-restricted-imports` (vía override de Biome en el propio
  `packages/core`, no global) que prohíbe importar `next`, `next/*`,
  `react-dom`, `expo`, `expo-*` y `react-native` dentro de core. El
  check corre solo sobre `packages/core` —no sobre el resto del
  monorepo— para no interferir con web ni mobile. Un import de
  plataforma rompe el lint de core de forma mecánica, no por revisión
  humana.

## Alternativas descartadas

- **Duplicar la lógica dentro de `apps/mobile`**: portar a mano stores,
  hooks y cliente API a `apps/mobile/src`. Arranca más rápido y no
  toca la web, pero crea dos copias que divergen con cada cambio de
  contrato del backend; contradice el espíritu de ADR-001 (compartir,
  no duplicar). Descartada salvo que `packages/core` resulte
  inviable en la práctica.
- **Dejar la lógica en `apps/web` e importarla desde `apps/mobile`**:
  haría que mobile dependa del package de una app (no de un package
  compartido), arrastrando dependencias de Next.js al grafo de mobile.
  Rompe la separación apps/packages del monorepo. Descartada.
- **Meter la lógica de aplicación en `packages/ui`**: `packages/ui` es
  para componentes UI realmente compartibles (ADR-001 / Repo Map), no
  para stores ni cliente HTTP. Mezclaría responsabilidades. Descartada.

## Notas de implementación (fuera del alcance de la decisión)

- NativeWind sigue sobre Tailwind 3 en mobile (landmine de
  AI-GUIDELINES); los design tokens se espejan a mano desde
  `apps/web/src/app/globals.css`. Esto no toca `packages/core`.
- `next-auth` (ADR-006) es web-only y no se porta: mobile hace auth
  manual contra `/v1/auth/*` con el token en SecureStore.
- El detalle táctil de la migración (orden de fases, pantallas para la
  demo) vive como plan de trabajo aparte, no en este ADR.
