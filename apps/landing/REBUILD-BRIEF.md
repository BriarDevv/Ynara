# YNARA · Brief de rebuild — Experiencia WebGL inmersiva (v2, desde cero)

> **Qué es esto:** la fuente única de verdad para reconstruir el sitio de Ynara
> de cero, sin la deuda de la v1 (que quedó "sobria" y parcheada por reacción).
> Cualquiera que construya —agente o humano— ejecuta ESTO, coherente, de una.
> Escrito por Eros (director creativo) tras analizar el código fuente de las
> referencias y varias rondas de feedback con Mateo.

> **Nota de implementación (estado actual):** el motor WebGL implementado es
> **CascadeField.tsx** — técnica infinitefield completa: `PlaneGeometry` muy
> subdividido + `RawShaderMaterial` con simplex-noise Ashima, morfeo por scroll
> vía ScrollTrigger, mouse reactivo. Montado por `Field.tsx` detrás de todo.
> Los capítulos viven en `components/journey/*`.
> LightForm.tsx, fieldState.ts, RibbonField.tsx y Constellation.tsx fueron
> descartados durante el desarrollo y ya no existen en el repositorio.

---

## 0. El veredicto en una frase

> **Ynara no es una página: es un objeto vivo de luz que se transforma mientras
> lo recorrés.** Una sola forma generativa 3D domina la pantalla y morfea con el
> scroll (alma infinitefield), con tipografía masiva como voz (alma tiwis), en la
> paleta locked de la marca — donde el drama nace del CONTRASTE DE VALOR, la
> ESCALA y el MOVIMIENTO, no de colores nuevos.

Norte: nivel Awwwards. Si una decisión se siente "prolija pero segura", está mal.

---

## 1. Qué es Ynara (contexto, no negociable)

Asistente personal adaptativo con **memoria propia, on-prem** (modelos Gemma+Qwen),
para estudiantes y jóvenes profesionales de LATAM. **Una sola presencia** que
reemplaza la dispersión de apps. Diferencial: integra las **3 capas que nadie
cruza** — productividad + memoria + bienestar. **5 modos** (productividad, estudio,
bienestar, vida, memoria) que se activan solos por contexto. Tagline: _"La única
presencia que necesitás."_ / _"Pensar mejor, recordar siempre."_ Es la **tesis de
Mateo** (Da Vinci 2026) — alto impacto, se va a defender ante jurado.

Etimología (presentar con honestidad, no como dato duro): _Ynara_ = construcción
de marca inspirada en raíz celta "uno/único" (cf. óen, un) + sufijo -ara de
presencia. NO afirmar reconstrucciones filológicas como hechos (evitar "*aen-" con
asterisco como si fuera atestiguado; evitar el ejemplo "Sara" que es hebreo).

---

## 2. Lo que Mateo QUIERE — y lo que NO (feedback real)

**Quiere (las 4 a la vez):**
- **WebGL/3D dominante** — el 3D es EL protagonista, no un fondo tímido.
- **Contraste / drama** — impacto visual a lo infinitefield/tiwis.
- **Experiencia continua** — un viaje, no una sucesión de secciones-caja.
- **Interactividad alta** — reacciona muchísimo a mouse y scroll; se siente vivo.

**Evitar (errores cometidos en v1):**
- Sobrio / minimalista / "sereno" → lee como vacío. NO.
- Formas generativas tímidas de fondo (nodos sutiles, partículas apenas visibles).
- Olas/superficies **geométricas y filosas** → tienen que ser **orgánicas, armoniosas**
  (ruido de baja frecuencia, malla muy subdividida, amplitud gentil).
- Bajo contraste que mata la legibilidad del texto (el manual manda **claridad**).
- **Cursor roto:** NO aplicar `cursor: none` sin un custom-cursor 100% confiable y
  con fallback garantizado. Si hay dudas → cursor nativo.
- Construir por parches reactivos. Acá se ejecuta el brief completo y coherente.

---

## 3. Marca LOCKED (estricto — el manual manda)

Paleta cerrada. El drama sale del VALOR, no de sumar colores.

