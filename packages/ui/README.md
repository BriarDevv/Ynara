# @ynara/ui

Fundaciones de UI **realmente compartibles** entre `apps/web` y
`apps/mobile`: lo portable y RN-compatible (íconos, sistema gráfico "Red
de memoria", grano). Los primitives web-only (Button, Card, TextField,
etc.) **no** viven acá — viven en `apps/web/src/components/ui/`
(ver `DESIGN.md` §11).

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

## Sistema gráfico (`src/graphics/`) — DESIGN.md §2 / §3.6

El rasgo más ownable de la marca: la **"Red de memoria"** como recurso de
profundidad/ambiente (reemplaza al gradiente genérico).

- **`MemoryField`** — fondo SVG de nodos + vínculos curvos + diamantes
  (acento). Props `density` (dispersa/media/densa), `variant`
  (clara/nocturna) y `seed`. Llena su contenedor (`width/height 100%` +
  `preserveAspectRatio="slice"`); envolverlo en un contenedor posicionado.

  ```tsx
  import { MemoryField } from "@ynara/ui";

  <div style={{ position: "relative", overflow: "hidden" }}>
    <MemoryField density="dispersa" variant="nocturna" />
    {/* contenido encima */}
  </div>
  ```

  La geometría vive como data **determinista** (`field.ts`, PRNG sembrado,
  sin `Math.random`/`Date`): idéntica en server y cliente (no rompe la
  hidratación SSR) y estable entre builds. Es la capa portable; el
  renderer web la dibuja, RN mapeará las mismas formas a `react-native-svg`.
  Colores siempre por tokens de la rampa de memoria (sin hex). Estático
  (sin loops, §2.5).

- **`GrainOverlay`** — capa de grano que envuelve el utility `.bg-grain`
  de `globals.css`. **Web-first**: depende de esa clase global (pseudo-
  elemento), que no existe en RN → para mobile necesita otra estrategia
  (imagen/SVG de ruido), TODO al llegar ese consumidor.

## Convención

- Componentes presentacionales, sin lógica de dominio.
- Re-export selectivo desde `src/index.ts` (sin barrel monstruo).
- **RN-compatible**: nada de APIs sólo-DOM en el código compartido. La
  capa de SVG usa `<svg>` en web y se porta a `react-native-svg` en
  mobile cuando ese consumidor exista.
- shadcn/ui se copia con `npx shadcn add` directo en
  `apps/web/src/components/ui/`, no acá.
