# Ynara · sitio

Experiencia web inmersiva para **Ynara** — el asistente personal adaptativo con
memoria propia (tesis Da Vinci 2026). No es una página de secciones: es **un objeto
vivo de luz** que se transforma mientras se recorre.

## La idea

Una sola **forma generativa 3D** (WebGL) persiste de principio a fin y **morfea con
el scroll** a través de 8 capítulos — olas de luz → red de puntos → plenitud. La
tipografía masiva entra como voz. Paleta de marca _locked_: el drama nace del
contraste de valor, la escala y el movimiento, no de colores nuevos.

## Stack

Next.js 16 (App Router) · React 19 · TypeScript · Tailwind v4 · three.js 0.164 ·
GSAP 3.12 (ScrollTrigger + SplitText) · Lenis · Biome.

## Arquitectura

```
src/
  app/                  layout (Field persistente) · page · SEO (robots, sitemap, OG)
                        · /presentacion (deck, layout propio) · /lab (sandbox de dev)
  components/
    field/              LA FORMA y su motor (home)
      CascadeField.tsx  terreno de luz WebGL (PlaneGeometry muy subdividido + shaders
                        simplex-noise Ashima, morfeo por scroll, mouse reactivo)
      Field.tsx         canvas fija detrás de todo + base void + grano
    journey/            los capítulos de home tejidos sobre la forma
    deck/               motor del deck de tesis (30 láminas) + living-field/ (motor
                        WebGL propio del deck, separado de CascadeField)
    motion/             Magnetic, RevealText — primitivos de animación
    ui/ site/           primitivos (YnaraMark, SiteNav, SiteFooter, Button…)
  content/              banco de copy — ynara.ts (home), deck.ts (deck)
  lib/                  cn.ts, motion.ts, reveal.ts, useDeckRoute.ts
```

El scroll no mueve cajas: **transforma la forma y el tipo**. `CascadeField` es el
corazón WebGL de home — `PlaneGeometry` muy subdividido con `RawShaderMaterial`
(simplex-noise Ashima), conducido por el scroll de la página vía ScrollTrigger y
montado por `Field` detrás de todo. Los capítulos viven en `components/journey/*`.
El deck de tesis (`/presentacion`) corre su propio motor WebGL
(`components/deck/living-field/`), independiente de `CascadeField`. Reglas y mapa
completo en [`AGENTS.md`](./AGENTS.md).

## Desarrollo

```bash
pnpm dev        # http://localhost:3000
pnpm build      # build de producción
pnpm typecheck  # tsc --noEmit
pnpm lint       # biome
```

## Calidad

a11y AA (reduced-motion = frame estático + contenido completo, scrims de legibilidad,
foco visible, semántica), perf (DPR cap, pausa fuera de viewport, dispose, malla
liviana en mobile), SEO (metadata + JSON-LD + OG + sitemap/robots), responsive real.
