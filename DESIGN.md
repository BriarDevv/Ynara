# Sistema de Diseño de Ynara

Este archivo es la **fuente de verdad del sistema visual de Ynara**. El código se
actualiza para matchear este doc, no al revés — los tokens reales viven en
[`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) y este doc es la
especificación legible que ese CSS debe implementar. Si hay divergencia, se
corrige el código.

> **Aprobación**: cualquier cambio sustantivo a este archivo requiere PR con review
> de @MateoGs013 (CODEOWNER). Para cambios que afecten identidad de marca (paleta,
> tipografía, sistema gráfico), revisar también con @BriarDevv y @querques20.

> **Estado — v3 (2026), lenguaje sobrio.** Esta versión documenta el sistema
> **realmente implementado** después de la serie de PRs #139–#148, donde la app
> migró al **lenguaje sobrio**: light-only, ivory canvas, ink-deep para titulares,
> azul plano de marca para CTA, sin sistema gráfico "Red de memoria" ni grano.
> Los cambios respecto a v2 se listan en el **§14 (deltas v2 → v3)**.
> Etiquetas: **[marca]** = literal de la guía 2026 · **[research]** = respaldado
> por evidencia · **[criterio]** = juicio de diseño · **[sobrio]** = decisión
> de la serie #139–#148.

---

## 1. Esencia de marca

> **"Tecnología que se siente como pensar."** Ynara no es una IA ruidosa: es una
> **compañía cognitiva diaria**. Su universo visual es **editorial y sereno — lo
> opuesto al cliché tecnológico.** [marca]

Esa última frase es la **regla rectora**: cada decisión visual se evalúa contra
"¿esto se siente editorial y sereno, o se siente como un template de SaaS generado
por IA?". Tres ideas gobiernan el sistema [marca]:

| Idea | Forma | Significado |
|---|---|---|
| **Memoria** | Nodos y puntos de luz | Cada idea/recuerdo capturado. La unidad mínima. |
| **Conexión** | Vínculos e hilos | El tejido que une un pensamiento con el siguiente. |
| **Presencia** | El diamante | Foco y claridad en la profundidad. El acento que ordena. |

Atributos operativos que la UI debe respirar siempre:

- **Claridad** — jerarquía visual obvia (por peso y contraste, no solo tamaño),
  copy directo con voz, sin ruido decorativo.
- **Calma** — espacio para respirar, contrastes que no agreden, motion que acompaña
  y nunca distrae.
- **Profundidad** — atmósfera construida con el sistema gráfico geométrico (§2) y la
  superficie marfil/nocturna; gradientes como ambiente contenido, jamás como relleno.

Lo que la UI **no es**: infantil, ñoña, recargada, ruidosa, "Material Design
genérico", ni el look "AI/SaaS template" (gradiente violeta-azul de relleno,
glassmorphism porque sí, emojis como íconos, todo centrado).

Para detalle conceptual ver [`IDENTITY.md`](./IDENTITY.md).

---

## 2. Sistema gráfico (histórico)

> **Estado v3: deprecado.** El sistema gráfico "Red de memoria"
> (`MemoryField`, `GrainOverlay`, diamante como acento ambiental) vivió en
> `packages/ui/src/graphics/` durante las fases F0.3 / F1.2 del
> [plan de rediseño](./docs/planning/FRONTEND-REDESIGN-PLAN.md). Se removió en el
> **PR #148** cuando la app se movió al **lenguaje sobrio**: light-only, sin
> trama de puntos detrás del contenido, recurso ambiental reducido al
> **brand veil** (`BrandWaves`).

### 2.1 Lo que sigue vigente del concepto

Los símbolos **conceptuales** de marca (nodos, vínculos, bifurcación Y,
diamante) siguen siendo el ADN de la **identidad visual** (guía 2026):
informan los **íconos** (§9), el **logo** (`YnaraMark`) y la voz de las
piezas editoriales. Lo que se deprecó es su materialización como **fondo
gráfico SVG** detrás del contenido de producto.

### 2.2 Recurso ambiental actual: `BrandWaves`

`BrandWaves` (en `apps/web/src/components/ui/`) reemplaza al `MemoryField`
como capa de profundidad. Es una **veil SVG con fade-top mask**, sin nodos
ni diamantes — coherente con el lenguaje sobrio. Consumido por
`onboarding/layout.tsx` y `today/HoyView.tsx`.

### 2.3 Histórico de la "Red de memoria"

Si más adelante un consumidor necesita el subsistema gráfico anterior, el
código vivió en `packages/ui/src/graphics/` hasta el PR #148: `MemoryField`,
`GrainOverlay`, y `buildMemoryField` (geometría determinista con PRNG
sembrado). La guía 2026 sigue siendo la fuente del concepto.

---

## 3. Paleta

Identidad cromática: **azul → violeta sobre marfil** (claro) / **nocturna**
(oscuro). La calidez viene de la **superficie marfil + el grano**, no de un acento
cálido nuevo — la paleta de sistema se mantiene fiel al universo de marca. [marca]
El ámbar y el jade existen **solo como tints por-modo** (§3.5), no como acento del
sistema.

### 3.1 Superficies — light-only

> **Decisión [sobrio]**: la app web es **light-only**. No hay variante dark, ni
> respeto a `prefers-color-scheme`. El layering nace de la distinción
> **canvas** (ivory tibio, el body) vs **bg** (blanco puro, las cards que
> flotan).

| Rol | Token CSS | Valor | Fuente |
|---|---|---|---|
| Canvas (body, fondo detrás del contenido) | `--color-bg-canvas` | `#FAF9F5` (ivory) | [marca] |
| Fondo elevado (cards, inputs, modales) | `--color-bg` | `#FFFFFF` (blanco) | [sobrio] |
| Fondo suave (pills, chip containers, secciones alternas) | `--color-bg-soft` | `#F3F0EA` (crema cálido) | [marca] |

> Regla [research]: **nunca blanco puro como body**. El ivory canvas es uno de
> los cambios de mayor señal para salir del look genérico. El blanco vive solo
> en superficies que se apoyan sobre el canvas (cards, inputs, modales), donde
> aporta jerarquía por luz.
>
> Nota v3 [sobrio]: el v2 tenía ambas superficies (body + cards) en marfil.
> El v3 separa **canvas ivory + bg blanco** para que las cards no se fundan
> con el body — más jerarquía sin sombras pesadas.

### 3.2 Tinta (texto)

| Rol | Token CSS | Valor |
|---|---|---|
| Hero / title con presencia editorial | `--color-ink-deep` | `#1B2233` |
| Texto principal | `--color-ink` | `#242C3F` |
| Texto secundario | `--color-ink-soft` | `rgb(36 44 63 / 0.65)` |
| Texto terciario | `--color-ink-muted` | `rgb(36 44 63 / 0.45)` |
| Texto desactivado | `--color-ink-faint` | `rgb(36 44 63 / 0.18)` |
| Texto sobre fondos de marca | `--color-on-dark` | `#FFFFFF` |

> Jerarquía [research]: de-enfatizar **bajando contraste** (ink-soft/muted), no
> agrisando con un gris ajeno a la marca.
>
> Nuevo en v3 [sobrio]: `--color-ink-deep` para titulares con presencia
> editorial (más oscuro que `ink`). Aplicado en h1 de `/hoy`, `/memoria`,
> `/chat`, `/buscar`, y en piezas editoriales de onboarding.

### 3.3 Bordes y líneas

| Rol | Token CSS | Valor |
|---|---|---|
| Borde sutil | `--color-border` | `rgb(36 44 63 / 0.12)` |
| Borde marcado | `--color-border-strong` | `rgb(36 44 63 / 0.22)` |

> Override de a11y: `html.theme-high-contrast` aumenta el contraste de
> `--color-ink-soft/muted` y `--color-border*` (ver `globals.css`).

### 3.4 Azul de marca

> **Decisión [sobrio]**: el CTA primario usa **azul plano**, no gradiente. El
> gradiente queda relegado a **acentos puntuales** (ProgressDots active,
> hairlines, decoraciones de OptionCard).

**Azul plano — CTA primario y motor de la marca [sobrio]:**

| Token | Valor | Uso |
|---|---|---|
| `--color-blue-flat` | `#2F5AA6` | CTA primario, link, marca |
| `--color-blue-flat-hover` | `#26498A` | Hover del CTA primario |
| `--color-blue-flat-active` | `#1F3C75` | Press del CTA primario |
| `--color-accent` | alias de `--color-blue-flat` | Focus-ring, text-link |

**Gradientes como acento ambiental** [marca]:

| Token | Stops | Uso |
|---|---|---|
| `--gradient-blue-base` | `#2F5AA6 → #1F66DB` (135°) | Tint del modo Productividad, acentos puntuales |
| `--gradient-blue-relief` | `#4B7EE6 → #7BA1F4` (135°) | Tint del modo Estudio, highlights |
| `--gradient-violet` | `#8C63B8 → #7C4FA3` (135°) | Tint del modo Memoria |
| `--gradient-jade` | `#4A9C8C → #6FBFAE` (135°) | Tint del modo Bienestar |
| `--gradient-amber` | `#D9A24A → #E8C77A` (135°) | Tint del modo Vida |

**Acentos violetas ambientales:**

| Token | Valor | Uso |
|---|---|---|
| `--color-violet-glow` | `rgb(129 101 163 / 0.18)` | Glow ambiental, no para fills |
| `--color-memory` | alias de `--color-violet-to` (`#7C4FA3`) | Tinta de íconos del badge "capa memoria" (PromptChip, MemoryDetailView, SearchResultRow, TimelineEntryRow) |

> **Cambio v2 → v3** [sobrio]: la v2 prescribía una **rampa de memoria** rica
> (`--color-memory-deep/soft/accent` + `--gradient-memory`). El v3 **no la
> implementó**: el violeta vive hoy como `--gradient-violet` (heredado de v1),
> `--color-violet-glow` ambiental y `--color-memory` para la tinta de íconos
> de capa. Si un consumidor futuro necesita la rampa completa, sumarla en su PR.
>
> `--color-memory` se sumó después del bump a v3 para cerrar una deuda
> preexistente: 4 callers lo referenciaban sin que el token existiera
> (commits `76b1622`, `0c5e59a`, `3d8f5c8`, `62acc8b` introdujeron los usos;
> `9f84c6a` bajó light-only sin migrar estos consumers; el PR de cierre
> sumó el alias al violeta de marca).

### 3.5 Tints por modo

Cada modo tiñe sutilmente `ModeChip` y `SuggestionCard`. **El jade y el ámbar viven
solo acá** — no son acentos del sistema [decisión validada]:

| Modo | Token de tint | Carácter | Fuente |
|---|---|---|---|
| Productividad | `--gradient-blue-base` | Azul base — acción, ejecución | [marca] |
| Estudio | `--gradient-blue-relief` | Azul claro — claridad, expansión | [marca] |
| Memoria | `--gradient-violet` | Violeta — el símbolo del logo | [marca] |
| Bienestar | `--gradient-jade` (`#4A9C8C → #6FBFAE`) | Jade — calma | [criterio] |
| Vida | `--gradient-amber` (`#D9A24A → #E8C77A`) | Ámbar — cotidiano cálido | [criterio] |

> Bienestar y Vida usan colores que **no están en la presentación de marca**;
> revalidar con @querques20 / @BriarDevv si se mantienen, se reencuadran dentro de la
> familia azul-violeta, o se acotan aún más.

### 3.6 Grano (textura de calidez)

> **Estado v3: no implementado.** [sobrio] La v2 prescribía un overlay de
> grano monocromo (`--texture-grain` / `.bg-grain`) para superficies grandes.
> El v3 decidió no implementarlo: el ivory canvas + las sombras suaves
> alcanzan para el efecto "papel" sin sumar overlay de ruido. Si una pieza
> específica lo pide, sumarlo en su PR.

### 3.7 Estados y utilitarios

| Rol | Token CSS | Valor |
|---|---|---|
| Error | `--color-error` | `#C0392B` |
| Error suave (fondo) | `--color-error-soft` | `rgb(192 57 43 / 0.12)` |
| Overlay (backdrop modales) | `--color-overlay` | `rgb(36 44 63 / 0.40)` |
| Acento puntual (focus-ring) | `--color-accent` | alias de `--color-blue-flat` (`#2F5AA6`) |

### 3.8 Contraste

- Target de compliance: **WCAG 2.1 AA** mínimo (AAA en textos críticos: hero, CTA).
- Guía de diseño, sobre todo en dark: **APCA** (Lc ~75+ para body, ~60 para
  secundario/large), por ser más preciso que WCAG 2.x en interfaces oscuras.
  [research] APCA orienta el diseño; WCAG valida el compliance.

---

## 4. Tipografía

### 4.1 Familias [marca]

| Familia | Para | Pesos | Source |
|---|---|---|---|
| **Space Grotesk** | Display (hero, títulos, marca, "big type" editorial) | 500, 700 | `next/font/google` |
| **DM Sans** | Body, botones, UI, captions | 400, 500, 600 | `next/font/google` |

Regla: **jamás Space Grotesk en body** — es display. El "carácter editorial" de las
piezas de gran formato (posters del slide 09) sale de la **composición** (big type,
jerarquía dramática, espacio), no de sumar fuentes. [marca]

> Decisión abierta: la presentación NO usa serif. Si se quisiera un serif humanista
> para momentos empáticos (saludo del asistente, quotes), es una propuesta a discutir
> con marca, **no** algo que el universo actual ya tenga. [criterio]

### 4.2 Escala fluida

Base 16px. Escala fluida con `clamp(rem + vw)` (nunca `vw` puro, para no romper el
zoom). Anclas ~360px → ~1240px. [research]

| Token | `clamp()` | line-height / tracking | Uso |
|---|---|---|---|
| `text-display` | `clamp(2.6rem, 1.9rem + 3.5vw, 3.5rem)` | 1.04 / `-0.03em` | Hero editorial, onboarding, posters in-app |
| `text-hero` | `clamp(2.25rem, 1.5rem + 3.75vw, 3rem)` | 1.08 / `-0.04em` | Hero de welcome |
| `text-title` | `clamp(1.75rem, 1.35rem + 2vw, 2.125rem)` | 1.12 / `-0.025em` | Título de step / sección |
| `text-subtitle` | `1.375rem` | 1.27 / `-0.018em` | Subtítulo |
| `text-body` | `1rem` | 1.5 / `-0.006em` | Cuerpo |
| `text-body-sm` | `0.875rem` | 1.43 / `-0.003em` | Helper, hints |
| `text-caption` | `0.75rem` | 1.33 / `+0.06em` UPPERCASE | Labels, etiquetas |
| `text-button` | `1rem` | 1.25 / `-0.006em` | Botones |

Reglas por rol [research]:

- **Display/hero (Space Grotesk):** tracking negativo (`-0.03em`/`-0.04em`),
  line-height ajustado (1.04-1.12). El tracking negativo en big type es lo que se ve
  "premium".
- **Body (DM Sans):** line-height 1.5-1.6, tracking ~0.
- **Labels uppercase:** tracking positivo `+0.06em`.
- **Datos/timestamps:** `font-variant-numeric: tabular-nums`.
- **Measure** (ancho de línea de lectura, ej. respuesta del asistente): **60-70ch**.
- Usar comillas curvas (« » / " ") y em-dash reales en copy, no rectas.

> **Nota v3** [sobrio]: `text-display` está documentado en esta tabla pero
> **no implementado** en `globals.css`. La app sobria topa en `text-hero` y
> `text-title` como techo editorial; si una pieza pide el display real
> (poster del slide 09), sumar la utility en su PR.

### 4.3 Sizing accesible

El store de a11y aplica `text-size-sm` / `text-size-md` (default) / `text-size-lg`
al `<html>`, cambiando el `font-size` base (`15px` / `16px` / `18px`); toda la escala
escala con `rem`.

---

## 5. Spacing

Escala base 4, **sin tokens propios**: se usa la escala default de Tailwind v4
(`p-1`=4px, `p-2`=8px, …) para minimizar superficie de tokens. Esta tabla documenta
el uso semántico.

| Tailwind | Valor | Uso típico |
|---|---|---|
| `1` (xs) | 4px | Microajustes, gap mínimo |
| `2` (sm) | 8px | Gap entre elementos relacionados |
| `3` (md) | 12px | Padding pequeño |
| `4` (base) | 16px | Padding default, gap de cards |
| `6` (lg) | 24px | Padding de cards, gap entre secciones |
| `8` (xl) | 32px | Sección |
| `12` (2xl) | 48px | Bloque grande |
| `16` (3xl) | 64px | Margen vertical de hero |
| `24` (4xl) | 96px | Aire editorial (hero/onboarding de gran formato) |

> Regla [research]: **spacing no uniforme** — más aire entre grupos distintos que
> entre elementos del mismo grupo. La uniformidad plana es un "tell" amateur.

---

## 6. Radius

| Token | Valor | Uso |
|---|---|---|
| `--radius-sm` | `0.5rem` (8px) | Inputs chicos, chips |
| `--radius-md` | `0.75rem` (12px) | Botones, cards default |
| `--radius-lg` | `1rem` (16px) | Cards prominentes, modales |
| `--radius-xl` | `1.25rem` (20px) | Hero cards, contenedores grandes |
| `--radius-pill` | `9999px` | Pill chips |

---

## 7. Elevation

3 niveles. Más allá → revisar jerarquía, no agregar sombra. Implementados como
utilities custom en `globals.css`.

| Utility | Sombra | Uso |
|---|---|---|
| (ninguna) | — | Cards default, inputs |
| `.shadow-soft` | `0 1px 2px rgb(36 44 63 / 0.06), 0 4px 12px rgb(36 44 63 / 0.04)` | Cards interactivas, hover |
| `.shadow-lifted` | `0 8px 24px rgb(36 44 63 / 0.08), 0 24px 48px rgb(36 44 63 / 0.06)` | Modales, toasts, dropdowns |

> Calibrado para card blanca sobre canvas ivory. Si una superficie nueva se
> apoya sobre `--color-bg-soft` (crema), revisar los alphas — pueden verse
> pesados.

---

## 8. Motion

### 8.1 Tokens (estado v3)

| Token | Valor | Uso |
|---|---|---|
| `--duration-base` | `250ms` | Transiciones de UI estándar |
| `--duration-screen` | `350ms` | Cambio de pantalla / navegación entre vistas |
| `--ease-out-soft` | `cubic-bezier(0.22, 1, 0.36, 1)` | Easing default |

> **Cambio v2 → v3** [sobrio]: la v2 prescribía 5 duraciones
> (`--duration-instant/fast/base/slow/screen` con base bajada a 200ms) +
> springs. El v3 mantuvo solo **base + screen** (con base en 250ms), y deja
> los springs como objetivo futuro si llega un consumidor que los pida.

**Modelo de reduced-motion** (ver `globals.css`):

- OS pide `prefers-reduced-motion: reduce` + sin override → animaciones off.
- `html.motion-off` → animaciones off (override del usuario desde a11y).
- `html.motion-on` → animaciones on (gana siempre).

### 8.2 Microinteracciones (alto ROI) [research]

| Patrón | Valor | Cuándo |
|---|---|---|
| Hover (cards/botones) | `scale(1.02)` + leve elevación, 150ms | Puntero sobre interactivos |
| Press | `scale(0.97-0.98)`, 100ms | Tap/click |
| Focus | ring animado (§12), 150ms | `focus-visible` |
| Entrada con stagger | fade + `translateY(8-12px)`, delay 30-50ms × i (máx ~6) | Listas de cards |
| Skeleton (shimmer sutil) | loop suave | Carga en vistas content-heavy (conversación, memoria) |
| Toast | 300ms in / 200ms out | Notificaciones |

### 8.3 Motion con significado de marca [criterio, anclado en marca]

El movimiento **expresa el concepto**, no decora:

- **Presencia** → el **foco editorial** (h1 con `--color-ink-deep`, hero con
  `text-hero`) ordena la jerarquía sin sumar acentos decorativos.
- **Estado** → el botón **Detener** durante streaming (§10.2) y el **chevron
  "ir al final"** (§10.4) marcan estado activo sin animaciones decorativas.

> **Cambio v2 → v3** [sobrio]: la v2 prescribía motion atado al sistema
> gráfico (nodos que se encienden al guardar, vínculos que se dibujan al
> cargar la red, diamante como indicador de "pensando"). El v3 **no las
> implementó** al deprecar `MemoryField`. Si más adelante una pieza pide
> motion conceptual, sumar en su PR.

### 8.4 Implementación y reglas

- Animar **solo `transform` y `opacity`** (GPU). Nunca `width`/`height`/`top`/`left`.
- **View Transitions API** para cambios de ruta / shared-element, con progressive
  enhancement (`if (document.startViewTransition)`) y fallback sin animación;
  `view-transition-name` únicos y pocos. [research]
- GSAP para secuencias complejas; CSS keyframes para microinteracciones; Lenis para
  smooth scroll en páginas largas (no en formularios).
- `prefers-reduced-motion` respetado globalmente, con override manual desde el store
  de a11y (`html.motion-on` / `html.motion-off`). Incluye pseudo-elementos de
  view-transition.
- ❌ Animaciones >500ms en UI utilitaria, bounce excesivo, loops decorativos
  infinitos. [research]

---

## 9. Iconografía

Ynara tiene un **set de íconos propio** con el ADN de los elementos: **trazo
uniforme + el diamante como acento**. [marca]

Íconos definidos en la guía: **Idea, Conexión, Memoria, Nota, Buscar, Diálogo,
Recordatorio, Adaptación, Foco, Red.**

Reglas:

- ✅ Implementar/extender el **set propio** (grosor de trazo uniforme, esquinas y
  remates consistentes, diamante como acento donde aplique). Un set custom es uno de
  los marcadores más fuertes de "producto crafteado vs generado por IA". [research]
- ✅ Fallback: **Lucide** solo para íconos utilitarios que el set propio no cubra
  todavía, **manteniendo el mismo grosor de trazo** para que convivan.
- ❌ **Nunca emojis ni flechas como íconos de UI** (es un "tell" amateur directo).
  [research]

---

## 10. Chat UI / asistente

El asistente es el corazón del producto; su UI debe sentirse **editorial, no
mensajería**. [research, alineado con "editorial y sereno" de marca]

### 10.1 Mensajes — "documento", no "burbujas"

- **Asistente: sin burbuja.** Respuesta a ancho de columna acotada (**~680-720px,
  measure 60-70ch**), prosa real con markdown completo (`line-height` 1.5-1.6,
  15-16px). [research]
- **Usuario:** contenedor liviano alineado a la derecha (no una burbuja pesada).
- Jerarquía tipográfica real entre turnos; nada de globos cargados en ambos lados.

### 10.2 Composer (editor vivo)

- Textarea autosize multi-línea con tope (~6-8 líneas y luego scroll interno).
- Enter envía / Shift+Enter newline.
- Estados: draft / sending / streaming / disabled.
- Acciones: adjuntar (izquierda), enviar (derecha). Durante el streaming, el botón
  enviar se convierte en **Detener** prominente. [research]
- Íconos del set propio (§9), **no** flechas emoji.

### 10.3 Streaming

- Render token a token con **cursor sutil** (~2px, parpadeo ~500ms) que desaparece al
  terminar.
- **Bufferizar markdown incompleto**: diferir bloques de código hasta cerrar el fence
  (que un `**` o ``` a medias no rompa el layout). Evitar re-layout por token.
  [research]
- Indicadores diferenciados con voz de Ynara (pensando / buscando / generando) +
  skeleton antes del primer token. [criterio]
- Tool-calls `memory.*` como **acordeones colapsables** ("Usando memoria…"), no texto
  crudo.

### 10.4 Auto-scroll inteligente

- Seguir el stream **solo si el usuario está cerca del fondo**; si scrollea arriba,
  **pausar** y mostrar botón flotante "ir al final" (chevron). [research]
- ⚠️ **Corrige el auto-scroll de W2** (`MessageList`), que hoy secuestra la lectura
  porque siempre baja al fondo.

### 10.5 Empty state / onboarding conversacional

- Como las piezas de gran formato (slide 09): **big type + voz de marca**, con
  `BrandWaves` (§2.2) como capa ambiental cuando el layout lo pida.
- Welcome + **3-4 chips de prompt accionables**; nunca un placeholder genérico tipo
  "Escribí algo…". [research]

### 10.6 Accesibilidad del chat

- `aria-live="polite"` + `aria-atomic="false"`, debounced para no spamear el lector.
- Orden de tab predecible; no robar el foco al terminar el stream.

---

## 11. Componentes (primitives)

Los primitives web-only viven en
[`apps/web/src/components/ui/`](./apps/web/src/components/ui/) (regla del repo:
`packages/ui` está reservado para cosas portables web/mobile RN-compatibles).

> **Deuda explícita**: `YnaraMark.tsx` (SVG) y `modes.ts` (type-only) son portables a
> mobile. En la sesión mobile, mover `YnaraMark` a `packages/ui` (`<svg>` → `<Svg>` de
> `react-native-svg`) y `modes.ts` a `packages/shared-types`.

| Componente | Variants | Notas |
|---|---|---|
| `Button` | `primary`, `secondary`, `ghost` | `primary` usa `--color-blue-flat` + hover/active. Hover/press según §8.2. |
| `Card` | `default`, `interactive` | `interactive`: `shadow-soft` + hover `scale(1.02)`. |
| `OptionCard` | idle, selected | Selected: fondo ink + hairline gradient en borde. |
| `TextField` / `Textarea` | default, error | Error inline con copy humano. |
| `Toggle` | off, on | Switch propio con tokens. |
| `ChipGroup` | — | Opciones segmentadas. |
| `PromptChip` | — | Chip de prompt accionable (empty state del chat, §10.5). |
| `ProgressDots` | — | current = gradient azul base; otros = ink-faint. |
| `Toast` | info, success, error | Auto-dismiss configurable. |
| `YnaraMark` | size | Logo SVG con gradientes. |
| `Icon` | nombre del set | Set propio (§9); fallback Lucide controlado. |
| `ModeChip` / `SuggestionCard` | por modo | Tint del modo (§3.5). |
| `EmptyStateCard` | — | Estados vacíos sobrios (sin fondo gráfico) [sobrio]. |
| `BrandWaves` | `relative`, `absolute` | Brand veil SVG con fade-top mask. Reemplazo del sistema gráfico (§2.2). |

Cada componente en su propio archivo, named export, sin barrel monstruo.

---

## 12. Reglas visuales transversales

- Contraste mínimo **WCAG AA**, target **AAA** en textos críticos; APCA como guía de
  diseño (§3.8).
- Respetar `prefers-reduced-motion`, con override manual desde a11y.
- Tap targets ≥ **44×44px**.
- Focus rings visibles con identidad (anillo doble: `--color-bg` + `--color-accent`),
  nunca `outline: none` sin reemplazo.
- **Mobile-first** siempre. Breakpoints: `sm:640`, `md:768`, `lg:1024`, `xl:1280`.
- Container max-width: formularios/onboarding `480px`; conversación `~720px` (§10.1).
- **Light-only declarado** [sobrio]: la app no tiene variante dark ni respeta
  `prefers-color-scheme`. La jerarquía viene del par canvas ivory / bg blanco
  + las sombras suaves (§7).

---

## 13. Anti-patterns

Errores de implementación:

- ❌ Hardcodear hex en componentes — siempre vía CSS var.
- ❌ Space Grotesk en body — es display.
- ❌ Animar `width`/`height`/`top`/`left` — solo `transform` y `opacity`.
- ❌ `outline: none` sin reemplazar el focus visual.
- ❌ Sombras múltiples superpuestas — usar la escala.
- ❌ Botones disabled sin copy/tooltip que explique por qué.
- ❌ Toast genérico para errores de form — usar inline.
- ❌ Loops decorativos infinitos.
- ❌ Imágenes sin `alt`, `width`, `height`, `loading="lazy"`.

"Tells" del look generado por IA / amateur a evitar [research]:

- ❌ **Blanco puro como body** → ivory canvas (§3.1). El blanco sí vive en cards.
- ❌ **Gradiente violeta-azul de relleno** + glassmorphism porque sí → sistema gráfico
  (§2) y gradientes solo como ambiente.
- ❌ **Emojis/flechas como íconos** → set propio (§9).
- ❌ **Todo centrado y simétrico** / grid de 3 tarjetas idénticas → layout intencional,
  jerarquía y foco claros.
- ❌ **Jerarquía solo por tamaño** → peso + contraste; spacing no uniforme.
- ❌ **Spinners genéricos** → skeletons + indicadores con voz (§10.3).
- ❌ **Copy buzzword** → microcopy específico con voz de Ynara.
- ❌ **Banding en gradientes** → grano (§3.6).

---

## 14. Migración v2 → v3 (deltas implementados)

La serie de PRs **#139–#148** materializó el bump a v3. Tabla de deltas reales:

| Área | v2 (objetivo histórico) | v3 (estado vivo) |
|---|---|---|
| Layering de superficies | marfil body + marfil cards | ivory canvas + white cards (light-only) |
| Dark mode | co-protagonista | **eliminado** (light-only declarado en `globals.css`) |
| CTA primario | `--gradient-blue-base` | `--color-blue-flat` + hover/active |
| Titulares | `--color-ink` | `--color-ink-deep` para hero/title editorial |
| Subtítulos | `--color-ink-muted` | `--color-ink-soft` |
| Sistema gráfico | `MemoryField` + `GrainOverlay` + diamante ambiental | **deprecado** (PR #148); reemplazado por `BrandWaves` |
| Grano | `--texture-grain` / `.bg-grain` | **no implementado** [sobrio] |
| Rampa de memoria | `--color-memory-*` (4 tokens) + `--gradient-memory` | **no implementada**; `--gradient-violet` legacy + `--color-violet-glow` |
| Tipografía | `text-display` (clamp 2.6 → 3.5rem) | **no implementada**; tope en `text-hero` / `text-title` |
| Motion | 5 duraciones + springs | 2 duraciones (`base` 250ms + `screen` 350ms) |

> Migraciones canceladas a propósito: rampa de memoria, grano, `text-display`,
> dark mode. No son deuda — son decisiones del lenguaje sobrio, documentadas
> en los PRs de la serie. Si un consumidor futuro pide alguna, suma su token
> en su PR.

### Histórico de PRs

- **PR #97** — bump v0 → v1: tokens base.
- **PR #139** — onboarding sobrio (auth/name/mood/modes/a11y + outro).
- **PR #140** — hoy sobrio (header + secciones + cards).
- **PR #141** — chat sobrio (composer + empty state).
- **PR #147** — memoria + buscar sobrios.
- **PR #148** — deprecación de `MemoryField` + `GrainOverlay` (cierre de F0.3).
- **Este PR** — bump del DESIGN.md a v3 (cierre editorial de la serie).

---

## 15. Referencias

- [`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) — tokens en CSS
  vars y `@theme`.
- [`apps/web/src/styles/motion.css`](./apps/web/src/styles/motion.css) — keyframes
  reutilizables.
- [`apps/web/src/components/ui/`](./apps/web/src/components/ui/) — primitives.
- [`docs/planning/design-research-2026.md`](./docs/planning/design-research-2026.md)
  — research de tendencias 2026 + integración del universo de marca (con citas y
  verificación adversarial).
- `Ynara-Universo-de-Marca.html` — Guía de identidad visual · Ynara 2026 (fuente del
  sistema gráfico, iconografía, paleta y aplicaciones; **conviene versionarla en el
  repo**, p. ej. `docs/brand/`).
- [`IDENTITY.md`](./IDENTITY.md) — ADN de marca.
- [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md) — voz operativa
  modo-por-modo.
- Prototipo de referencia: [querques20/ynara](https://github.com/querques20/ynara).
