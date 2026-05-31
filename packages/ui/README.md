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

## Convención

- Componentes presentacionales, sin lógica de dominio.
- Re-export selectivo desde `src/index.ts` (sin barrel monstruo).
- **RN-compatible**: nada de APIs sólo-DOM en el código compartido. La
  capa de SVG usa `<svg>` en web y se porta a `react-native-svg` en
  mobile cuando ese consumidor exista.
- shadcn/ui se copia con `npx shadcn add` directo en
  `apps/web/src/components/ui/`, no acá.
</content>
