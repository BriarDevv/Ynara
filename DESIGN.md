# Sistema de Diseño de Ynara

Este archivo es la fuente de verdad del sistema visual de Ynara. Cualquier divergencia entre código y este doc se resuelve actualizando el código, no el doc — los tokens reales viven en [`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) y este doc es la documentación legible de esos tokens.

> **Aprobación**: cualquier cambio sustantivo a este archivo requiere PR con review de @MateoGs013 (CODEOWNER). Para cambios que afecten identidad de marca (paleta, tipografía), revisar también con @BriarDevv y @querques20.

---

## 1. Esencia de marca

Tres atributos que la UI debe respirar siempre:

- **Claridad** — jerarquía visual obvia, sin ruido decorativo, copy directo.
- **Calma** — espacio para respirar, contrastes que no agreden, motion que acompaña.
- **Profundidad** — gradientes contenidos como acento, no decoración. Sobriedad técnica.

Lo que la UI **no es**: infantil, ñoña, recargada, ruidosa, "Material Design genérico".

Para detalle conceptual ver [`IDENTITY.md`](./IDENTITY.md).

---

## 2. Paleta

### 2.1 Colores base

| Rol | Token CSS | Valor |
|---|---|---|
| Texto principal | `--color-ink` | `#242C3F` (azul-tinta profundo, no negro puro) |
| Texto secundario | `--color-ink-soft` | `rgba(36, 44, 63, 0.65)` |
| Texto terciario | `--color-ink-muted` | `rgba(36, 44, 63, 0.45)` |
| Texto desactivado | `--color-ink-faint` | `rgba(36, 44, 63, 0.18)` |
| Fondo base | `--color-bg` | `#FFFFFF` |
| Fondo suave (cards, secciones) | `--color-bg-soft` | `#F6F6F8` |
| Borde sutil | `--color-border` | `rgba(36, 44, 63, 0.12)` |
| Borde marcado | `--color-border-strong` | `rgba(36, 44, 63, 0.22)` |
| Texto sobre fondos oscuros | `--color-on-dark` | `#FFFFFF` |

### 2.2 Gradientes

Tres gradientes con uso semántico claro:

| Gradiente | Token | Stops | Uso |
|---|---|---|---|
| Azul base | `--gradient-blue-base` | `#2F5AA6 → #1F66DB` (135deg) | CTA primario, marca, modo Productividad |
| Azul relief | `--gradient-blue-relief` | `#4B7EE6 → #7BA1F4` (135deg) | Glow, highlights, modo Estudio |
| Violeta | `--gradient-violet` | `#8C63B8 → #7C4FA3` (135deg) | Símbolo de memoria — modo Memoria, recall, outro del onboarding |

**Regla clave**: el gradiente azul base es el rasgo más identitario. El CTA primario lo usa. No se reemplaza por color sólido salvo en casos donde el gradiente afectaría la legibilidad (botones muy chicos, chips densos).

### 2.3 Tints por modo

Cada modo tiene un tint sutil para `ModeChip` y `SuggestionCard`:

| Modo | Token de tint | Carácter |
|---|---|---|
| Productividad | `--gradient-blue-base` | Azul base — acción, ejecución |
| Estudio | `--gradient-blue-relief` | Azul claro — claridad, expansión |
| Bienestar | `--gradient-jade` (`#4A9C8C → #6FBFAE`) | Jade — calma |
| Vida | `--gradient-amber` (`#D9A24A → #E8C77A`) | Ámbar — cotidiano cálido |
| Memoria | `--gradient-violet` | Violeta — el símbolo del logo |

> Bienestar y Vida son propuesta inicial; revalidar con @querques20 en review.

### 2.4 Dark mode (discreto)

Activado con `[data-theme="dark"]` o `prefers-color-scheme: dark`, override desde store de a11y.

| Token | Light | Dark |
|---|---|---|
| `--color-bg` | `#FFFFFF` | `#0E1219` |
| `--color-bg-soft` | `#F6F6F8` | `#161B25` |
| `--color-ink` | `#242C3F` | `#E8ECF4` |
| `--color-ink-soft` | `rgba(36,44,63,0.65)` | `rgba(232,236,244,0.70)` |
| `--color-ink-muted` | `rgba(36,44,63,0.45)` | `rgba(232,236,244,0.50)` |
| `--color-border` | `rgba(36,44,63,0.12)` | `rgba(232,236,244,0.12)` |

Los gradientes no cambian — son los mismos en ambos modos.

---

## 3. Tipografía

### 3.1 Familias

| Familia | Para | Pesos | Source |
|---|---|---|---|
| **Space Grotesk** | Display (hero, títulos, subtítulos, marca) | 500, 700 | `next/font/google` |
| **DM Sans** | Body, botones, captions | 400, 500 | `next/font/google` |

Regla: **jamás Space Grotesk en body**. Es display.

### 3.2 Escala

Base 16px. Valores en `rem`:

| Token | Tamaño / line-height / letter-spacing | Uso |
|---|---|---|
| `text-hero` | `3rem` / `3.25rem` / `-0.05em` | Hero de welcome |
| `text-title` | `2.125rem` / `2.375rem` / `-0.03em` | Título de step / sección |
| `text-subtitle` | `1.375rem` / `1.75rem` / `-0.018em` | Subtítulo |
| `text-body` | `1rem` / `1.5rem` / `-0.006em` | Cuerpo |
| `text-body-sm` | `0.875rem` / `1.25rem` / `-0.003em` | Helper, hints |
| `text-caption` | `0.75rem` / `1rem` / `+0.06em` UPPERCASE | Labels, etiquetas |
| `text-button` | `1rem` / `1.25rem` / `-0.006em` | Botones |

### 3.3 Sizing accesible

El store de a11y puede aplicar `text-size-sm`, `text-size-md` (default), o `text-size-lg` al `<html>`. Cada clase ajusta el `font-size` base del `<html>` (`15px` / `16px` / `18px`), y toda la escala escala con `rem`.

---

## 4. Spacing

Escala base 4. **Sin tokens propios**: usamos la escala default de Tailwind v4 (`p-1` = 4px, `p-2` = 8px, …) para minimizar superficie de tokens y facilitar onboarding. Esta tabla documenta el uso semántico, no introduce variables CSS nuevas.

| Token Tailwind | Valor | Uso típico |
|---|---|---|
| `1` (`xs`) | `4px` | Microajustes, gap mínimo |
| `2` (`sm`) | `8px` | Gap entre elementos relacionados |
| `3` (`md`) | `12px` | Padding pequeño |
| `4` (`base`) | `16px` | Padding default, gap de cards |
| `6` (`lg`) | `24px` | Padding de cards, gap entre secciones |
| `8` (`xl`) | `32px` | Sección |
| `12` (`2xl`) | `48px` | Bloque grande |
| `16` (`3xl`) | `64px` | Margen vertical de hero |

---

## 5. Radius

| Token | Valor | Uso |
|---|---|---|
| `radius-sm` | `8px` | Inputs chicos, chips |
| `radius-md` | `12px` | Botones, cards default |
| `radius-lg` | `16px` | Cards prominentes, modales |
| `radius-xl` | `20px` | Hero cards, contenedores grandes |
| `radius-pill` | `9999px` | Pill chips |

---

## 6. Elevation

3 niveles. Más allá de eso → revisar jerarquía, no agregar sombra.

Implementados como **utilities custom** en `globals.css` (no como CSS vars), porque la composición de sombra interna del navegador no se beneficia de la indirección var().

| Utility | Sombra | Uso |
|---|---|---|
| (ninguna) | — | Cards default, inputs |
| `.shadow-soft` | `0 1px 2px rgb(36 44 63 / 0.06), 0 4px 12px rgb(36 44 63 / 0.04)` | Cards interactivas, hover |
| `.shadow-lifted` | `0 8px 24px rgb(36 44 63 / 0.08), 0 24px 48px rgb(36 44 63 / 0.06)` | Modales, toasts, dropdowns |

---

## 7. Motion

### 7.1 Reglas globales

- Easing default: `cubic-bezier(0.22, 1, 0.36, 1)` (out expo suave). Token: `--ease-out-soft`.
- Duración base: `250ms`. Token: `--duration-base`.
- **Toda animación dentro de `@media (prefers-reduced-motion: no-preference)`**.
- Override manual desde Step 5 del onboarding (a11y): cuando `motion-reduced` está activo en `<html>`, todas las animaciones tienen duración `0.001ms`.

### 7.2 Lenguaje de motion

| Patrón | Duración | Easing | Cuándo |
|---|---|---|---|
| Entrada de pantalla | `350ms` | `ease-out-soft` | Cambio de step, navegación |
| Entrada de elemento (stagger) | `420ms` con delay 80ms x i | `ease-out-soft` | Listas de cards apareciendo |
| Selección | `200ms` spring (damping 18) | spring | Tap/click en OptionCard |
| Confirmación | `400ms` | `ease-out-soft` | Gradient sweep en submit exitoso |
| Pulse (símbolo de memoria) | `1500ms` | `ease-in-out` | YnaraMark al guardar memoria, outro del onboarding |
| Toast | `300ms` in, `200ms` out | `ease-out-soft` | Notificaciones |

### 7.3 Implementación

- GSAP para animaciones complejas (transiciones de step, outro).
- CSS keyframes para microinteracciones (toast, hover).
- Lenis para smooth scroll (modo "calma" en páginas largas; no usar en formularios).

---

## 8. Componentes (primitives)

Los primitives web-only viven en [`apps/web/src/components/ui/`](./apps/web/src/components/ui/) (regla del repo: el `packages/ui` está reservado para cosas web/mobile-portables RN-compatibles).

> **Deuda explícita**: `YnaraMark.tsx` (SVG puro) y `modes.ts` (type-only + readonly array) son **portables a mobile** sin cambios significativos. Cuando arranque la sesión mobile, mover `YnaraMark` a `packages/ui` (sustituir `<svg>` por `<Svg>` de `react-native-svg`) y `modes.ts` a `packages/shared-types`. Por ahora viven en web para no inflar el scope del plan actual.

| Componente | Variants | Notas |
|---|---|---|
| `Button` | `primary`, `secondary`, `ghost` | `primary` usa `--gradient-blue-base`. Mismo padding y tipografía en todas las variants. |
| `Card` | `default`, `interactive` | `interactive` tiene `shadow-soft` y cursor pointer. |
| `OptionCard` | idle, selected | Selected: fondo ink + hairline gradient en borde. |
| `TextField` | default, error | Error inline con copy humano. |
| `Textarea` | default, error | Mismas reglas que TextField. |
| `Toggle` | off, on | Switch propio con tokens. |
| `ChipGroup` | — | Para opciones segmentadas (ej. tamaño de texto). |
| `ProgressDots` | — | N dots; current=gradient blue base, otros=ink-faint. |
| `Toast` | info, success, error | Auto-dismiss configurable. |
| `YnaraMark` | size prop | Logo SVG con 3 gradientes. |
| `ModeChip` | por modo | Pastilla con tint del modo. |
| `SuggestionCard` | por modo | Card de recomendación con tint del modo. |
| `EmptyStateCard` | — | Estados vacíos. |

Cada componente vive en su propio archivo, exporta named export, sin barrel monstruo.

---

## 9. Reglas visuales transversales

- Contraste mínimo **WCAG AA**, target **AAA** en textos críticos (hero, CTA copy).
- Respetar `prefers-reduced-motion`. Permitir override manual desde a11y store.
- Tap targets ≥ 44×44px.
- Focus rings visibles con gradiente sutil (no `outline: none`).
- Mobile-first siempre. Breakpoints: `sm:640`, `md:768`, `lg:1024`, `xl:1280`.
- Container max-width en formularios y onboarding: `480px` (mobile-first centered).

---

## 10. Anti-patterns

- ❌ Hardcodear hex en componentes — siempre via CSS var.
- ❌ Mezclar Space Grotesk en body — es display.
- ❌ Animar `width`/`height`/`top`/`left` — sólo `transform` y `opacity`.
- ❌ Usar `outline: none` sin reemplazar el focus visual.
- ❌ Sombras múltiples superpuestas — usar la escala definida.
- ❌ Botones disabled sin tooltip o copy explicando por qué.
- ❌ Toast genéricos para errores de form — usar inline.
- ❌ Loops decorativos infinitos.
- ❌ Imágenes sin `alt`, `width`, `height`, `loading="lazy"`.

---

## 11. Referencias

- [`apps/web/src/app/globals.css`](./apps/web/src/app/globals.css) — tokens reales en CSS vars y `@theme`.
- [`apps/web/src/styles/motion.css`](./apps/web/src/styles/motion.css) — keyframes reutilizables.
- [`apps/web/src/components/ui/`](./apps/web/src/components/ui/) — primitives.
- [`IDENTITY.md`](./IDENTITY.md) — ADN de marca (los 4 pilares).
- [`docs/product/TONE-OF-VOICE.md`](./docs/product/TONE-OF-VOICE.md) — voz operativa modo-por-modo.
- [`docs/planning/archive/FRONTEND-ONBOARDING-PLAN.md`](./docs/planning/archive/FRONTEND-ONBOARDING-PLAN.md) — plan de implementación del primer slice (ejecutado y archivado).
- Prototipo de referencia: [querques20/ynara](https://github.com/querques20/ynara).
