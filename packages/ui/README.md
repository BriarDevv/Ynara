# @ynara/ui

Fundaciones de UI **realmente compartibles** entre `apps/web` y
`apps/mobile`: lo portable y RN-compatible (íconos, presets de motion).
Los primitives web-only (Button, Card, TextField, etc.) **no** viven
acá — viven en `apps/web/src/components/ui/` (ver `DESIGN.md` §11).

## Wiring (cómo se consume)

Se publica como **TS/TSX source**, sin build step: `main`/`types`/
`exports` apuntan a `./src/index.ts`. No hay `dist`. `apps/web` lo
declara como `"@ynara/ui": "workspace:*"` y lo importa con
`import { ... } from "@ynara/ui"`.

Verificado end-to-end (con un componente TSX de smoke, después revertido):

- **TypeScript** lo resuelve por el `exports` del package (`tsc --noEmit`
  verde en `@ynara/ui` y `@ynara/web`).
- **Next (Turbopack)** transpila el workspace source automáticamente en
  `next build` — **no requiere `transpilePackages`** (mismo trato que
  `@ynara/shared-schemas`, que ya se consume así). *Caveat:* si el build
  alguna vez cae a webpack, habría que agregar
  `transpilePackages: ["@ynara/ui"]` en `apps/web/next.config.ts`.
- **Vitest** lo resuelve con un alias explícito a `src/index.ts` en
  `apps/web/vitest.config.ts` (mismo patrón que `@ynara/shared-schemas`):
  resolución determinista a la fuente, sin depender del symlink de pnpm.

## Íconos (`src/icons/`) — DESIGN.md §9

Set propio con el ADN de los elementos: **trazo uniforme + el diamante
como acento**. 10 íconos de marca (`idea`, `conexion`, `memoria`, `nota`,
`buscar`, `dialogo`, `recordatorio`, `adaptacion`, `foco`, `red`) con la
geometría **literal** de la guía de identidad visual (lámina 08), más 5
utilitarios (`enviar`, `detener`, `atras`, `cerrar`, `chevron`) diseñados
en la misma grilla `44×44` y trazo. Reemplazan los "tells" de flechas
`→ ← ↓` como íconos.

```tsx
import { Icon } from "@ynara/ui";

<Icon name="enviar" />                 // decorativo (aria-hidden)
<Icon name="buscar" title="Buscar" />  // accesible (role=img + aria-label)
<Icon name="foco" size={32} color="var(--color-accent)" />
```

La geometría vive como **data** (`registry.ts`), no como JSX: es la capa
portable. El renderer web (`Icon.tsx`) la traza con `<svg>`; un renderer
RN futuro mapea las mismas formas a `react-native-svg` sin tocar la data.
El color sale de `currentColor` por defecto (sin hex hardcodeado).

> **Fallback Lucide** (DESIGN.md §9): para utilitarios que el set propio
> no cubra todavía, se puede sumar Lucide manteniendo el mismo grosor de
> trazo. Pendiente (no se agregó la dep en este PR).

## Motion (`src/motion/`) — DESIGN.md §8

**Valores** compartidos, sin atar una librería (decisión F0.4:
**CSS-first**, sin Framer Motion). Los springs usan el modelo perceptual
`visualDuration` + `bounce` (§8.1), consumible por Motion (web) o
Reanimated (mobile) cuando una animación compleja lo necesite.

```ts
import { SPRING_SNAPPY, SPRING_SOFT, DURATION, EASE_OUT_SOFT } from "@ynara/ui";
```

- `SPRING_SNAPPY` / `SPRING_SOFT` — presets de spring.
- `DURATION` — duraciones en ms (espejo de `--duration-*`).
- `EASE_OUT_SOFT` — puntos de la curva (espejo de `--ease-out-soft`).

Los helpers **web** viven en `apps/web` (no son portables): el hook
`useReducedMotion` (deriva del store de a11y + `prefers-reduced-motion`,
espejando la cascada de `globals.css`) y `startViewTransition` (View
Transitions con progressive enhancement + respeto de reduced-motion).

## Convención

- Componentes presentacionales, sin lógica de dominio.
- Re-export selectivo desde `src/index.ts` (sin barrel monstruo).
- **RN-compatible**: nada de APIs sólo-DOM en el código compartido. La
  capa de SVG usa `<svg>` en web y se porta a `react-native-svg` en
  mobile cuando ese consumidor exista.
- shadcn/ui se copia con `npx shadcn add` directo en
  `apps/web/src/components/ui/`, no acá.

## Histórico

- El subsistema `graphics/` (`MemoryField`, `GrainOverlay`,
  `buildMemoryField`) vivió en este package durante la fase F0.3 del
  rediseño y se deprecó al migrar la app al **lenguaje sobrio**
  (PRs #139–#147). El recurso ambiental actual es `LivingField`, el
  fondo vivo en canvas del sistema v4 (vive en
  `apps/web/src/components/ui/`; DESIGN.md §2).