| Rol | Token | Valor |
|---|---|---|
| Void (fondo, casi negro) | `--void` | `#0a0c12` |
| Navy (superficie nocturna) | `--navy` | `#242C3F` |
| Marfil (texto/luz) | `--ivory` | `#F3F0EA` |
| Paper (ivory canvas claro) | `--paper` | `#FAF9F5` |
| **Azul plano — ÚNICO acento** | `--blue` | `#2F5AA6` (hover `#26498A`) |
| Azul brillante (glow/highlight) | `--blue-bright` | `#4B7EE6` |
| Periwinkle (acento 2º sobre oscuro) | `--acc` | `#8B9AD0` |

Gradientes por-modo (SOLO como tints de modo, nunca relleno): blue `#2F5AA6→#1F66DB`,
estudio `#4B7EE6→#7BA1F4`, bienestar/jade `#4A9C8C→#6FBFAE`, vida/ámbar `#D9A24A→#E8C77A`,
memoria/violeta `#8C63B8→#7C4FA3`. **Fuera de los modos, todo es azul + marfil + void.**

**Tipografía:** Space Grotesk (display, 500/600/700) + DM Sans (body, 400/500/600).
**Mark:** la "Y" de Ynara (figura con brazos + diamante de presencia). SVG en v1
(`YnaraMark`); idealmente extruido a 3D (.glb) para el rebuild.

**Estrategia de contraste DENTRO de la paleta (clave):** void casi-negro como base →
las crestas de luz azul y el texto marfil estallan por valor. Scrims oscuros detrás
del texto para legibilidad AA. La sobriedad se rompe con ESCALA + MOVIMIENTO +
luminosidad puntual, no con color.

**Voz (rioplatense, del tone-of-voice):** voseo, directa, sin tics de chatbot, sin
emojis, sin moralizar. Cita textual lo que recuerda. (Reusar el banco de copy de v1
— es bueno. Mateo dijo que el contenido le da igual y se puede cambiar.)

---

## 4. Referencias — técnicas EXACTAS (analizadas del código fuente)

### infinitefield.xyz (el alma generativa)
- **three.js v0.164** (ES modules). **Lenis + GSAP** (ScrollTrigger, SplitText, TextPlugin).
- `<canvas>` full-screen. WebGLRenderer + WebGLRenderTarget (render-to-texture).
- **El corazón:** un `PlaneGeometry` MUY subdividido + `RawShaderMaterial` con:
  - **Vertex:** simplex-noise 2D de Ashima (`snoise`), función `displacement(p)` =
    2 octavas de snoise moviéndose con `u_time` → olas fluidas. Desplaza z, calcula
    normales por diferencias finitas.
  - **Fragment:** colorea por altura/ruido, con ~10 uniforms que MORFEAN el look:
    `u_wave_slowed`, `u_wave_to_plane`, `u_dots_mask_visibility`, `u_dots_radius_grow`,
    `u_checks_to_pattern`, `u_grid_scale`, `u_wave_colored`, `u_wave_opacity`… →
    la MISMA malla pasa de **olas → plano → grilla de puntos → patrón de checks**.
  - **Bandas de luz** que fluyen por las crestas: `opacity_stripe = fract(.2*u_time + .12*vPos.y - .04*sin(.8*vPos.x))`.
  - `AdditiveBlending`, `DoubleSide`. Cámara perspectiva 45°. Logo 3D `.glb`.
- **Scroll = morfeo:** UN `mainSequence` (timeline GSAP) cuyo `progress` lo conduce
  UN ScrollTrigger (`onUpdate → mainSequence.progress(self.progress)`), scrubbeado,
  con **loop infinito** (wrap-around al llegar a 0/1). Los uniforms, la cámara y la
  rotación de la malla son tweens dentro de ese timeline.
- **El mouse NO toca el WebGL** (es 100% scroll-driven). ← para Ynara SÍ lo queremos
  interactivo al mouse (es un pedido explícito), así que sumamos perturbación por
  cursor además del morfeo por scroll.

