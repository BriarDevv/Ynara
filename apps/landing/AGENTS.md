# apps/landing/AGENTS.md — Reglas del sitio institucional

> Fuente canónica del repo: [`../../AGENTS.md`](../../AGENTS.md) (10 reglas
> no negociables). Acá solo reglas y mapa específicos de este app.

## 0. Qué es `apps/landing` (y qué NO es)

Es el **sitio institucional de Ynara**: una experiencia web inmersiva WebGL
(three.js) construida para la tesis de Mateo (Da Vinci 2026) — home pública
(scrollytelling de 8 capítulos) + [`/presentacion`](./src/app/presentacion)
(deck de 30 láminas para la defensa ante jurado). El brief creativo completo
(dirección de arte, paleta LOCKED, referencias técnicas exactas, spec del
shader) vive en [`REBUILD-BRIEF.md`](./REBUILD-BRIEF.md) — **leerlo entero**
antes de tocar la forma WebGL o la tipografía.

**No es `apps/web`.** No es el producto: no hay chat, no hay auth, no hay
memoria, no consume la API de FastAPI ni ningún backend (verificado: cero
`process.env` / `fetch` a servicios propios o de terceros en `src/`). Es
marketing + material de tesis, self-contained. Comparte identidad de marca
con el resto del repo pero **no** comparte código ni tokens 1:1 con
`apps/web` (ver regla 3).

Este app llegó al monorepo importado desde un repo standalone
(`MateoGs013/Ynara-Web`, historia completa disponible en GitHub); el `.git`
anidado que traía se eliminó al integrarlo acá.

## 1. Reglas duras

1. **Sin cliente Supabase ni llamadas a APIs de IA externa** (reglas #4/#5
   del contrato global) — heredado por consistencia, aunque hoy este app no
   hace ningún fetch a servicios propios ni de terceros. Si en algún momento
   necesita datos reales, pasa por FastAPI como cualquier otro frontend.
2. **TypeScript strict.** `tsconfig.json` extiende
   [`packages/config/tsconfig.base.json`](../../packages/config/tsconfig.base.json)
   (recién alineado — antes era standalone). Esto activa `noUnusedLocals` /
   `noUnusedParameters` / `noUncheckedIndexedAccess`, que el código heredado
   del repo original no corría: es esperable que aparezcan errores nuevos al
   correr `pnpm typecheck` acá por primera vez — arreglarlos es deuda
   pendiente, no un bug del tsconfig.
3. **Paleta de marca LOCKED, propia de este app.** Tokens en
   `src/app/globals.css`, definidos y cerrados en
   [`REBUILD-BRIEF.md` §3](./REBUILD-BRIEF.md). El drama visual sale de
   contraste de valor/escala/movimiento, **no** de sumar colores nuevos. Es
   el sistema de marca más desarrollado que existe en el repo hoy —
   `DESIGN.md` (root) sigue siendo placeholder — pero son sistemas
   **separados**: no asumas que son los mismos tokens que
   `apps/web/src/app/globals.css` hasta que haya una decisión humana de
   unificarlos.
4. **`prefers-reduced-motion` obligatorio en todo lo animado** (GSAP /
   ScrollTrigger, el shader de `CascadeField`, el deck). Reduced-motion =
   frame estático completo con el contenido entero, nunca contenido
   faltante.
5. **`/lab/*` son rutas de sandbox de desarrollo** (`field`, `horizontal`) —
   no están linkeadas desde la nav pública. Antes de un deploy a producción,
   confirmar si se excluyen del build o quedan como demo interna.

## 2. Arquitectura (`src/`)

```
src/
├── app/            App Router — home (page.tsx), SEO (robots/sitemap/OG/apple-icon),
│                   /presentacion (deck, layout propio) y /lab/* (sandbox: field, horizontal)
├── components/
│   ├── field/      CascadeField.tsx — motor WebGL de home (PlaneGeometry muy subdividido +
│   │               RawShaderMaterial, simplex-noise Ashima, morfeo por scroll) + Field.tsx (canvas fija)
│   ├── journey/    capítulos del scrollytelling de home (Hero, Problem, Trust, VoiceChapter,
│   │               HorizontalModes, Marquee, Closing)
│   ├── deck/       motor del deck de tesis (Deck.tsx, Slide.tsx, deck-context.ts) + 30 slides en
│   │               slides/ + subsistema propio living-field/ (shader de fondo del deck — climate/
│   │               config/model separados de CascadeField, NO es el mismo motor)
│   ├── motion/     Magnetic.tsx, RevealText.tsx — primitivos de animación
│   ├── site/       SiteNav.tsx, SiteFooter.tsx
│   └── ui/         YnaraMark.tsx, YnaraLockup.tsx, Button.tsx
├── content/        banco de copy — ynara.ts (voz rioplatense de home), deck.ts (contenido del deck)
└── lib/            cn.ts, motion.ts, reveal.ts, useDeckRoute.ts
```

`CascadeField` (home) y `living-field/` (deck) son **dos motores WebGL
separados**, cada uno con su propia lógica — no es el mismo componente
reusado. Si tocás uno, confirmá cuál es antes de generalizar entre ambos.

## 3. Convenciones

- **Rutas Next.js:** kebab-case (`/presentacion`, no acentos ni PascalCase).
- **Componentes:** `PascalCase.tsx`. Cada lámina del deck es `SlideNN.tsx` +
  `SlideNN.css` hermano cuando tiene estilos propios.
- **GSAP + Lenis** para todo el motion; nada de `useEffect` + listeners de
  scroll manuales.
- **Biome:** `apps/landing/biome.json` extiende el root
  (`../../biome.json`, mismo patrón que `packages/core/biome.json`) con un
  único override propio: `noImgElement: off` en
  `components/deck/slides/**` (las láminas usan `<img>` directo para las
  piezas promocionales reales — fotos de eventos/objetos/vía pública — sin
  pasar por el pipeline de `next/image`).

## 4. Calidad (innegociable — ver [`REBUILD-BRIEF.md` §10](./REBUILD-BRIEF.md))

a11y AA (reduced-motion = frame estático, scrims de legibilidad, foco
visible, semántica), perf (DPR cap, pausa del WebGL fuera de viewport,
dispose en cleanup, malla liviana en mobile), SEO (metadata + JSON-LD + OG +
sitemap/robots ya armados en `app/`), responsive real.

## 5. Dev

```bash
pnpm dev        # http://localhost:3000
pnpm build      # build de producción
pnpm typecheck  # tsc --noEmit
pnpm lint       # biome check .
```

Sin tests unitarios ni E2E propios todavía (TODO). Sin CI propia: ni
`ci-web.yml` ni `ci-admin.yml` cubren `apps/landing/**` — correr
lint/typecheck/build a mano antes de cada PR hasta que se sume un workflow
dedicado. Sin `.env`/`.env.example`: hoy no hay ninguna variable de entorno
que configurar (nada de `process.env`/`NEXT_PUBLIC_*` en `src/`).

## 6. Docs

| Doc | Para qué |
| --- | --- |
| [`README.md`](./README.md) | Quickstart humano — qué es, stack, arquitectura resumida. |
| [`REBUILD-BRIEF.md`](./REBUILD-BRIEF.md) | Fuente de verdad creativa: dirección de arte, paleta LOCKED, referencias técnicas exactas (infinitefield/tiwis), spec del shader, estructura de capítulos. Leer completo antes de tocar la forma WebGL. |
