# Sistema de Diseño de Ynara

Este archivo es la **fuente de verdad del sistema visual de Ynara**. El código se
actualiza para matchear este doc, no al revés — los tokens reales viven en
[`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) y este doc es la
especificación legible que ese CSS debe implementar. Si hay divergencia, se
corrige el código.

> **Aprobación**: este repo tiene un único dueño de producto/marca. Los cambios
> a este archivo y al sistema visual se deciden a ese nivel. Aun así, todo cambio
> entra por **PR** (rama → commits atómicos → `ynara-doctor` exit 0 → review →
> rebase merge), nunca por push directo a `main`.

> **Estado — v4 (2026), sistema vivo.** Esta versión **eleva la vara** del
> lenguaje sobrio (v3) al lenguaje del **prototipo de referencia**: la marca
> mejor planteada, más inmersiva y con más carácter, **sin perder calma ni
> accesibilidad**. v4 conserva toda la **ingeniería** que v3 dejó bien (tokens
> CSS-first, a11y, primitivas, escala tipográfica, disciplina de CTA plano) y
> **reintroduce con criterio** lo que v3 había recortado de más:
> **tema dual (marfil + Noche)**, **fondo vivo en canvas** (reemplaza al velo
> estático), y **modos alineados a la paleta oficial**. Los deltas exactos
> respecto a v3 están en el **§14**.
> Etiquetas: **[marca]** = literal de la guía 2026 · **[research]** = respaldado
> por evidencia · **[criterio]** = juicio de diseño · **[v4]** = decisión del
> sistema vivo (este bump) · **[sobrio]** = decisión heredada de la serie #139–#148
> que v4 **conserva**.

---

## 1. Esencia de marca

> **"Tecnología que se siente como pensar."** Ynara no es una IA ruidosa: es una
> **compañía cognitiva diaria**. Su universo visual es **editorial y sereno — lo
> opuesto al cliché tecnológico.** [marca]

Esa frase sigue siendo la **regla rectora**. v4 agrega un matiz: *editorial y
sereno* **no es lo mismo que vacío**. Una pieza puede ser calma y a la vez
**estar viva** — respirar, reaccionar a tu presencia, tener atmósfera. El error
de v3 fue confundir "sobrio" con "plano". v4 corrige eso: **calma con alma.**
[v4]

Tres ideas gobiernan el sistema [marca]:

| Idea | Forma | Significado |
|---|---|---|
| **Memoria** | Nodos y puntos de luz | Cada idea/recuerdo capturado. La unidad mínima. |
| **Conexión** | Vínculos e hilos | El tejido que une un pensamiento con el siguiente. |
| **Presencia** | El diamante | Foco y claridad en la profundidad. El acento que ordena. |

Atributos operativos que la UI debe respirar siempre:

- **Claridad** — jerarquía obvia (peso + contraste, no solo tamaño), copy
  directo con voz, sin ruido decorativo.
- **Calma** — espacio para respirar, contrastes que no agreden, motion que
  acompaña y nunca distrae.
- **Profundidad** — atmósfera construida con el **fondo vivo** (§2) y el par de
  superficies (marfil/Noche); gradientes como ambiente contenido, jamás como
  relleno de UI.
- **Presencia** [v4] — el entorno **sabe que estás ahí**: el campo reacciona al
  cursor, los titulares ordenan la mirada, el orbe acompaña. Es el atributo que
  separa "una UI linda" de "una experiencia de la que el usuario se siente
  parte".

Lo que la UI **no es**: infantil, ñoña, recargada, ruidosa, "Material Design
genérico", ni el look "AI/SaaS template" (gradiente violeta-azul de relleno,
glassmorphism porque sí, emojis como íconos, todo centrado).

Para detalle conceptual ver [`IDENTITY.md`](./IDENTITY.md).

---

## 2. Fondo vivo (sistema ambiental)

> **Cambio central de v4.** [v4] v3 deprecó el sistema gráfico "Red de memoria"
> (`MemoryField` + `GrainOverlay`) y lo reemplazó por un **velo SVG estático**
> (`BrandWaves`). v4 lo reemplaza por un **campo vivo en `<canvas>`**: la
> atmósfera de la marca, ahora animada, calma y **reactiva**. El concepto de
> "Red de memoria" vuelve — pero **bien hecho**: sutil, performante y al servicio
> de la calma, no del ruido que v3 quería evitar.

### 2.1 Qué es

`LivingField` (en `apps/web/src/components/ui/`) dibuja, en un solo `<canvas>`
detrás del contenido (`-z-10`, `aria-hidden`, `pointer-events-none`):

- **Profundidad** — blooms de color (gradientes radiales) que derivan lento. Es
  la "atmósfera". *Acá viven los gradientes ambientales — en el canvas, no en la
  UI.*
- **Ondas de marca** — cintas horizontales con gradiente izq→der (transparente →
  color) + hilos finos que las siguen. La estética literal del poster de marca
  (guía 2026), en movimiento muy lento.
- **Campo de nodos** — puntos de luz que derivan y se enlazan con hilos finos
  (la "Memoria" + "Conexión" del §1).
- **Reactividad al cursor** [v4] — alrededor del puntero los nodos se apartan y
  se iluminan apenas, los hilos cercanos brillan, y un **halo de presencia**
  suave sigue al cursor. Spring-back al alejarse. Es el atributo *Presencia*
  hecho material. En touch/mobile, sin cursor, queda el campo en deriva.

### 2.2 Variantes por pantalla (diversificación)

Una sola textura en todas las pantallas aplana la experiencia. Cada vista
**destaca una textura** del repertorio, para dar dinamismo y contraste entre
secciones [v4]:

| Pantalla | Variante | Textura dominante | Estado en el repo |
|---|---|---|---|
| Hoy | `aurora` | Ondas que fluyen + atmósfera | **migrar** (`HoyView.tsx:59` monta `BrandWaves`) |
| Hablar (chat) | `constellation` | Campo de nodos denso (estrellas) | montaje **nuevo** (hoy sin fondo) |
| Memoria | `network` | Red de nodos con hilos marcados | montaje **nuevo** (hoy sin fondo) |
| Onboarding (layout) | `constellation` | Campo de nodos (primera impresión) | **migrar** (`app/onboarding/layout.tsx:39`) |
| Paywall | `constellation` | ídem | montaje **nuevo** |
| Agenda | `paper` | Grano — limpio, casi quieto, sin cursor | **pendiente** — la feature aún no existe |
| Tu (perfil) | `depth` | Profundidad pura (blooms, sin partículas) | **pendiente** — la feature aún no existe |

> **Call sites reales.** Hoy `BrandWaves` se monta en **solo dos** lugares:
> `app/onboarding/layout.tsx:39` y `features/today/components/HoyView.tsx:59`.
> `StepShell.tsx` y `OnboardingHeader.tsx` **solo lo mencionan en comentarios**
> (heredan el velo del layout). Las demás variantes son **montajes nuevos** en
> pantallas que hoy no tienen fondo (Chat, Memoria, Paywall) o en features que
> **todavía no existen** (Agenda, Tu/Perfil — `features/` solo tiene `chat`,
> `memory`, `onboarding`, `today`). Detalle de migración en §16.

### 2.3 Reglas no negociables del fondo vivo

Son las que contestan la objeción legítima que motivó la deprecación en v3
("es ruidoso / pesa / distrae"):

- **`prefers-reduced-motion`** respetado: con reduce (y sin override `motion-on`)
  dibuja **un solo frame estático**. Nunca anima si el usuario pidió quietud.
- **Pausa en `visibilitychange`**: cuando la pestaña no está visible, corta el
  `requestAnimationFrame`. Cero CPU en background.
- **Solo GPU-friendly**: canvas 2D con `transform`/alpha, sin layout. DPR capado
  a 2. Densidad de nodos acotada por área.
- **Detrás del contenido, sin foco, sin eventos**: `-z-10`, `aria-hidden`,
  `pointer-events-none`. Jamás compite con la legibilidad (va detrás, con un
  fade-mask que lo concentra arriba/lo desvanece bajo el texto).
- **Baja opacidad por diseño**: es atmósfera, no protagonista. Calmo es el
  default; el control de intensidad (`sutil/media/intensa`) vive en el componente.

### 2.4 Histórico

El subsistema "Red de memoria" original (`MemoryField`, `GrainOverlay`,
`buildMemoryField` con PRNG sembrado) vivió en `packages/ui/src/graphics/` hasta
el PR #148. v4 **no lo restaura tal cual**: lo reescribe como `LivingField`
(canvas, reactivo, variantes). La guía 2026 sigue siendo la fuente del concepto.

---

## 3. Paleta

Identidad cromática: **azul → violeta** sobre dos superficies de marca —
**marfil** (claro) y **Noche** (oscuro). La calidez viene de la superficie marfil
y el grano del canvas, no de un acento cálido nuevo. [marca]

### 3.1 Tema dual — marfil + Noche

> **Cambio v4.** [v4] v3 declaró la app **light-only** (sin dark). v4
> **reintroduce el tema oscuro Noche** como co-protagonista, porque es uno de los
> momentos de más carácter de la marca (el poster oscuro de la guía). El tema se
> togglea por clase en `<html>` (`html.theme-dark`), controlado por el store —
> en el mismo modelo que el override de a11y, sin depender de
> `prefers-color-scheme`. Default: **claro**.

**Superficies — claro (marfil):** *(se conservan de v3, ya fieles a la guía; el
prototipo se toma como referencia para el **tema oscuro**, no para reemplazar el
claro de v3)*

| Rol | Token | Valor |
|---|---|---|
| Canvas (body) | `--color-bg-canvas` | `#FAF9F5` (ivory) [marca] |
| Fondo elevado (cards, inputs, modales) | `--color-bg` | `#FFFFFF` [sobrio] |
| Fondo suave (pills, secciones alternas) | `--color-bg-soft` | `#F3F0EA` (crema) [marca] |

**Superficies — oscuro (Noche):** [v4]

| Rol | Token (en `html.theme-dark`) | Valor | Fuente |
|---|---|---|---|
| Canvas (body) | `--color-bg-canvas` | `#242C3F` (Noche) | [marca] |
| Fondo elevado (cards, vidrios) | `--color-bg` | `#2B3346` (card oscura de la guía) | [marca] |
| Fondo suave | `--color-bg-soft` | `#313A52` | [mock] |

> Regla [research]: **nunca blanco puro como body** (en claro) ni **negro puro**
> (en oscuro). El ivory y el Noche son colores **de la paleta**, planos. El
> color/gradiente vive en el canvas y el logo, **no** en el fondo de la UI.

> **Mecanismo [v4].** El tema oscuro **re-declara los `--color-*` afectados dentro
> de un bloque `html.theme-dark { … }`** (igual que hoy hace
> `html.theme-high-contrast`). Como el `@theme inline` de Tailwind v4 lee
> `var(--color-*)` en runtime, las utilities cambian solas al togglear la clase —
> **no** se crea un segundo `@theme` ni se duplican tokens.

### 3.2 Tinta (texto)

| Rol | Token (claro) | Token (oscuro `theme-dark`) |
|---|---|---|
| Hero/title editorial | `--color-ink-deep` `#1B2233` | `#FFFFFF` |
| Texto principal | `--color-ink` `#242C3F` | `#F3F0EA` (marfil) |
| Secundario | `--color-ink-soft` `rgb(36 44 63 / .65)` | `rgb(243 240 234 / .65)` |
| Terciario | `--color-ink-muted` `… / .45` | `rgb(243 240 234 / .45)` |
| Desactivado | `--color-ink-faint` `… / .18` | `rgb(243 240 234 / .18)` |
| Sobre fondos de marca | `--color-on-dark` `#FFFFFF` | `#FFFFFF` |

> Jerarquía [research]: de-enfatizar **bajando contraste** (soft/muted), no
> agrisando con un gris ajeno a la marca.

### 3.3 Bordes y líneas

| Rol | Claro | Oscuro |
|---|---|---|
| Borde sutil `--color-border` | `rgb(36 44 63 / .12)` | `rgb(243 240 234 / .10)` |
| Borde marcado `--color-border-strong` | `rgb(36 44 63 / .22)` | `rgb(243 240 234 / .18)` |

> Override de a11y: `html.theme-high-contrast` sube el contraste de soft/muted y
> bordes. Hoy en `globals.css` aplica **solo en claro**; extenderlo al tema Noche
> queda **pendiente** (PR de tema Noche, §16 #4). [v4]

### 3.4 Azul de marca y disciplina de gradiente

> **Decisión conservada de v3 [sobrio], respaldada por la guía.** El manual dice
> textual: *"Sin gradientes decorativos: el color trabaja por jerarquía, no por
> adorno."* [marca] El fondo vivo (§2) **no contradice** esa regla: es atmósfera
> ambiental contenida en el canvas, no adorno de relleno. De ahí la disciplina —
> **el gradiente vive solo en (1) el fondo vivo (§2), (2) el logo (isotipo) y
> (3) el glow ambiental del `YnaraOrb` (§8.3) — el orbe es presencia de marca,
> su halo es atmósfera radial, no relleno de UI. Nada más.** Todo lo demás —CTA,
> fills, bordes, texto, dots, tint de modo— es **color plano**. El **tint de
> modo** (`ModeChip`/`SuggestionCard`) es color plano a baja opacidad, no
> gradiente. **Nunca** gradiente como fill o borde de botón, card, dot, texto o
> superficie. [marca + v4]
>
> El guard `apps/web/src/__tests__/gradient-guard.test.ts` hace cumplir esto:
> prohíbe clases de gradiente y `linear/radial/conic-gradient(` inline en
> `components/`/`features/`, con allowlist exacto = los tres portadores de
> arriba (`LivingField.tsx`, `YnaraMark.tsx`, `YnaraOrb.tsx`).

| Token | Valor | Uso |
|---|---|---|
| `--color-blue-flat` | `#2F5AA6` | CTA primario, link, marca |
| `--color-blue-flat-hover` | `#26498A` | Hover |
| `--color-blue-flat-active` | `#1F3C75` | Press |
| `--color-accent` | alias de `--color-blue-flat` | Focus-ring, text-link |

**Stops oficiales de la paleta** (fuente única para gradientes y stops del logo) —
alineados al manual de marca 2026. Nombrados con el prefijo **`--color-*`** (la
única convención del repo) para que entren al `@theme` de Tailwind v4 y generen
utilities `bg-*`/`text-*`:

| Token | Valor | Nombre en la guía |
|---|---|---|
| `--color-azul` | `#2F5AA6` | Azul |
| `--color-indigo` | `#434A82` | Índigo |
| `--color-violaceo` | `#5C6FB3` | Azul violáceo |
| `--color-violeta` | `#8165A3` | Violeta |
| `--color-celeste` | `#6E92CC` | Celeste |
| `--color-lavanda` | `#8B9AD0` | Lavanda (acento, solo ambiente/canvas) |
| `--color-lavanda-deep` | `#565F81` | Lavanda oscuro (fill/texto de Memoria, AA) |
| `--color-noche` | `#242C3F` | Noche |
| `--color-marfil` | `#F3F0EA` | Marfil |

### 3.5 Tints por modo — alineados a la paleta oficial

> **Cambio v4.** [v4] v3 usaba **jade (Bienestar)** y **ámbar (Vida)**, colores
> que **no están en el manual de marca**. v4 los **reencuadra dentro de la
> familia azul→violeta oficial**, para coherencia total con la identidad.

Cada modo tiñe sutilmente `ModeChip`/`SuggestionCard` y define el clima de dos
tonos del **fondo vivo** de su pantalla. **Color base** = el tono ambiental (tint
de chip a baja opacidad + clima del canvas). **Color fill** = el tono que puede
llevar **texto blanco encima** (CTA primaria teñida por modo, icono/texto de
modo); debe pasar **WCAG AA (≥4.5:1) con blanco**:

| Modo | Color base (ambiente) | Color fill (texto blanco) | Blanco/fill | Gradiente (clima del canvas) |
|---|---|---|---|---|
| Productividad | `--color-azul` `#2F5AA6` | `#2F5AA6` | 6.7:1 ✅ | `#2F5AA6 → #6E92CC` (azul → celeste) |
| Estudio | `--color-indigo` `#434A82` | `#434A82` | ~8:1 ✅ | `#434A82 → #6E92CC` (índigo → celeste) |
| Bienestar | `--color-violeta` `#8165A3` | `#8165A3` | 4.9:1 ✅ | `#8165A3 → #8B9AD0` (violeta → lavanda) |
| Vida | `--color-violaceo` `#5C6FB3` | `#5C6FB3` | 4.8:1 ✅ | `#5C6FB3 → #8165A3` (violáceo → violeta) |
| Memoria | `--color-lavanda` `#8B9AD0` | **`--color-lavanda-deep` `#565F81`** | 6.3:1 ✅ | `#6E92CC → #8B9AD0` (celeste → lavanda) |

> **Excepción de contraste — Memoria.** [v4] El lavanda claro `#8B9AD0` es
> precioso como ambiente, pero con texto blanco da **2.75:1 — falla AA**. Por eso
> Memoria es el único modo con **dos tonos**: `--color-lavanda` `#8B9AD0` para
> ambiente/canvas/tint, y **`--color-lavanda-deep` `#565F81`** para cualquier
> **fill o texto** (CTA teñida, icono de modo, el token `--color-memory`). En tema
> **Noche**, donde el texto de modo va claro sobre oscuro, se usa el lavanda claro
> `#8B9AD0` (4.1:1 sobre `#313A52`, ok para icono/acento ≥3:1). Los demás modos
> usan un único tono porque ya pasan AA con blanco.

> Estos gradientes **solo** se usan como: tint de modo (color plano a baja
> opacidad) y clima del fondo vivo (canvas). Jamás como fill de UI (§3.4).

### 3.6 Grano

> **Cambio v4.** [v4] v3 no implementó grano. v4 lo trae **dentro del canvas**
> (variante `paper`, y como capa sutil en las demás), no como overlay global de
> UI. Es "materia física / papel", monocromo, en `soft-light`, baja opacidad.
> Respeta reduced-motion como todo el §2.

### 3.7 Estados y utilitarios

| Rol | Token | Valor |
|---|---|---|
| Error | `--color-error` | `#C0392B` |
| Error suave | `--color-error-soft` | `rgb(192 57 43 / .12)` |
| Overlay (backdrop) | `--color-overlay` | `rgb(36 44 63 / .40)` |

### 3.8 Contraste

- Compliance: **WCAG 2.1 AA** mínimo (AAA en hero/CTA). **APCA** como guía de
  diseño, sobre todo en el tema **Noche** (Lc ~75+ body, ~60 secundario). El
  texto siempre va **sobre la superficie plana** (no sobre el canvas), que está
  detrás con fade-mask — el contraste se mide contra el plano, no contra la
  atmósfera. [research]
- **Colores de modo como fill/texto**: cualquier color de modo que lleve texto
  encima se verifica contra ese texto, no solo contra el fondo. Todos pasan AA con
  blanco salvo el lavanda claro de Memoria (`#8B9AD0`, 2.75:1) — por eso su fill
  usa `--color-lavanda-deep` `#565F81` (§3.5). El **tint ambiental** (chip a baja
  opacidad, canvas) no lleva texto y no entra en esta regla.
- **Deuda conocida [v4]:** `--color-ink-muted` (`rgb(36 44 63 / .45)`) se usa hoy
  como texto/placeholder/label y da ~3.4:1 sobre blanco — **falla AA**. Es la
  violation `serious` que axe reporta y que el gate hoy ignora. El PR de QA
  (§16 #11) la corrige (el texto real pasa a `ink-soft` 0.65) **antes** de endurecer
  el gate.

---

## 4. Tipografía

*(Se conserva íntegra de v3 — está bien resuelta.)*

| Familia | Para | Pesos |
|---|---|---|
| **Space Grotesk** | Display (hero, títulos, marca, big type) | 500, 700 |
| **DM Sans** | Body, botones, UI, captions | 400, 500, 600 |

Regla: **jamás Space Grotesk en body**. Escala fluida con `clamp(rem + vw)`,
anclas ~360→~1240px. Tracking negativo en display (`-0.03`/`-0.04em`),
line-height 1.04–1.12; body 1.5–1.6, tracking ~0; labels uppercase `+0.06em`;
datos/timestamps `tabular-nums`; **measure de lectura 60–70ch** (respuesta del
asistente, §10). Comillas curvas y em-dash reales en copy. Tokens y escala en
`globals.css` (`text-hero`, `text-title`, `text-subtitle`, `text-body`, …).

---

## 5. Spacing

Escala base 4, sin tokens propios (Tailwind v4 default). **Spacing no uniforme**:
más aire entre grupos distintos que entre elementos del mismo grupo. *(Igual que
v3.)*

---

## 6. Radius

`--radius-sm` 8px · `--radius-md` 12px · `--radius-lg` 16px · `--radius-xl` 20px ·
`--radius-pill` 9999px. *(Igual que v3.)*

---

## 7. Elevation

3 niveles. Más allá → revisar jerarquía, no agregar sombra.

| Utility | Claro | Oscuro (`theme-dark`) |
|---|---|---|
| (ninguna) | — | — |
| `.shadow-soft` | `0 1px 2px /.06, 0 4px 12px /.04` | sombras + borde hairline (la profundidad en Noche viene más del borde que de la sombra) |
| `.shadow-lifted` | `0 8px 24px /.08, 0 24px 48px /.06` | ídem, alphas recalibrados sobre Noche |

> En **Noche**, una card (`#2B3346`) se separa del canvas (`#242C3F`) por la
> diferencia de superficie + el borde hairline, no por sombra pesada. [v4]

---

## 8. Motion

### 8.1 Tokens

Set completo de duración (las micro del §8.2 y los toasts los referencian):

| Token | Valor | Uso | Estado |
|---|---|---|---|
| `--duration-instant` | `100ms` | Press/tap inmediato (`PromptChip`) | **a definir** en `globals.css` |
| `--duration-fast` | `150ms` | Hover/focus, micro | **a definir** en `globals.css` |
| `--duration-base` | `250ms` | Transiciones estándar | definido |
| `--duration-screen` | `350ms` | Cambio de pantalla | definido |
| `--duration-slow` | `300ms` | Toast-in, secuencias suaves | **a definir** en `globals.css` |
| `--ease-out-soft` | `cubic-bezier(0.22, 1, 0.36, 1)` | Easing default | definido |

> **Deuda heredada [v4].** Hoy `globals.css` solo define `--duration-base` y
> `--duration-screen`. `motion.css` y ~12 componentes ya usan `--duration-fast`,
> `--duration-slow` y `--duration-instant` (`PromptChip.tsx:26`), que **solo
> resuelven por fallback inline** o, **sin fallback, animan en 0ms** (caso de
> `--duration-fast` en `Card`/`AppNav`/`ChatComposer`/`RecapCta`/…). El PR de
> tokens (§16) **debe definir los tres** en `globals.css` para cerrar el set.

Modelo reduced-motion idéntico a v3 (`motion-off`/`motion-on` override).

### 8.2 Microinteracciones *(de v3, vigentes)*

Hover `scale(1.02)` 150ms · Press `scale(0.97-0.98)` 100ms · Focus ring 150ms ·
Stagger de entrada (fade + `translateY` 8-12px, delay 30-50ms × i, máx ~6) ·
Skeleton shimmer · Toast 300/200ms.

### 8.3 Motion con significado de marca [v4]

El movimiento **expresa el concepto** (§1), no decora:

- **Presencia** → el **campo reactivo al cursor** (§2.1): el espacio responde a
  vos. Y el **orbe** de Ynara (presencia viva) que late al "pensar".
- **Memoria/Conexión** → el campo de nodos que deriva y se enlaza lento.
- **Transición de pantalla** → **crossfade** suave (la saliente se desvanece
  mientras entra la nueva), no corte seco. Shared-element donde aplique (View
  Transitions API con progressive enhancement).

> v3 había sacado el motion conceptual al deprecar el sistema gráfico. v4 lo
> recupera atado al fondo vivo, con todas las reglas de performance del §2.3.

### 8.4 Implementación y reglas *(de v3, vigentes)*

Animar **solo `transform`/`opacity`** (GPU). View Transitions API con fallback.
GSAP para secuencias; CSS keyframes para micro; Lenis para smooth scroll en
páginas largas (no en formularios). `prefers-reduced-motion` global con override.
❌ Animaciones >500ms en UI utilitaria, bounce excesivo, loops decorativos
infinitos **en la UI** (el campo vivo del §2 es la excepción documentada y
acotada, con reduce-motion respetado).

---

## 9. Iconografía

*(Igual que v3.)* Set propio con el ADN de la marca: **trazo uniforme + el
diamante como acento**. Íconos: Idea, Conexión, Memoria, Nota, Buscar, Diálogo,
Recordatorio, Adaptación, Foco, Red. Fallback Lucide solo para utilitarios que el
set no cubra, mismo grosor de trazo. ❌ Nunca emojis ni flechas como íconos.

---

## 10. Chat UI / asistente

*(Se conserva de v3 — ya está alineado con el prototipo.)* El asistente se siente
**editorial, no mensajería**:

- **Asistente sin burbuja**: prosa a measure 60-70ch (~680-720px), markdown
  completo, line-height 1.5-1.6.
- **Usuario**: contenedor liviano a la derecha, no burbuja pesada.
- **Composer** vivo (autosize, Enter envía / Shift+Enter newline, draft/sending/
  streaming/disabled; durante streaming el enviar se vuelve **Detener**).
- **Streaming**: token a token, cursor sutil, bufferizar markdown incompleto,
  indicadores con voz (pensando/buscando/generando), tool-calls `memory.*` como
  acordeones.
- **Auto-scroll inteligente**: seguir solo si estás cerca del fondo; si scrolleás
  arriba, pausar + botón "ir al final".
- **Empty state**: big type + voz de marca, con el **fondo vivo** (variante
  `constellation`) como capa ambiental + 3-4 chips de prompt accionables.
- a11y: `aria-live="polite"`, orden de tab predecible, no robar foco al terminar.

---

## 11. Componentes (primitives)

Primitives web-only en
[`apps/web/src/components/ui/`](./apps/web/src/components/ui/).

| Componente | Notas |
|---|---|
| `Button` | `primary` usa `--color-blue-flat` **plano** + hover/active. |
| `Card` | `interactive`: `shadow-soft` + hover `scale(1.02)`. |
| `OptionCard` | Selected: fondo ink + **ring azul plano** (`--color-blue-flat`). Sin gradiente (§3.4). |
| `TextField`/`Textarea`, `Toggle`, `ChipGroup` | Tokens, error inline humano. |
| `PromptChip`, `ProgressDots` (active = **azul plano**), `Toast` | `Toast` success hoy usa gradiente como fill → migrar a plano (§3.4/§16). |
| `Icon` | Set propio (§9). |
| `ModeChip`/`SuggestionCard` | Tint del modo plano a baja opacidad (§3.5). Texto/icono de modo y `--color-memory` usan el tono **fill** (Memoria → `--color-lavanda-deep`). |
| `YnaraMark` | Logo SVG. Símbolos: color / mono-dark / mono-light / avatar. |
| `YnaraWordmark` [v4] | **Lockup oficial**: símbolo (22×22) + "Ynara", con la **misma base** (los pies de la Y caen sobre la baseline del texto, y≈19.8). Variante por fondo: color sobre claro/neutro, mono-light sobre Noche. Reemplaza los lockups armados a mano con `align-items:center`. |
| `LivingField` [v4] | **Fondo vivo en canvas** (§2). Reemplaza a `BrandWaves`. Props: `variant`, `mode`, intensidad. |
| `EmptyStateCard` | Estados vacíos sobrios. |

Cada componente en su archivo, named export, sin barrel monstruo.

### 11.1 Uso correcto del logo [v4]

Aplica también a **posiciones, márgenes, fondos y contraste**:

- **Variante por fondo**: símbolo **a color** sobre claro/neutro; **mono-light**
  (`#F3F0EA`) sobre Noche o fondos de marca; **mono-dark** (`#242C3F`) sobre
  claro cuando se quiere mono; **avatar** (cuadrado redondeado) solo como
  app-icon, nunca inline en un lockup.
- **Lockup símbolo+wordmark**: usar `YnaraWordmark` (baseline compartida), nunca
  `align-items:center` a mano.
- **Clear-space**: aire mínimo alrededor ≥ la altura del símbolo. No apretar el
  logo contra bordes.
- **Contraste**: jamás el símbolo a color (con la "Y" azul) sobre Noche — pierde
  contraste; ahí va mono-light.

---

## 12. Reglas visuales transversales

- Contraste **WCAG AA** mín., **AAA** en críticos; APCA como guía (sobre todo en
  Noche).
- `prefers-reduced-motion` respetado, override desde a11y (incluye el fondo vivo).
- Tap targets ≥ **44×44px**.
- Focus rings con identidad (anillo doble `--color-bg` + `--color-accent`).
- **Mobile-first**. Breakpoints `sm:640 md:768 lg:1024 xl:1280`.
- **Tema dual declarado** [v4]: marfil (default) + Noche, vía `html.theme-dark`
  desde el store. Sin `prefers-color-scheme` (la elección es del usuario, no del
  OS).
- **Gradiente solo en canvas + logo** (§3.4). Todo fill, borde y dot de UI es
  plano.
- **Layout editorial / des-encajonado** [v4]: listas aireadas separadas por
  hilos finos (no cajas), una sola superficie suave por pantalla, **medida de
  texto acotada** y datos (hora/chevron) al borde derecho en filas anchas
  (ancho 100%, sin contenedor centrado que deje franjas del fondo en los
  márgenes).

---

## 13. Anti-patterns

Errores de implementación: ❌ hex hardcodeado (siempre token) · ❌ Space Grotesk
en body · ❌ animar `width/height/top/left` · ❌ `outline:none` sin reemplazo ·
❌ sombras superpuestas · ❌ disabled sin explicación · ❌ toast para error de
form (usar inline) · ❌ loops decorativos infinitos **en la UI**.

"Tells" del look AI/amateur a evitar [research]: ❌ blanco puro como body (claro)
o negro puro (Noche) → superficies de marca · ❌ **gradiente de relleno en UI** +
glassmorphism porque sí → gradiente solo en canvas/logo (§3.4) · ❌ emojis/flechas
como íconos → set propio · ❌ todo centrado y simétrico / grid de 3 cards
idénticas → layout intencional · ❌ jerarquía solo por tamaño → peso + contraste ·
❌ spinners genéricos → skeletons + voz · ❌ banding en gradientes → el grano del
canvas (§3.6).

---

## 14. Migración v3 → v4 (deltas)

v4 **conserva la ingeniería** de v3 y **sube la vara de diseño** al prototipo.

| Área | v3 (sobrio) | v4 (sistema vivo) | Tipo |
|---|---|---|---|
| Tema | light-only | **marfil + Noche** (`html.theme-dark`) | reintroduce |
| Fondo ambiental | `BrandWaves` (SVG estático) | **`LivingField`** (canvas: ondas + nodos + blooms + reactivo al cursor, por variante) | reescribe |
| Modos Bienestar/Vida | jade / ámbar (fuera del manual) | **violeta / violáceo** (paleta oficial) | realinea |
| Color de Memoria | `--color-memory` = `--color-violet-to` (violeta) | **lavanda** `#8B9AD0` (ambiente) + `--color-lavanda-deep` `#565F81` (fill/texto, AA) | realinea |
| Grano | no implementado | **dentro del canvas** (variante `paper` + capa sutil) | reintroduce |
| Motion conceptual | sacado | **campo reactivo + crossfade de pantalla + orbe** | reintroduce |
| Logo lockup | armado a mano (`align-items:center`) | **`YnaraWordmark`** con baseline compartida + reglas de uso (§11.1) | agrega |
| Layout | sobrio | **editorial des-encajonado + medida acotada** (§12) | refina |
| CTA primario | azul plano | azul plano | **conserva** |
| Disciplina de gradiente | gradiente solo como acento | gradiente solo en canvas/logo/acento | **conserva + refuerza** |
| Arquitectura de tokens | CSS vars + `@theme` | igual (extendida para Noche + paleta) | **conserva** |
| a11y (alto contraste, motion override, focus) | sí | igual (extendido a ambos temas + al campo vivo) | **conserva** |
| Escala tipográfica fluida | sí | igual | **conserva** |
| Primitivas | sí | igual + `YnaraWordmark` + `LivingField` | **conserva + agrega** |

> Lo que v4 **no toca**: el backend, la memoria, la config de modos
> (`ynara.config.json`), ni ninguna regla del `AGENTS.md`. Es puramente la capa
> visual del frontend.

---

## 15. Referencias

- [`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) — tokens.
- [`apps/web/src/styles/motion.css`](./apps/web/src/styles/motion.css) — keyframes.
- [`apps/web/src/components/ui/`](./apps/web/src/components/ui/) — primitives
  (incluye `LivingField`, `YnaraWordmark`).
- [`docs/brand/Ynara-Universo-de-Marca.html`](./docs/brand/Ynara-Universo-de-Marca.html)
  — **Guía de identidad visual 2026** (fuente de paleta, sistema gráfico,
  iconografía, logo y aplicaciones). Ya versionada en el repo (ver
  [`docs/brand/README.md`](./docs/brand/README.md)).
- [`IDENTITY.md`](./IDENTITY.md) — ADN de marca.
- [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md) — voz por modo.
- Prototipo de referencia (fuente de v4): el mock del dueño — Vite + React, con el
  sistema vivo completo (campo reactivo, tema dual, lockup, layout editorial).

---

## 16. Plan de implementación (v3 → v4)

> **Salud de base (auditoría total de front, 2026-06).** El frontend v3 está
> **bien construido**: `tsc --noEmit` limpio, 165 tests de Vitest en verde,
> disciplina de tokens altísima (cero hex hardcodeado fuera del SVG del logo),
> icon-set propio, a11y sólida (skip-link, focus-trap nativo, pre-paint anti-FOUC),
> arquitectura feature-based sin imports cruzados. El riesgo **no** está en lo
> heredado sino en (1) lo que v4 agrega (canvas + Noche), (2) deudas que el plan
> subestimaba (dedup divergente, contraste sistémico de `ink-muted`, streaming
> a11y), y (3) la **falta de red de seguridad**: `biome` está **rojo en la base**
> (19 errores), no hay CI de frontend, y hay **cero tests de tokens/color/tema**.

Cada item es un **PR atómico** (rama desde `origin/main` → commits chicos en
español, Conventional, scope `web` → `ynara-doctor` exit 0 → gates locales →
review → rebase merge).

> **No hay CI de frontend.** Los PRs que solo tocan `apps/web/**` **no disparan**
> `biome`/`tsc`/`vitest`/`build` ni las guards de commits (la CI está scopeada a
> `apps/backend/**`). Los gates se corren **a mano, siempre**:
>
> ```
> bash scripts/ynara-doctor.sh   # exit 0 — check 9 (sin tailwind.config) y check 10 (rama deriva de origin/main)
> pnpm biome check .
> pnpm turbo run typecheck        # tsc strict
> pnpm turbo run test             # vitest
> ```
>
> El hook `biome-check` de `.pre-commit-config.yaml` está pinneado a **biome@2.0.0**
> (el repo usa **2.4.15**) y es **opt-in** — no es red de seguridad confiable.

Orden sugerido:

**0. `chore(web)` — verde de base (prerequisito de todo).** Hoy `pnpm biome check .`
da **exit 1 (19 errores)**: 14 de formato + 2 de imports (auto-fix con
`biome check . --write`) + 3 de a11y a mano (`OnboardingHeader.tsx:102,104`,
`StepShell.test.tsx:79`). Sumar un **test de tokens/utilities** (render de `/test-ds`
o assert de que `bg-azul`/`text-*`/`bg-mode-*` resuelven) — hoy **no existe** y es el
único que atraparía "token solo en `:root` → utility no generada". Sin este PR, todo
PR posterior arranca con el gate rojo y el ruido tapa regresiones nuevas.

**1. `docs(design)` — este bump del `DESIGN.md` a v4.** *(este PR)* Aprobación de
**@MateoGs013** + CODEOWNERS. El scope `design` no es canónico en `COMMITS.md`; usar
`docs(conventions)` o blesear `design`.

**2. `feat(web)` — tokens base (paleta + motion).** En `globals.css`: los 9 stops
oficiales (`--color-azul`…`--color-marfil`) **+ `--color-lavanda-deep`**, en `:root`
**y** en `@theme inline`. Definir `--duration-instant: 100ms`, `--duration-fast:
150ms`, `--duration-slow: 300ms` (hoy ~13 archivos animan en 0ms sin fallback).
Definir o quitar la utility **fantasma `text-display`** (referenciada en
`test-ds/page.tsx:34,73`, no existe en `globals.css`).
- *Landmine:* el `@theme inline` lista token por token — declararlos solo en
  `:root` **no** genera las utilities. El test del PR #0 lo cubre.

**3. `feat(web)` — modos azul→violeta + tint plano + dedup + Memoria.** Cambiar los
5 `--mode-*` de jade/ámbar/violeta a la familia oficial (§3.5). **Cambio de raíz:**
`components/ui/modes.ts` expone hoy `gradientClass: bg-mode-${id}` como **contrato de
tipo** — migrarlo a un token de color **plano** (`tintVar`/`fillVar`) propaga el fix
a los 6 call-sites de una. Esos call-sites (todos gradiente-de-modo hoy): `ui/ModeChip`,
`ui/SuggestionCard`, `today/ModeChip`, `today/SuggestionCard`, **`chat/MessageBubble.tsx:67`**
(hairline del asistente — no estaba en el plan) y `test-ds`. Remapear `--color-memory`
→ `--color-lavanda-deep` (4 callers icono → sube contraste). Migrar `Toast.tsx:20` de
gradiente a plano.
- *Landmine (corregido):* `today/ModeChip` y `today/SuggestionCard` **no son copias**
  de los primitives — **divergieron** (uno es `<li>` display, otro `<button>`; APIs y
  tokens distintos). Deduplicar = unificar API + migrar 3 call-sites
  (`HoyHeader.tsx:22`, `ChatHeader.tsx:25`, `SuggestionsSection.tsx:46`), no un merge
  mecánico. Agregar tests de color a cada primitive (hoy ninguno los cubre).
- *Guard:* sumar un check grep-based (no hay CI front) que falle ante
  `bg-mode-*`/`bg-gradient-*`/`gradientClass` en `components/**`/`features/**`
  (excepto `LivingField`/`YnaraMark`/`globals.css`), para atajar regresiones del
  anti-patrón §3.4/§13.

**4. `feat(web)` — tema Noche (greenfield).** Bloque `html.theme-dark { … }`
re-declarando `--color-*` (canvas/bg/bg-soft, 5 inks, on-dark, 2 bordes,
`--color-memory`→`#8B9AD0`, elevación §7). Extender `html.theme-high-contrast` a
Noche (hoy es **light-only**; se re-declara bajo `html.theme-dark.theme-high-contrast`).
**Store de tema propio (`ynara.theme`)** clonando `stores/a11y.ts` — **no** extender
el store de a11y (arrastraría el mirror del draft de onboarding y el `reset()`).
**Bloqueante:** resolver el `data-theme="light"` hardcodeado en `layout.tsx:27` y
extender el pre-paint `a11y-init.ts` a leer también la key de tema **antes del primer
paint**.
- *Landmine (alto):* FOUC/hydration garantizado sin el pre-paint. `@theme inline`
  relee `var()` en runtime → re-declarar basta; no crear un segundo `@theme`. Sumar
  test del store + e2e que togglee y verifique `html.theme-dark`.

**5. `feat(web)` — `LivingField` (canvas) + retiro de `BrandWaves`.** Portar
`canvas-field.jsx` + la lógica de `CalmBg` a `apps/web/src/components/ui/LivingField.tsx`
(`'use client'`). Crear `YnaraOrb`. Grano: capa CSS estática para `paper`.
**Prerequisito:** promover `useActiveMode` (hoy **local en `HoyView.tsx:15`**) a un
hook/store compartido — Chat y Memoria lo necesitan para el canvas reactivo al modo.
**Decisión de montaje:** el fondo hoy vive por-vista (no en layout); `AppShell` crea
`isolate` → `LivingField` va **`absolute` dentro del shell, nunca `fixed`** (el
`-z-10` quedaría atrapado). Migrar `onboarding/layout.tsx:39` (`constellation`) y
`HoyView.tsx:59` (`aurora`); montajes **nuevos** en Chat (`constellation`) y Memoria
(`network`). `paper`/`depth` pendientes (Agenda/Tu no existen). Retirar
`BrandWaves.tsx` + `waves-light.svg` + 6 comentarios stale.
- *Landmines:* (a) reduced-motion del canvas **en JS** con `prefersReducedMotion()`
  / `useReducedMotion` (reaccionando al store en runtime), no el `matchMedia` crudo;
  el CSS no frena el `rAF` (será el primer loop de `rAF` del repo). (b) Cleanup
  completo (cancelar `rAF` + remover los 5 listeners de `window`) o leakea por
  navegación — agregar test de unmount. (c) `BrandWaves.variant` (posición) ≠
  `LivingField.variant` (textura). (d) O(N²) de hilos a densidad `intensa` en mobile;
  DPR≤2; cuidado con 120Hz (velocidad x2).

**6. `feat(web)` — `YnaraWordmark` + uso del logo.** Crear `YnaraWordmark` (lockup
baseline, y≈19.8). Sumar a `YnaraMark` los símbolos **mono-dark `#242C3F` /
mono-light `#F3F0EA` / avatar** + prop de variante por fondo. Migrar el lockup a mano
de `AppNav.tsx:63`. **Migrar los stops del SVG** (`YnaraMark.tsx:32-55`) a los tokens
oficiales en este mismo PR (si no, cae a hex hardcodeado). Extender `snap-logo.mjs`
para capturar el lockup nuevo.

**7. `feat(web)` — sistema de motion (Lenis + GSAP).** Cablear las dos deps hoy
instaladas con **0 imports** (§8.4), al servicio de la inmersión y la experiencia
única de la marca:
- **Lenis** — smooth-scroll en páginas largas (Chat, timeline de Memoria), **nunca
  en formularios ni en el step-flow del onboarding**. Montado en el shell, con
  `destroy()` bajo reduced-motion (`useReducedMotion`/store) y cleanup en unmount.
- **GSAP** — registrar una sola vez; gatear **todo** con `gsap.matchMedia()` +
  reduced-motion + el override del store; patrón `useGSAP` (cleanup de contexto
  automático). Reservado para **secuencias / momentos-firma** (entrada del hero, orbe
  "pensando", reveal del recap), no para micro (eso queda en CSS keyframes, §8.2).
- *Landmines:* (a) Lenis **pelea con el `scrollIntoView`/scroll-anchor del chat**
  (§10) — desactivarlo o usar `lenis.scrollTo` en esas vistas. (b) Lenis corre su
  propio `rAF` → mismo riesgo de leak que el canvas: destruir bajo reduced-motion y
  al desmontar. (c) GSAP sin `matchMedia` ignora la preferencia de motion — gatear
  siempre. (d) Lenis hijackea el scroll → verificar teclado (PgUp/Down/Home/End),
  `scroll-padding` del skip-link y el focus-scroll de a11y.

**8. `feat(web)` — crossfade de pantalla (§8.3).** Cablear `startViewTransition`
(`lib/viewTransition.ts` existe pero con **0 callers**) + reglas CSS
`view-transition-name` (View Transitions API; GSAP del #7 queda para las secuencias,
no para el crossfade de ruta). **Prerequisito:** no hay `loading.tsx`/`error.tsx` en
ninguna ruta y 4 rutas son `force-dynamic` (`chat/[sessionId]`, `memoria/[id]`,
`buscar`, `onboarding/[step]`) → un crossfade sobre navegación dynamic puede mostrar
frame en blanco. Agregar `loading.tsx` por segmento (al menos en `(app)`)
antes/dentro.

**9. `feat(web)` — a11y de chat/streaming (§10).** *(net-new — sin dueño en el plan
anterior.)* Región `aria-live="polite"` **dedicada al mensaje en curso** (hoy está
sobre toda la lista, `MessageList.tsx:46` → spamea al lector con streaming),
`aria-busy` durante el stream, auto-scroll inteligente (seguir solo si estás cerca
del fondo) y no robar foco al terminar. **Coordinar con Lenis (#7)**: el smooth-scroll
no debe pelear con el auto-scroll del stream.

**10. `feat(web)` — layout editorial por vista.** Medida acotada, des-encajonado,
datos al borde, una superficie suave por pantalla (§12). Alcance: **Chat landing
(`/chat`) es un stub** — aplica a la conversación (`chat/[sessionId]`), Memoria, y
**`/buscar`** (vista completa hoy sin lugar en la nav). Hoy ya migrado.

**11. `feat(web)` — QA de contraste + endurecer red.** **Orden duro:** primero
arreglar el contraste sistémico de **`--color-ink-muted` (0.45)** usado como
texto/placeholder/label (falla AA ~3.4:1 en toda la app, no solo Memoria) — el texto
real pasa a `ink-soft` (0.65); **después** endurecer axe de `critical` a incluir
`color-contrast` `serious` (`onboarding.spec.ts:31`), o el gate falla de entrada.
Sumar axe en las vistas nuevas (Chat/Memoria/Buscar) y en **Noche** (hoy solo cubre
auth + Hoy en claro), assert de que `LivingField` no aparece en el a11y-tree, y
snapshot visual de `/test-ds` en claro+Noche (esperando `mocksReady`; MSW bloquea el
render en dev).

> **Decisión abierta.**
> - **Virtualization**: ni el timeline de Memoria ni el chat virtualizan. Invisible
>   con mocks; va a doler con historiales reales. Deuda explícita (no bloquea v4).
>   Cobra más peso con Lenis (#7) activo: smooth-scroll sobre listas largas
>   sin virtualizar amplifica el costo por frame.

> **Gobernanza (inquebrantable).** Nada se commitea ni pushea sin OK humano
> explícito (regla #1). `main` solo se actualiza por **PR mergeado** (rebase, sin
> merge commit); nunca push directo, merge local, ni force-push a `main`.
> `DESIGN.md` y todo `.md` raíz requieren aprobación de **@MateoGs013** +
> CODEOWNERS. Commits **atómicos** (regla #7): tokens, modos+dedup y tema Noche son
> los más pesados — splitear en commits chicos. v4 **no toca** backend, memoria,
> `ynara.config.json` ni ninguna regla de `AGENTS.md`.
