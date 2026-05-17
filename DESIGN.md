# Sistema de Diseño de Ynara

Este archivo es la fuente de verdad del sistema visual de Ynara. Lo
completa el equipo de diseño cuando esté cerrada la identidad visual.

Mientras tanto, el desarrollo frontend debe usar tokens neutrales
genéricos de Tailwind sin hardcodear colores ni tipografías
específicas, así la migración a tokens finales es trivial.

## Paleta

<!-- TODO: completar con la paleta final de Ynara -->

- Primary: TODO
- Secondary: TODO
- Background: TODO
- Foreground: TODO
- Accent: TODO
- Muted: TODO

## Tipografías

<!-- TODO: completar con las tipografías finales -->

- Display (títulos): TODO
- Body (cuerpo): TODO
- Mono (código): TODO

## Tokens

<!-- TODO: definir tokens CSS en globals.css -->

Los tokens viven en `apps/web/src/app/globals.css` como variables CSS.
Tailwind v4 los consume con `@theme`.

## Reglas visuales

- Contraste mínimo WCAG AA, target AAA en textos críticos.
- Respetar `prefers-reduced-motion`.
- Mobile-first en todo.
- Sin estética infantil.
- Tono: TODO (sobrio / cálido / profesional / juvenil — definir).

## Movimiento

<!-- TODO: definir patrones de animación con GSAP + Lenis -->

- Duración estándar: TODO ms
- Easing por defecto: TODO
- Componente que entra/sale: TODO

## Aprobación

Este archivo se considera "vivo" hasta que el equipo lo apruebe en una
reunión específica. Cualquier cambio requiere PR con aprobación de
@MateoGs013 (CODEOWNER del archivo).
