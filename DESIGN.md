# Sistema de Diseño de Ynara

Este archivo es la **fuente de verdad del sistema visual de Ynara**. El código se
actualiza para matchear este doc, no al revés — los tokens reales viven en
[`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) y este doc es la
especificación legible que ese CSS debe implementar. Si hay divergencia, se
corrige el código.

> **Aprobación**: cualquier cambio sustantivo a este archivo requiere PR con review
> de @MateoGs013 (CODEOWNER). Para cambios que afecten identidad de marca (paleta,
> tipografía, sistema gráfico), revisar también con @BriarDevv y @querques20.

> **Estado — v2 (2026), redefinición.** Esta versión integra el **universo de marca
> propio** (`Ynara-Universo-de-Marca.html`, Guía de identidad visual · Ynara 2026) y
> el research de tendencias 2026 ([`docs/planning/design-research-2026.md`](./docs/planning/design-research-2026.md)).
> Define el **sistema objetivo**; la migración del `globals.css` actual está
> detallada en el **§14**. Cada valor está etiquetado:
> **[marca]** = literal de la presentación · **[research]** = respaldado por evidencia ·
> **[criterio]** = juicio de diseño a validar en review.

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

## 2. Sistema gráfico (la "Red de memoria")

El rasgo más identitario y ownable de Ynara. **Esto reemplaza al gradiente
genérico** como recurso de profundidad/ambiente y es el antídoto principal contra
el look "generado por IA". [marca]

### 2.1 Elementos base

| Elemento | Forma | Significado |
|---|---|---|
| **Nodo** | Punto / círculo pequeño con halo | Una idea o recuerdo capturado. Unidad mínima. |
| **Vínculo** | Línea / hilo curvo entre nodos | La asociación que une dos ideas. |
| **Bifurcación** | Ramificación — **la forma de la Y** | El pensamiento que se ramifica. |
| **Diamante** | Rombo (acento del logo) | Foco y presencia. El acento que ordena. |

### 2.2 Patrón "Red de memoria" [marca]

- Módulo base de **320px** que se repite sin costura.
- Nodos enlazados en una **red orgánica**; los diamantes son los **acentos
  rítmicos**.
- Versión base: **azul sobre marfil**.
- Variaciones de densidad: **dispersa / media / densa** (según cuánto protagonismo
  quiera la superficie).

### 2.3 Trama "Continuidad" [marca]

Líneas de **flujo paralelo** que traducen la continuidad del pensamiento.
Variaciones: base (flujo paralelo) / abierta / densa. Útil para divisores,
transiciones y fondos de bloques largos.

### 2.4 Texturas [marca]

Las texturas **se construyen con la geometría del sistema — nunca con fotografía.**
Aportan materia sin romper la sobriedad.

| Textura | Rol |
|---|---|
| **Grano** | Calidez y materia física (overlay de ruido — ver §3.6). |
| **Campo de nodos** | Densidad de ideas (fondo ambiental). |
| **Profundidad** | Atmósfera y niebla nocturna (gradiente desaturado + grano en dark). |

### 2.5 Reglas de uso

- ✅ Fondos ambientales de hero / onboarding / empty states, dividers, estados de
  carga, decoración de secciones.
- ✅ Implementado como **SVG vectorial** (como en la presentación: `<linearGradient>`
  + paths), no como mesh-gradient CSS. [marca]
- ✅ Densidad acorde a la jerarquía: más denso donde la superficie es protagonista,
  disperso/sutil detrás de contenido legible.
- ❌ Nunca detrás de texto largo sin bajar opacidad/contraste lo suficiente.
- ❌ Nunca animar la red de forma decorativa infinita (ver §8).

---

## 3. Paleta

Identidad cromática: **azul → violeta sobre marfil** (claro) / **nocturna**
(oscuro). La calidez viene de la **superficie marfil + el grano**, no de un acento
cálido nuevo — la paleta de sistema se mantiene fiel al universo de marca. [marca]
El ámbar y el jade existen **solo como tints por-modo** (§3.5), no como acento del
sistema.

### 3.1 Superficies

**Light ("marfil"):**

| Rol | Token CSS | Valor | Fuente |
|---|---|---|---|
| Fondo base | `--color-bg` | `#FAF9F5` (marfil claro) | [marca] |
| Fondo suave / recesado (cards, secciones) | `--color-bg-soft` | `#F3F0EA` (marfil) | [marca] |

> Regla [research]: **nunca blanco puro `#FFFFFF`** como superficie. El marfil cálido
> es uno de los cambios de mayor señal para salir del look genérico.

**Dark ("nocturna"):**

| Rol | Token CSS | Valor | Fuente |
|---|---|---|---|
| Fondo base | `--color-bg` | `#242C3F` (la nocturna de marca) | [marca] |
| Fondo elevado (cards) | `--color-bg-soft` | `#2E3750` (un paso más claro) | [criterio] |

> Regla [research]: en dark, **nunca negro puro**; la elevación se expresa por **luz**
> (la superficie más alta es más clara), no por sombra. El dark de Ynara es su
> azul-tinta de siempre, no un negro nuevo — coherente con la "niebla nocturna" de
> marca.

### 3.2 Tinta (texto)

| Rol | Token CSS | Light | Dark |
|---|---|---|---|
| Texto principal | `--color-ink` | `#242C3F` | `#E8ECF4` |
| Texto secundario | `--color-ink-soft` | `rgb(36 44 63 / 0.65)` | `rgb(232 236 244 / 0.70)` |
| Texto terciario | `--color-ink-muted` | `rgb(36 44 63 / 0.45)` | `rgb(232 236 244 / 0.50)` |
| Texto desactivado | `--color-ink-faint` | `rgb(36 44 63 / 0.18)` | `rgb(232 236 244 / 0.20)` |
| Texto sobre fondos de marca | `--color-on-dark` | `#FAF9F5` | `#FAF9F5` |

> Jerarquía [research]: de-enfatizar **bajando contraste** (ink-soft/muted), no
> agrisando con un gris ajeno a la marca.

### 3.3 Bordes y líneas

| Rol | Token CSS | Light | Dark |
|---|---|---|---|
| Borde sutil | `--color-border` | `rgb(36 44 63 / 0.12)` | `rgb(232 236 244 / 0.12)` |
| Borde marcado | `--color-border-strong` | `rgb(36 44 63 / 0.22)` | `rgb(232 236 244 / 0.22)` |

### 3.4 Azul de marca y rampa de memoria (violeta)

**Azul** — el rasgo más identitario, motor del CTA primario [marca]:

| Token | Stops | Uso |
|---|---|---|
| `--gradient-blue-base` | `#2F5AA6 → #1F66DB` (135°) | CTA primario, marca, modo Productividad |
| `--gradient-blue-relief` | `#4B7EE6 → #7BA1F4` (135°) | Glow, highlights, modo Estudio |

**Rampa de memoria (violeta)** — enriquecida con la familia real de la marca, que
tenía más matices que el único violeta anterior [marca]:

| Token | Valor | Rol |
|---|---|---|
| `--color-memory-deep` | `#434A82` (indigo) | Profundidad de la red |
| `--color-memory` | `#5C6FB3` (violáceo) | Tono medio |
| `--color-memory-soft` | `#8B9AD0` (periwinkle) | Acento claro / nodos |
| `--color-memory-accent` | `#8165A3` (violeta) | Acento de memoria |
| `--gradient-memory` | `#434A82 → #8165A3` (135°) | Símbolo de memoria, recall, modo Memoria, outro onboarding |

> **Regla clave** [marca]: el **gradiente azul base es el rasgo más identitario**; el
> CTA primario lo usa y no se reemplaza por sólido salvo donde el gradiente afecte la
> legibilidad (botones muy chicos, chips densos). Los gradientes ricos (azul,
> memoria) son **ambiente y marca**, no relleno de UI funcional.

### 3.5 Tints por modo

Cada modo tiñe sutilmente `ModeChip` y `SuggestionCard`. **El jade y el ámbar viven
solo acá** — no son acentos del sistema [decisión validada]:

| Modo | Token de tint | Carácter | Fuente |
|---|---|---|---|
| Productividad | `--gradient-blue-base` | Azul base — acción, ejecución | [marca] |
| Estudio | `--gradient-blue-relief` | Azul claro — claridad, expansión | [marca] |
| Memoria | `--gradient-memory` | Violeta — el símbolo del logo | [marca] |
| Bienestar | `--gradient-jade` (`#4A9C8C → #6FBFAE`) | Jade — calma | [criterio] |
| Vida | `--gradient-amber` (`#D9A24A → #E8C77A`) | Ámbar — cotidiano cálido | [criterio] |

> Bienestar y Vida usan colores que **no están en la presentación de marca**;
> revalidar con @querques20 / @BriarDevv si se mantienen, se reencuadran dentro de la
> familia azul-violeta, o se acotan aún más.

### 3.6 Grano (textura de calidez)

Overlay de **ruido monocromo al 3-6%** sobre superficies grandes y gradientes, para
matar el banding y aportar "materia física". [marca][research]

- Implementación: SVG `feTurbulence` tileado o PNG de ruido, como utility único
  (`--texture-grain` / `.bg-grain`).
- Usar con **sobriedad y propósito** (superficies amplias, hero, nocturna), no como
  sello obligatorio en cada caja. [research]

### 3.7 Estados y utilitarios

| Rol | Token CSS | Valor |
|---|---|---|
| Error | `--color-error` | `#C0392B` |
| Error suave (fondo) | `--color-error-soft` | `rgb(192 57 43 / 0.12)` |
| Overlay (backdrop modales) | `--color-overlay` | `rgb(36 44 63 / 0.40)` (light) · `rgb(14 18 25 / 0.60)` (dark) |
| Acento puntual (focus-ring) | `--color-accent` | alias de `--color-blue-base-from` (`#2F5AA6`) |

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

3 niveles. Más allá de eso → revisar jerarquía, no agregar sombra.
Implementados como utilities custom en `globals.css`.

**Light** — sombra suave con una sola fuente de luz (top-down) [research]:

| Utility | Sombra | Uso |
|---|---|---|
| (ninguna) | — | Cards default, inputs |
| `.shadow-soft` | `0 1px 2px rgb(36 44 63 / 0.06), 0 4px 12px rgb(36 44 63 / 0.04)` | Cards interactivas, hover |
| `.shadow-lifted` | `0 8px 24px rgb(36 44 63 / 0.08), 0 24px 48px rgb(36 44 63 / 0.06)` | Modales, toasts, dropdowns |

**Dark** — la elevación se expresa por **luz, no por sombra** [research]: las
superficies más altas usan `--color-bg-soft` (más claro) y/o un overlay blanco
semitransparente; las sombras se reducen al mínimo.

---

## 8. Motion

### 8.1 Tokens

| Token | Valor | Uso |
|---|---|---|
| `--duration-instant` | `100ms` | Feedback inmediato (press) |
| `--duration-fast` | `150ms` | Hover, focus, microinteracciones |
| `--duration-base` | `200ms` | Transiciones de UI estándar |
| `--duration-slow` | `300ms` | Transiciones más amplias |
| `--duration-screen` | `350ms` | Cambio de pantalla / navegación |
| `--ease-out-soft` | `cubic-bezier(0.22, 1, 0.36, 1)` | Easing default |

**Springs** (para Motion / animaciones con física), modelo perceptual
`visualDuration` + `bounce` [research, respaldado por Apple WWDC23 + Figma]:

- `spring-snappy`: `visualDuration 0.2`, `bounce 0` — UI utilitaria.
- `spring-soft`: `visualDuration 0.35`, `bounce 0.15` — entradas, elementos amables.

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

- **Memoria** → un nodo **se enciende / pulsa** al guardar un recuerdo.
- **Conexión** → los vínculos **se dibujan** (path draw) al cargar la red.
- **Presencia** → el **diamante** marca el estado activo / foco (p. ej. indicador de
  "pensando" del asistente, §10).

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
  skeleton antes del primer token. El **diamante** (§2.1) puede ser el indicador de
  "pensando/foco". [criterio]
- Tool-calls `memory.*` como **acordeones colapsables** ("Usando memoria…"), no texto
  crudo.

### 10.4 Auto-scroll inteligente

- Seguir el stream **solo si el usuario está cerca del fondo**; si scrollea arriba,
  **pausar** y mostrar botón flotante "ir al final" (chevron). [research]
- ⚠️ **Corrige el auto-scroll de W2** (`MessageList`), que hoy secuestra la lectura
  porque siempre baja al fondo.

### 10.5 Empty state / onboarding conversacional

- Como las piezas de gran formato (slide 09): **big type + voz de marca**, con el
  sistema gráfico (§2) como capa ambiental detrás.
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
| `Button` | `primary`, `secondary`, `ghost` | `primary` usa `--gradient-blue-base`. Hover/press según §8.2. |
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
| `EmptyStateCard` | — | Estados vacíos con sistema gráfico de fondo. |
| `GrainOverlay` / `MemoryField` | — | Capa de grano (§3.6) / red de memoria (§2) ambiental. |

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
- **Dark mode co-protagonista**: light y dark son ambos first-class; cada superficie,
  sombra y textura tiene su variante (no un dark "discreto" como afterthought).

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

- ❌ **Blanco/negro puro** como superficie → marfil / nocturna (§3.1).
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

## 14. Migración desde el sistema actual (deltas para `globals.css`)

Este doc define el objetivo; el `globals.css` actual aún implementa el sistema v1.
Cambios a aplicar (en su propio PR de implementación, con verificación visual):

| Área | Actual (v1) | Objetivo (v2) |
|---|---|---|
| `--color-bg` (light) | `#FFFFFF` | `#FAF9F5` (marfil claro) |
| `--color-bg-soft` (light) | `#F6F6F8` | `#F3F0EA` (marfil) |
| `--color-bg` (dark) | `#0E1219` | `#242C3F` (nocturna de marca) |
| `--color-bg-soft` (dark) | `#161B25` | `#2E3750` |
| `--color-on-dark` | `#FFFFFF` | `#FAF9F5` |
| Rampa de memoria | solo `--gradient-violet` (`#8C63B8→#7C4FA3`) | `--color-memory-*` (indigo/violáceo/periwinkle/violeta) + `--gradient-memory` (`#434A82→#8165A3`) |
| Motion tokens | `--duration-base`, `--duration-screen`, `--ease-out-soft` | + `--duration-instant/fast/slow` + springs (§8.1) |
| Tipografía | escala fija + clamp en hero/title | escala fluida completa (§4.2) + `text-display` |
| Grano | — | `--texture-grain` / `.bg-grain` (§3.6) |
| Sistema gráfico | — | componentes SVG `MemoryField` / patrón (§2) |
| Iconografía | ad-hoc / emojis | set propio `Icon` (§9) |
| Dark mode | "discreto" (afterthought) | co-protagonista, elevación por luz (§7) |

> Nota: el ámbar y el jade (`--gradient-amber`, `--gradient-jade`) se **conservan**
> como tints de modo (§3.5), pendientes de revalidación con marca.

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