### tiwis.fr (el alma tipográfica)
- **Webflow** + **GSAP 3.15** (SplitText para tipo masiva que se revela, ScrollTrigger,
  **Draggable + InertiaPlugin** para elementos arrastrables con el mouse) + **Lenis**.
- **UnicornStudio** (WebGL no-code) para el ambiente shader.
- Wordmark "TIWIS" gigante llenando el viewport. Wipes de panel blanco/contraste.

### La síntesis para Ynara
**Forma generativa 3D dominante que morfea con el scroll (infinitefield) + tipografía
masiva como voz (tiwis) + interactividad mouse/scroll fuerte, todo conducido por UN
master timeline scrubbeado.** El scroll no mueve cosas: TRANSFORMA la forma y el tipo.

---

## 5. La experiencia (estructura propuesta) — un viaje continuo

**Una sola forma de luz WebGL persiste de principio a fin y MORFEA por estados.** No
hay "secciones-caja": hay capítulos del mismo organismo. El contenido de la tesis se
teje como estados de la forma. Master timeline scrubbeado por scroll (Lenis+ScrollTrigger).

| # | Estado / capítulo | La forma hace | Tipo / contenido |
|---|---|---|---|
| 00 | **Génesis (preloader→hero)** | Del void, puntos de luz se ensamblan en la superficie fluida; emerge y respira | Mark se enciende → "La única **presencia** que necesitás." (masivo) |
| 01 | **El nombre** | La superficie se aquieta, fluye lento | Etimología honesta, escala editorial |
| 02 | **La intersección** ⭐ | La forma se separa en 3 corrientes (productividad/memoria/bienestar) que convergen y **encienden a Ynara** donde se tocan | "Vivís entre ocho apps. Ynara es una." + competidores |
| 03 | **Los 5 modos** | La forma cambia de comportamiento/tint por cada modo (sigue siendo azul dominante; el tint del modo es sutil) | Número gigante + nombre del modo masivo, secuencia |
| 04 | **Memoria** | La forma se vuelve **red de nodos/puntos de luz** (morfeo wave→dots, técnica infinitefield) | "Recuerda por vos. Con discreción, no con vigilancia." 3 capas |
| 05 | **La voz** | La forma se calma al mínimo | Conversación rioplatense que se escribe sola (mode-tinted) |
| 06 | **Precio** | La forma sostiene, serena | Free / Premium, restringido |
| 07 | **Cierre** | La forma alcanza su plenitud luminosa | Wordmark **YNARA** masivo + "Pensar mejor, recordar siempre." |

(Mateo confió la estructura a Eros. Esta es la propuesta; ajustable, pero el
principio "una forma continua que morfea" es la columna vertebral.)

---

## 6. Spec WebGL (el corazón — construir esto PRIMERO)

- **three.js**. Una superficie de luz: `PlaneGeometry` muy subdividido (≥300×190),
  desplazada por **simplex-noise de Ashima** en el vertex (2–3 octavas, **frecuencias
  BAJAS** → orgánico, no geométrico), `AdditiveBlending`, cámara perspectiva en
  ángulo (terreno/horizonte de luz). Bandas de luz fluyentes en las crestas.
- **Morfeo por scroll** (uniforms tweened en el master timeline): amplitud, escala/
  velocidad de ruido, **estado** (wave ↔ dots/red ↔ plano), brillo/valor, tint de modo.
- **Interactividad por mouse** (pedido explícito): el cursor perturba la forma —
  ripple/atracción/swell suave y ancho que sigue al puntero (no un bump filoso).
- **Contraste:** la forma vive sobre void `#0a0c12`; scrims oscuros detrás del texto
  para legibilidad. Azul/marfil luminoso sobre casi-negro = el drama de valor.
- **Perf:** `setPixelRatio(min(dpr,2))`, pausa con IntersectionObserver + `document.hidden`,
  dispose en cleanup. **Mobile:** versión más liviana (menos segmentos) o forma simplificada.
- **Reduced-motion:** render de UN frame estático hermoso (la forma quieta, igual impactante).
- **Mark 3D (deseable):** extruir el SVG del mark a `.glb` y sumarlo como objeto 3D
  con shader que rota/responde (como el logo de infinitefield).

---

## 7. Tipografía (alma tiwis)

- **Escala masiva** — el tipo es protagonista. Hero y cierre con wordmark/título que
  llena el ancho (clamp hasta ~18–22vw). Space Grotesk 700, tracking apretado.
- **SplitText / char reveals** sincronizados al scroll (máscaras, subida palabra/letra).
- **Wipes de panel** en transiciones de capítulo (contraste, no tintes tímidos).
- Legibilidad innegociable (scrims). El tipo marfil sobre void = contraste de valor.

---

## 8. Motion / interacción

- **Lenis** (smooth scroll) + **GSAP ScrollTrigger** + **SplitText**.
- **UN master timeline scrubbeado** conduce: uniforms de la forma + cámara +
  tipografía + transiciones (patrón infinitefield). El scroll = la línea de tiempo.
- **Mouse reactivo en todo:** la forma (perturbación), botones (magnético), parallax
  de profundidad por cursor. Opcional: un elemento arrastrable (Draggable/Inertia, tiwis).
- **Cursor:** custom SOLO si es bulletproof (visible siempre, blend-difference, z alto,
  sin spurious-hide) y con garantía de no dejar al usuario sin cursor; ante la duda → nativo.
- Easing: `power3.out` / `expo.out` / cubic-bezier(.22,1,.36,1). Reduced-motion: estado final, sin scroll-jack.

---

## 9. Stack técnico

Next.js 16 (App Router, `src/app`) · React 19 · TypeScript · **Tailwind 4** ·
**three.js ^0.164** · **GSAP + ScrollTrigger + SplitText** · **Lenis** · pnpm · Biome.
(Matchea el stack del equipo `BriarDevv/Ynara` + suma three.js para el WebGL.)

---

## 10. Calidad (innegociable — para la defensa)

- **a11y:** reduced-motion en TODO (forma estática), contraste AA (scrims, no text-muted
  flojo sobre la forma), navegación por teclado, skip-link, focus visible, headings semánticos.
- **Perf:** Core Web Vitals; pausar WebGL fuera de viewport; DPR cap; mobile liviano.
- **SEO:** metadata + **og:image** (next/og) + **JSON-LD** (Organization + SoftwareApplication
  con planes) + canonical + sitemap.ts + robots.ts + icon.
- **Responsive:** mobile real (forma simplificada, tipo fluida con clamp, sin pin pesado en touch).

---

## 11. Proceso recomendado (en este orden)

1. Scaffold (Next 16 + Tailwind 4 + three + GSAP + Lenis) + tokens del manual + fuentes.
2. **La forma WebGL primero** — es el corazón. Lograr que sea orgánica, luminosa,
   dominante y armoniosa ANTES de cualquier contenido. Screenshot-verificar.
3. El **master timeline de scroll** que la morfea por estados.
4. Tipografía masiva + escenas/capítulos tejidos sobre la forma.
5. Interactividad de mouse (perturbación de la forma, magnéticos, parallax).
6. Cadena de calidad (a11y, perf, SEO, responsive) + auditoría multi-agente.
7. **Verificar con screenshots en cada paso** (build → captura → comparación honesta
   contra las referencias; el screenshot no miente).

---

## 12. Activos que ya existen (reusar de la v1)

- Banco de copy en `src/content/ynara.ts` (voz rioplatense, secciones) — bueno, reusable.
- `YnaraMark` (SVG del mark, paths exactos) — base para el .glb.
- Tokens del manual (este doc + `apps/web/globals.css` del repo del equipo).
- Técnica de olas WebGL ya probada (`WebGLWaves.tsx` v1) — punto de partida del shader.
- Demo viva del producto (nocturna): el target de "feeling" del onboarding.

---

_Norte final: si al abrirlo no te detiene en seco y te dan ganas de scrollear solo
para ver qué hace la forma — todavía no llegamos. Inevitable o nada._
