# Frontend MVP · Onboarding + Home vacío — Plan completo

> **Estado**: ✅ EJECUTADO — todas las sesiones cerradas. S1–S3 mergeadas
> previamente; S4 (mood/modos/a11y/outro) + S5 (home vacía) + S6 (tests)
> mergeadas en [PR #48](https://github.com/BriarDevv/Ynara/pull/48) el
> 2026-05-30. Documento archivado.
> **Fecha**: 2026-05-18 (plan) · 2026-05-30 (ejecución)
> **Owner**: @MateoGs013
> **Reviewers sugeridos**: @BriarDevv (foundations / infra), @querques20 (UX / UI)
> **Alcance**: `apps/web` (incluye primitives web-only en `apps/web/src/components/ui/`). Mobile (Expo) y `packages/ui` (reservado para RN-compatibles) quedan fuera.

---

## 0. Contexto

Este documento es el plan de trabajo para dejar terminado el **primer slice navegable** del frontend web de Ynara: el flujo de onboarding completo y la pantalla de inicio (`/home`) en estado vacío con recomendaciones. Backend real fuera de scope — todo mockeado con MSW.

El plan se apoya en tres fuentes:

1. [`IDENTITY.md`](../../IDENTITY.md) — los 4 pilares de marca (Productividad, Memoria, Compañía, Adaptación) y lo que Ynara **es / no es**.
2. [`DESIGN.md`](../../DESIGN.md) — actualmente con TODOs. Este plan lo completa en la Sesión 1.
3. [`querques20/ynara`](https://github.com/querques20/ynara) — prototipo Expo de un miembro del equipo, usado como **base visual + UX a portar y mejorar**.

### Por qué este plan existe ahora

- El front actualmente es un scaffold (`globals.css` con tokens placeholder, `layout.tsx` sin providers, `page.tsx` de "pendiente UI").
- Hay un prototipo del equipo con identidad visual sólida que vale la pena heredar (no descartar).
- Necesitamos un slice end-to-end navegable para empezar a iterar con feedback real, antes de que el backend esté listo.

---

## Tabla de contenidos

1. [Análisis del prototipo de referencia](#1-análisis-del-prototipo-de-referencia-querques20ynara)
2. [Identidad visual base](#2-identidad-visual-base)
3. [Sistema de componentes](#3-sistema-de-componentes)
4. [Onboarding — spec funcional](#4-onboarding--spec-funcional)
5. [Home vacío — spec funcional](#5-home-vacío--spec-funcional)
6. [Arquitectura técnica](#6-arquitectura-técnica)
7. [Plan de ejecución](#7-plan-de-ejecución)
8. [Definition of Done](#8-definition-of-done)
9. [Referencias cruzadas](#9-referencias-cruzadas)

---

## 1. Análisis del prototipo de referencia (querques20/ynara)

### 1.1 Aciertos que conservamos

| # | Acierto | Razón |
|---|---|---|
| 1 | Dual font Space Grotesk (display) + DM Sans (body) | Personalidad técnica sin sacrificar legibilidad |
| 2 | Paleta ink-sobre-blanco con azul y violeta como gradientes acento | Sobria, "no infantil", coherente con IDENTITY |
| 3 | `YnaraMark` con 3 gradientes (azul base + relief + diamond violeta) | Logo distintivo y memorable |
| 4 | `ProgressDots` arriba en cada step | Feedback constante de avance |
| 5 | `OptionCard` con estado seleccionado invertido (ink de fondo) | Feedback inequívoco al tap/click |
| 6 | Animaciones escalonadas (`FadeInDown.delay`) | Sensación orgánica, no robótica |
| 7 | Pantalla "Listen" final tipo *"esto entendí de vos"* | Cierre de marca brillante — momento memorable |
| 8 | Greeting que cambia según tono (`Mateo.` vs `Buen día Mateo`) | Demuestra adaptación del sistema desde el día 1 |
| 9 | Microcopy específico de marca (*"Lo uso solo cuando hablo con vos"*) | Voz Ynara ya escrita |
| 10 | Haptic feedback en cada Pressable | Calidad táctil — traducible a microinteracción visual en web |

### 1.2 Debilidades y mejoras propuestas

#### A. Sistema visual

| # | Problema | Mejora |
|---|---|---|
| A1 | El gradiente azul existe solo en el logo. Button primary es `ink` plano, perdiendo el rasgo más identitario. | Button primary usa `--gradient-blue-base`. El ink pasa a `secondary`. |
| A2 | Los 5 modos no tienen diferenciación visual. | Cada modo tiene un *tint* propio (productividad / estudio / bienestar / vida / memoria). Acento sutil, no decoración. |
| A3 | El gradiente violeta diamond se desperdicia. | Asignarlo como "símbolo de memoria" — aparece en chip del modo Memoria, confirmaciones de recall, outro del onboarding. |
| A4 | Sólo light mode. | Dark mode discreto desde día 1 (no negro puro, sí `#0E1219`). IDENTITY pide sobriedad — dark refuerza calma. |
| A5 | No hay sistema de elevation. | 3 niveles: `none`, `soft` (cards interactivas), `lifted` (modales, toasts). |
| A6 | `OptionCard` seleccionado pierde calidez (todo ink). | Mantener fondo ink + hairline gradient en el borde (1px blue-relief) para "respirar". |

#### B. UX del onboarding

| # | Problema en el proto | Mejora |
|---|---|---|
| B1 | No hay Auth. | Step 1: Auth real (mock por ahora) con email + password + opción "Sin registrarme aún". |
| B2 | Step "tono" no está en el alcance pedido. | Reemplazar por step "Modos que te interesan" (multi-select). Tono se infiere del uso o vive en Ajustes. |
| B3 | Step "permisos" pide acceso a datos (calendario, mails, salud, ubicación, contactos). | Reemplazar por permisos de **accesibilidad visual** sin APIs externas. Permisos a datos quedan para post-onboarding just-in-time cuando un modo los necesite. |
| B4 | Step "día" tiene 5 opciones cerradas, sin escape. | Multi-select hasta 2 + **textarea libre opcional**. |
| B5 | "Saltar" / "Atrás" conviven mal por step (mismo destino, confunde). | Eliminar "Saltar" por step. Único "Saltar onboarding" en header con confirmación. |
| B6 | Botón "Seguir" disabled silencioso. | Botón habilitado siempre, valida en submit, error inline. |
| B7 | Sólo `FadeInDown` en todas las animaciones. | Lenguaje de motion ampliado: entrada de pantalla, entrada de elementos staggered, selección (scale spring), confirmación (gradient sweep). |
| B8 | `router.replace` final → cambio brusco. | Outro de 1.5s: YnaraMark pulsa una vez con diamond violeta + copy "Listo, te estoy esperando" + fade lento al home. |
| B9 | No hay states de error. | Error inline con copy humano ("Esa contraseña es muy corta, dame al menos 8"). Nunca toast genérico. |
| B10 | "Listen" final muestra cards no editables. | Cada card editable con link al step correspondiente. |

#### C. Web-specific (que el proto no contempla porque es Expo)

| # | Mejora |
|---|---|
| C1 | Container central con max-width 480px en desktop, no expandir a 1440px. |
| C2 | Fondo desktop con `--color-bg-soft`, card central blanca: no mar de blanco. |
| C3 | Navegación por teclado: Tab order claro, Enter submits, Esc abre "saltar onboarding". |
| C4 | Focus rings custom con gradiente sutil. |
| C5 | `prefers-reduced-motion` respetado siempre, con override desde Step 5 (a11y). |

#### D. Microcopy heredado + ampliado

Mantener la voz del proto. Extender al resto:

| Step | Título | Subtítulo |
|---|---|---|
| Auth | "Antes que nada" | "Me hace falta una cuenta para acordarme de vos." |
| Nombre | "¿Cómo te llamo?" | "Lo uso solo cuando hablo con vos." (del proto) |
| Día | "¿Cómo viene tu día, en general?" | "Elegí lo que aplique. Te voy a entender mejor." |
| Modos | "¿Para qué te puedo servir?" | "Empezás por lo que te interese. Después abrís más." |
| A11y | "Ajustemos cómo se lee." | "Lo cambiás cuando quieras." |
| Outro | "Listo, te estoy esperando." | (sin subtítulo, solo YnaraMark + transición) |

---

## 2. Identidad visual base

Toda esta sección se materializa en `apps/web/src/app/globals.css` + `DESIGN.md` raíz durante la Sesión 1.

### 2.1 Paleta + gradientes

| Rol | Token CSS | Valor |
|---|---|---|
| Gradiente primario (CTA, marca) | `--gradient-blue-base` | `linear-gradient(135deg, #2F5AA6, #1F66DB)` |
| Gradiente secundario (glow, highlights) | `--gradient-blue-relief` | `linear-gradient(135deg, #4B7EE6, #7BA1F4)` |
| Gradiente acento (memoria) | `--gradient-violet` | `linear-gradient(135deg, #8C63B8, #7C4FA3)` |
| Texto principal | `--color-ink` | `#242C3F` |
| Texto secundario | `--color-ink-soft` | `rgba(36,44,63,0.65)` |
| Texto terciario | `--color-ink-muted` | `rgba(36,44,63,0.45)` |
| Texto desactivado | `--color-ink-faint` | `rgba(36,44,63,0.18)` |
| Fondo base | `--color-bg` | `#FFFFFF` |
| Fondo suave (cards, secciones) | `--color-bg-soft` | `#F6F6F8` |
| Borde sutil | `--color-border` | `rgba(36,44,63,0.12)` |
| Borde marcado | `--color-border-strong` | `rgba(36,44,63,0.22)` |
| Texto sobre fondos oscuros | `--color-on-dark` | `#FFFFFF` |

### 2.2 Tipografía

| Familia | Para | Pesos | Source |
|---|---|---|---|
| **Space Grotesk** | Display (hero, títulos, subtítulos, marca) | 500, 700 | `next/font/google` |
| **DM Sans** | Body, botones, captions | 400, 500 | `next/font/google` |

**Escala** (rem, base 16px):

| Token | Tamaño / line-height / letter-spacing | Uso |
|---|---|---|
| `text-hero` | 3rem / 3.25rem / -0.05em | Hero de welcome |
| `text-title` | 2.125rem / 2.375rem / -0.03em | Título de step |
| `text-subtitle` | 1.375rem / 1.75rem / -0.018em | Subtítulo de step |
| `text-body` | 1rem / 1.5rem / -0.006em | Cuerpo |
| `text-body-sm` | 0.875rem / 1.25rem / -0.003em | Helper, hints |
| `text-caption` | 0.75rem / 1rem / +0.06em uppercase | Labels, etiquetas |
| `text-button` | 1rem / 1.25rem / -0.006em | Botones |

### 2.3 Spacing

Escala base 4: `xs:4 · sm:8 · md:12 · base:16 · lg:24 · xl:32 · 2xl:48 · 3xl:64`.

### 2.4 Radius

`sm:8 · md:12 · lg:16 · xl:20 · pill:9999`.

### 2.5 Motion

- Easing default: `cubic-bezier(0.22, 1, 0.36, 1)` (out expo suave)
- Duración base: `250ms`
- Transición de step: fade + slide horizontal 24px, `350ms`
- Selección: `scale 1.0 → 1.02` con spring (`damping: 18`)
- Confirmación: gradient sweep `400ms`
- Todo dentro de `@media (prefers-reduced-motion: no-preference)`, override desde store de a11y

### 2.6 Dark mode (discreto)

| Token | Light | Dark |
|---|---|---|
| `--color-bg` | `#FFFFFF` | `#0E1219` |
| `--color-bg-soft` | `#F6F6F8` | `#161B25` |
| `--color-ink` | `#242C3F` | `#E8ECF4` |
| Resto | usar alpha | usar alpha |

Activación: `[data-theme="dark"]` o `prefers-color-scheme: dark` por default, override desde a11y store.

### 2.7 Tints por modo

Cada modo tiene un tint sutil para usar en `ModeChip` y `SuggestionCard`:

| Modo | Tint primario | Para |
|---|---|---|
| Productividad | `--gradient-blue-base` | Azul base — acción, ejecución |
| Estudio | `--gradient-blue-relief` | Azul claro — claridad, expansión |
| Bienestar | `linear-gradient(135deg, #4A9C8C, #6FBFAE)` | Jade — calma |
| Vida | `linear-gradient(135deg, #D9A24A, #E8C77A)` | Ámbar — cotidiano cálido |
| Memoria | `--gradient-violet` | Violeta — el símbolo de memoria del logo |

> Los valores de Bienestar y Vida son propuesta inicial — requieren validación visual con @querques20 en Sesión 1.

---

## 3. Sistema de componentes

### 3.1 Primitives — `packages/ui/src/primitives/`

Atómicas, reutilizables, web y mobile-portables. No conocen features.

| Componente | Origen | Notas |
|---|---|---|
| `Button` | port + mejora del proto | 3 variants: `primary` (gradient), `secondary` (ink solid), `ghost` (transparente) |
| `Card` | nuevo | Default + interactive |
| `OptionCard` | port del proto | Mejora: hairline gradient en borde cuando seleccionado |
| `TextField` | port del proto | + estado error inline con copy humano |
| `Textarea` | nuevo | Mismas reglas que TextField |
| `Toggle` | reemplaza `Switch` del proto | Switch propio con tokens |
| `ChipGroup` | nuevo | Para opciones segmentadas (ej. tamaño de texto) |
| `ProgressDots` | port del proto | Igual con tokens nuevos |
| `Toast` | port del proto | Adaptado a web (sin haptic, con micro-vibración visual) |
| `YnaraMark` | port del proto | SVG con 3 gradientes — convertido a React |
| `ModeChip` | nuevo | Pastilla con tint del modo. Reutilizable en header + recommendations |
| `SuggestionCard` | formaliza patrón del home del proto | Es el patrón clave de Ynara |
| `EmptyStateCard` | nuevo | Para sessions vacías, conversaciones nuevas |

### 3.2 Composiciones — `apps/web/src/components/` y `features/`

Conocen features y reglas web-específicas.

| Componente | Ubicación | Función |
|---|---|---|
| `StepShell` | `features/onboarding/components/` | Container del step con transición GSAP, max-width desktop, container |
| `StepFooter` | `features/onboarding/components/` | Atrás (ghost) + CTA (gradient). Sin "Saltar" por step. |
| `OnboardingHeader` | `features/onboarding/components/` | ProgressDots + "Saltar onboarding" discreto con confirmación |
| `CelebrationOutro` | `features/onboarding/components/` | YnaraMark pulse violeta + copy, 1.5s antes de `/home` |
| `Greeting` | `features/home/components/` | Saludo dinámico + nombre + línea sutil con mood |
| `ModeSwitcher` | `features/home/components/` | Header chip con sólo modos seleccionados |
| `RecommendationsGrid` | `features/home/components/` | 4 SuggestionCards filtradas por interestedModes |
| `EmptySessions` | `features/home/components/` | Usa EmptyStateCard del shared package |
| `ChatInputDocked` | `features/home/components/` | Input fijo abajo, disabled con tooltip "Próximamente" |

---

## 4. Onboarding — spec funcional

### 4.1 Flujo

```
/onboarding/auth   →  /onboarding/nombre  →  /onboarding/dia  →  /onboarding/modos
                                                                      ↓
                /home?welcome=true  ←  outro (1.5s)  ←  /onboarding/a11y
```

5 steps + outro de celebración. `ProgressDots` muestra 5 puntos.

### 4.2 Step 1 · Auth

- **Copy**: título "Antes que nada", subtítulo "Me hace falta una cuenta para acordarme de vos."
- **UI**: tabs "Crear cuenta" / "Iniciar sesión", email + password, CTA gradient. Botón ghost "Probar sin cuenta" abajo (cuenta efímera, perfil no persiste entre sesiones).
- **Validación Zod**: email válido, password ≥ 8.
- **Mock MSW**: `POST /v1/auth/login` y `POST /v1/auth/signup` devuelven `{ token, userId }` siempre OK. Toggle de dev para simular 401.
- **Estado**: guarda `{ userId, isEphemeral }` en store de onboarding.

> **Contrato con backend — landmine documentada**
>
> `apps/backend/app/core/security.py` está en `NotImplementedError` a propósito (ver [`docs/conventions/AI-GUIDELINES.md`](../conventions/AI-GUIDELINES.md): _"si necesitás auth para tu feature, abrí un issue/discusión primero"_). El shape `{ token, userId }` mockeado acá es **provisional** y no tiene contraparte real en backend todavía.
>
> Reglas para no acumular deuda de divergencia Zod ↔ Pydantic:
>
> 1. **Antes de mergear la PR de Sesión 3**, abrir issue con @BriarDevv para acordar el contrato (shape de request/response, claims del JWT, scopes). Si ya existe PR en curso de `core/security.py`, referenciarlo.
> 2. **Schemas Zod en `packages/shared-schemas/`** desde el día 1 (no inline en `apps/web`). Cuando el backend defina Pydantic, los modelos se mirroran manualmente contra los Zod existentes — eso vuelve la divergencia detectable en code review.
> 3. **MSW handlers comentados** con un `TODO(@BriarDevv)` y link al issue, así no quedan handlers huérfanos cuando el backend reemplace los mocks.

### 4.3 Step 2 · Nombre

- **Copy**: "¿Cómo te llamo?" / "Lo uso solo cuando hablo con vos."
- **UI**: `TextField` grande con autofocus, CTA gradient.
- **Validación Zod**: `name` 2–40 caracteres, sin caracteres raros.
- **Estado**: `displayName`.

### 4.4 Step 3 · Día (mood)

- **Copy**: "¿Cómo viene tu día, en general?" / "Elegí lo que aplique. Te voy a entender mejor."
- **UI**: 6 `OptionCard` multi-select limitado a 2 + `Textarea` libre opcional debajo.
- **Opciones predefinidas**:
  1. Tranquilo, con tiempo
  2. Ocupado, varias cosas
  3. Estresado
  4. Confuso, no sé por dónde arrancar
  5. Creativo, con ideas
  6. Cansado
- **Validación Zod**: `mood: string[]` length 0-2, `moodFreeText` 0-160 chars.
- **Por qué importa**: alimenta la primera memoria episódica.
- **Estado**: `mood`, `moodFreeText`.

### 4.5 Step 4 · Modos

- **Copy**: "¿Para qué te puedo servir?" / "Empezás por lo que te interese. Después abrís más."
- **UI**: 5 `OptionCard` con icono + título + subtítulo + `ModeChip` interno (con tint del modo). Multi-select mínimo 1.
- **Modos**: lectura desde [`ynara.config.json`](../../ynara.config.json) (no hardcodear).
- **Default sugerido**: Productividad pre-marcado.
- **Validación Zod**: `interestedModes: ModeId[]` length ≥ 1.
- **Estado**: `interestedModes`.

### 4.6 Step 5 · A11y visual

- **Copy**: "Ajustemos cómo se lee." / "Lo cambiás cuando quieras."
- **UI**: 3 controles puramente visuales, **sin APIs externas**:
  1. **Tamaño de texto**: `ChipGroup` 3 chips (Chico · Normal · Grande)
  2. **Contraste alto**: `Toggle`
  3. **Reducir animaciones**: `Toggle` (default lee `prefers-reduced-motion`)
- **Efecto inmediato**: cada cambio se aplica en vivo a la pantalla actual.
- **Implementación**: el store `stores/a11y.ts` aplica clases al `<html>` (`text-size-lg`, `theme-high-contrast`, `motion-reduced`).
- **Estado**: `a11y: { textSize, highContrast, reducedMotion }`.

### 4.7 Outro · CelebrationOutro

- Después del Step 5, mutation `POST /v1/user/onboard` mockeada.
- 1.5s de animación: `YnaraMark` pulsa una vez con el gradiente violeta diamond + copy "Listo, te estoy esperando".
- Fade lento al `/home?welcome=true`.

### 4.8 Reglas transversales

- Refresh a mitad: `sessionStorage` retoma el step.
- Guard: si el user ya completó onboarding, `/onboarding/*` redirige a `/home`.
- "Saltar onboarding" sólo en el header global, con modal de confirmación.
- Botones nunca disabled silenciosos. Validación en submit + error inline humano.
- Navegación por teclado: `Enter` submits, `Esc` abre "Saltar onboarding".

---

## 5. Home vacío — spec funcional

### 5.1 Layout

```
┌─────────────────────────────────────────────┐
│ Buenas tardes, Mateo                        │ ← saludo según hora + displayName
│ Modo: Productividad ▾                       │ ← ModeSwitcher (solo modos elegidos)
├─────────────────────────────────────────────┤
│                                             │
│ Para arrancar                               │
│ ┌──────────────┐ ┌──────────────┐           │
│ │ Agendame…    │ │ Explicame…   │           │ ← 4 SuggestionCard
│ └──────────────┘ └──────────────┘             filtradas por interestedModes
│ ┌──────────────┐ ┌──────────────┐           │
│ │ ¿Cómo estás? │ │ Recordá…     │           │
│ └──────────────┘ └──────────────┘           │
│                                             │
│ Tus conversaciones                          │
│ ╭─────────────────────────────────────╮     │
│ │  Vacío. Empezá una abajo ↓          │     │ ← EmptyStateCard
│ ╰─────────────────────────────────────╯     │
│                                             │
├─────────────────────────────────────────────┤
│ [ Escribí algo… ]                      [→]  │ ← ChatInputDocked (disabled, tooltip)
└─────────────────────────────────────────────┘
```

### 5.2 Saludo dinámico

- 6:00–11:59 → "Buen día"
- 12:00–19:59 → "Buenas tardes"
- 20:00–5:59 → "Buenas noches"
- Acompañado del `displayName` del store.
- Si `mood` o `moodFreeText` no vacío, segunda línea sutil opcional: *"Anoté que tu día viene tranquilo"*.

### 5.3 Recomendaciones (4 cards)

Catálogo en `apps/web/src/features/home/data/recommendations.ts`. Cada recomendación tiene `{ id, title, subtitle, modeId, prefillPrompt }`. Se muestran 4, filtradas/priorizadas por `interestedModes`:

- Si seleccionó 1 modo → 4 cards de ese modo.
- Si seleccionó 2+ modos → 1 card por modo, hasta 4.

| # | Título | Subtítulo | Modo |
|---|---|---|---|
| 1 | "Agendame algo" | "Probá pedirle al modo productividad" | productividad |
| 2 | "Explicame un tema" | "El modo estudio te tutorea" | estudio |
| 3 | "¿Cómo estás?" | "Charla casual, sin presión" | bienestar |
| 4 | "Contame qué pasó hoy" | "Te acompaño un rato" | bienestar |
| 5 | "Recordá esto sobre mí" | "Memoria semántica explícita" | memoria |
| 6 | "¿Qué dije la semana pasada?" | "Recall episódico" | memoria |
| 7 | "Recomendame algo para ver" | "Charla y sugerencias" | vida |
| 8 | "Bloqueame 2 horas de foco" | "Productividad bloque profundo" | productividad |

**Acción al click**: cambia el `ModeSwitcher` al modo de la card + prefillea el `ChatInputDocked` con `prefillPrompt`.

### 5.4 Mode switcher

- Header dropdown con sólo los modos que el user seleccionó en Step 4.
- Modos no seleccionados aparecen grisados al final del dropdown con CTA "Activar en Ajustes".
- Cada item del dropdown muestra su `ModeChip` con el tint correspondiente.

### 5.5 Empty state de sessions

- `EmptyStateCard` con copy "Vacío. Empezá una abajo ↓".
- Si futuro: pasar a `SessionsList` cuando haya sesiones reales.

### 5.6 Input docked

- Input fijo al pie de la página.
- Deshabilitado por ahora con tooltip "Próximamente" al hacer focus.
- Visualmente vivo (no atenuado al punto de invisibilidad) — sirve de promesa visual del chat.

### 5.7 Toast de bienvenida

- Si URL trae `?welcome=true`: muestra Toast "Listo, ya podés arrancar" 3s.
- Limpia el query param (replace state, sin recargar).
- Una vez sola por carga.

---

## 6. Arquitectura técnica

### 6.1 Estructura de carpetas (archivos nuevos)

```
apps/web/
├── DESIGN.md                                  ← (raíz, ya existe, completar contenido)
└── src/
    ├── app/
    │   ├── globals.css                        ← REEMPLAZO TOTAL
    │   ├── fonts.ts                           ← NUEVO
    │   ├── layout.tsx                         ← MODIFICAR (providers + fonts)
    │   ├── providers.tsx                      ← NUEVO
    │   ├── page.tsx                           ← MODIFICAR (guard de redirect)
    │   ├── test-ds/page.tsx                   ← NUEVO (sandbox del design system)
    │   ├── onboarding/
    │   │   ├── layout.tsx                     ← NUEVO
    │   │   ├── page.tsx                       ← NUEVO (redirect a /onboarding/auth)
    │   │   └── [step]/page.tsx                ← NUEVO (dispatcher)
    │   └── home/page.tsx                      ← NUEVO
    ├── features/
    │   ├── onboarding/
    │   │   ├── steps/
    │   │   │   ├── AuthStep.tsx
    │   │   │   ├── NameStep.tsx
    │   │   │   ├── MoodStep.tsx
    │   │   │   ├── ModesStep.tsx
    │   │   │   └── A11yStep.tsx
    │   │   ├── components/
    │   │   │   ├── StepShell.tsx
    │   │   │   ├── StepFooter.tsx
    │   │   │   ├── OnboardingHeader.tsx
    │   │   │   └── CelebrationOutro.tsx
    │   │   ├── store.ts
    │   │   ├── schemas.ts
    │   │   ├── constants.ts
    │   │   ├── hooks/
    │   │   │   ├── useOnboardingNav.ts
    │   │   │   └── useCompleteOnboarding.ts
    │   │   └── tests/
    │   └── home/
    │       ├── components/
    │       │   ├── Greeting.tsx
    │       │   ├── ModeSwitcher.tsx
    │       │   ├── RecommendationsGrid.tsx
    │       │   ├── EmptySessions.tsx
    │       │   └── ChatInputDocked.tsx
    │       ├── data/recommendations.ts
    │       └── tests/
    ├── lib/
    │   ├── api.ts
    │   ├── api.mocks.ts                       ← MSW handlers
    │   ├── auth.ts
    │   ├── cn.ts                              ← clsx + tailwind-merge
    │   ├── env.ts                             ← Zod sobre process.env
    │   ├── time.ts                            ← saludo según hora
    │   └── modes.ts                           ← lee ynara.config.json
    ├── stores/
    │   ├── user.ts
    │   └── a11y.ts                            ← aplica clases a <html>
    └── styles/
        └── motion.css                         ← keyframes reutilizables

packages/ui/src/
├── primitives/
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── OptionCard.tsx
│   ├── TextField.tsx
│   ├── Textarea.tsx
│   ├── Toggle.tsx
│   ├── ChipGroup.tsx
│   ├── ProgressDots.tsx
│   ├── Toast.tsx
│   ├── YnaraMark.tsx
│   ├── ModeChip.tsx
│   ├── SuggestionCard.tsx
│   └── EmptyStateCard.tsx
├── tokens/
│   └── modes.ts                               ← mapping modo → tint
└── index.ts                                   ← barrel

tests/e2e/
├── playwright.config.ts                       ← NUEVO si no existe
└── onboarding.spec.ts                         ← NUEVO
```

### 6.2 Archivos modificados

```
apps/web/src/app/globals.css   ← reemplazo total
apps/web/src/app/layout.tsx    ← monta providers, fonts, html classes de a11y
apps/web/src/app/page.tsx      ← guard que redirige a /onboarding o /home
apps/web/package.json          ← +deps (sección 6.3)
apps/web/AGENTS.md             ← +línea sobre primitives en packages/ui
DESIGN.md (raíz)               ← completar contenido (sección 2 acá)
packages/ui/package.json       ← exportar nuevos primitives
packages/ui/src/index.ts       ← barrel update
```

### 6.3 Deps a agregar (requieren OK humano — regla #1 AGENTS.md)

Las deps se instalan en **dos batches**, cada uno en su sesión correspondiente, para que cada `pnpm add` tenga aprobación explícita y para no inflar `package.json` con deps muertas hasta que se usen (feedback del review de @BriarDevv en PR del plan).

**Batch 1 — Sesión 2** (core de la app):

```
# apps/web
clsx
tailwind-merge
msw

# apps/web devDependencies
vitest
@vitejs/plugin-react
@testing-library/react
@testing-library/jest-dom
@testing-library/user-event
jsdom
```

**Batch 2 — Sesión 6** (solo cuando arranca testing E2E):

```
# apps/web devDependencies
@axe-core/playwright

# root (tests/e2e)
@playwright/test
msw  # reusar handlers entre dev/unit/e2e
```

### 6.4 Decisión: dónde viven primitives

- `packages/ui/src/primitives/` → primitives atómicas, web/mobile-portables (no conocen features).
- `apps/web/src/components/` → composiciones web-específicas.
- `apps/web/src/features/<feature>/` → todo lo de un feature (steps, hooks, store, schemas, tests).

Por qué: el `apps/web/src/app/globals.css` actual ya escanea `packages/ui/src/**` con `@source`. Es señal explícita del repo.

---

## 7. Plan de ejecución

6 sesiones, 1 PR por sesión.

### 7.1 Sesión 1 — Design system + DESIGN.md (3-4h)

**Branch**: `feat/design-system-base`
**PR**: `chore(design): sistema visual base + DESIGN.md`

1. Reemplazar `DESIGN.md` raíz con contenido completo (sección 2 de este doc).
2. `apps/web/src/app/fonts.ts` con `next/font/google` (Space Grotesk 500/700 + DM Sans 400/500).
3. Reemplazar `apps/web/src/app/globals.css` con tokens reales + `@theme` + utilities de gradiente.
4. `apps/web/src/styles/motion.css` con keyframes (fade-up, slide-in, gradient-sweep, pulse-soft).
5. `apps/web/src/lib/cn.ts`.
6. `packages/ui/src/tokens/modes.ts`.
7. Primitivas mínimas en `packages/ui/src/primitives/`: `Button`, `Card`, `YnaraMark`.
8. `apps/web/src/app/test-ds/page.tsx` — sandbox para verificar a ojo.
9. `pnpm typecheck && pnpm lint` verdes.
10. Modificar `apps/web/AGENTS.md`: línea sobre primitives.

**Done**: `/test-ds` se ve coherente con la identidad del proto pero con CTA gradient azul vivo.

### 7.2 Sesión 2 — Fundaciones funcionales (3h)

**Branch**: `feat/web-foundations`
**PR**: `feat(web): providers, MSW, primitives restantes`

1. Instalar deps **batch 1** (con OK): `clsx`, `tailwind-merge`, `msw`, `vitest` + RTL stack (`@vitejs/plugin-react`, `@testing-library/{react,jest-dom,user-event}`, `jsdom`). Sin `playwright` ni `axe` todavía — van en Sesión 6.
2. `apps/web/src/lib/env.ts` con Zod.
3. `apps/web/src/lib/api.ts` (fetcher tipado).
4. `apps/web/src/lib/api.mocks.ts` con MSW handlers (`/auth/login`, `/auth/signup`, `/user/onboard`, `/health`).
5. `apps/web/src/app/providers.tsx` (QueryClient + MSW init en dev).
6. `apps/web/src/stores/a11y.ts` (Zustand persist + apply a `<html>`).
7. `apps/web/src/stores/user.ts` (Zustand persist).
8. `apps/web/src/app/layout.tsx` con providers + fonts + html classes.
9. Resto de primitives en `packages/ui/src/primitives/`.
10. Extender `/test-ds`.
11. Smoke test `/test-mock`.

**Done**: providers + MSW + primitives completos. `/test-mock` devuelve `{ ok: true }`.

### 7.3 Sesión 3 — Onboarding parte 1 (Auth + Nombre) (2-3h)

**Branch**: `feat/onboarding-1`
**PR**: `feat(onboarding): auth y nombre`

**Antes de arrancar**: abrir issue con @BriarDevv para acordar el contrato de auth con el backend (ver §4.2 — landmine de `core/security.py`). El PR se mergea con link al issue, no antes.

1. Schemas Zod de auth (signup + login + sesión) en **`packages/shared-schemas/`** — no inline en `apps/web`. Esto permite mirrorearlos contra Pydantic cuando el backend implemente `core/security.py`.
2. `features/onboarding/schemas.ts` (importa desde `@ynara/shared-schemas`).
3. `features/onboarding/constants.ts`.
4. `features/onboarding/store.ts` (sessionStorage).
5. `components/OnboardingHeader.tsx`.
6. `components/StepShell.tsx` (GSAP fade+slide).
7. `components/StepFooter.tsx`.
8. `app/onboarding/layout.tsx` + `[step]/page.tsx`.
9. `AuthStep.tsx` completo (tabs + RHF + mock + errores inline). MSW handlers con `TODO(@BriarDevv)` linkeando al issue de contrato.
10. `NameStep.tsx` completo.

**Done**: `/onboarding` arranca, auth + nombre funcionan, refresh retoma. Issue de contrato de auth abierto y referenciado en el PR.

### 7.4 Sesión 4 — Onboarding parte 2 (Mood + Modos + A11y + Outro) (3-4h)

**Branch**: `feat/onboarding-2`
**PR**: `feat(onboarding): mood, modos, a11y, outro`

1. `MoodStep.tsx`.
2. `lib/modes.ts`.
3. `ModesStep.tsx` (cada card con su ModeChip).
4. `A11yStep.tsx`.
5. `components/CelebrationOutro.tsx`.
6. `hooks/useCompleteOnboarding.ts`.

**Done**: flujo de 5 steps + outro completo. Redirige a `/home` placeholder.

### 7.5 Sesión 5 — Home vacío (3h)

**Branch**: `feat/home-empty`
**PR**: `feat(home): empty state con recomendaciones`

1. `lib/time.ts`.
2. `data/recommendations.ts`.
3. `Greeting.tsx`, `ModeSwitcher.tsx`.
4. `RecommendationsGrid.tsx` con SuggestionCard.
5. `EmptySessions.tsx`.
6. `ChatInputDocked.tsx`.
7. `app/home/page.tsx`.
8. `app/page.tsx` con guard de redirect.

**Done**: home post-onboarding completa, recomendaciones filtradas por `interestedModes`.

### 7.6 Sesión 6 — Testing + a11y + pulido (2-3h)

**Branch**: `feat/web-tests`
**PR**: `test(web): vitest + playwright + axe`

1. Instalar deps **batch 2** (con OK): `@playwright/test`, `@axe-core/playwright`, `msw` en root para `tests/e2e/`.
2. `vitest.config.ts` + setup en `apps/web`.
3. Tests de componente: `store`, `MoodStep` (limit), `ModesStep` (min 1), `A11yStep` (clases `<html>`).
4. `tests/e2e/playwright.config.ts` si no existe.
5. `tests/e2e/onboarding.spec.ts` (happy path + auth error + axe).
6. Responsive 375 / 768 / 1280 (screenshots para PR).
7. `prefers-reduced-motion` (devtools).
8. `pnpm typecheck && lint && test` verde.
9. `bash scripts/ynara-doctor.sh` → `exit 0`.

**Done**: PR final con red de seguridad.

### 7.7 Estrategia de PRs

| # | PR | Branch | Tamaño | Reviewer crítico |
|---|---|---|---|---|
| 1 | `chore(design): sistema visual base + DESIGN.md` | `feat/design-system-base` | M | @MateoGs013 (CODEOWNER de DESIGN.md) |
| 2 | `feat(web): providers, MSW, primitives` | `feat/web-foundations` | M | @BriarDevv |
| 3 | `feat(onboarding): auth y nombre` | `feat/onboarding-1` | M | @querques20 (UX) |
| 4 | `feat(onboarding): mood + modos + a11y + outro` | `feat/onboarding-2` | L | @querques20 |
| 5 | `feat(home): empty state + recomendaciones` | `feat/home-empty` | M | @querques20 |
| 6 | `test(web): vitest + playwright + axe` | `feat/web-tests` | M | @BriarDevv |

**Por qué partido**: 6 PRs pequeñas tienen turnaround real. 1 PR enorme nadie lo revisa.

#### Checkpoint de entregable parcial

Si el cronograma se aprieta (problemas de scope, otras prioridades del equipo), **el corte natural cae tras Sesión 4**: el onboarding queda navegable de punta a punta con mocks, pero la home no existe todavía y la red de tests no está armada. Eso ya es suficiente para una primera demo interna y para mostrar el flow de UX al equipo.

Recomendación: revisar progreso al cerrar Sesión 4 y decidir si seguir directo a Sesión 5 + 6 o pausar para integrar feedback de UX antes de avanzar.

---

## 8. Definition of Done

### Repo / proceso

- [ ] 6 PRs mergeados a `main`.
- [ ] `DESIGN.md` raíz completo (paleta, type, spacing, radius, motion, primitives).
- [ ] `apps/web/globals.css` sin TODOs.
- [ ] `bash scripts/ynara-doctor.sh` → `exit 0`.
- [ ] Sin `any`, sin `@ts-ignore` sin justificación.
- [ ] Sin `useEffect + fetch`. Sin `@supabase/supabase-js`. Sin imports a `openai/anthropic/google-genai`.

### Identidad visual

- [ ] Space Grotesk + DM Sans cargadas vía `next/font`.
- [ ] Gradiente azul vivo en CTA primary.
- [ ] 5 modos con tint propio.
- [ ] Dark mode discreto funcionando.
- [ ] `/test-ds` renderiza sistema entero sin gaps.

### Onboarding

- [ ] 5 steps: Auth → Nombre → Día → Modos → A11y → Outro celebración.
- [ ] Refresh a mitad retoma step (sessionStorage).
- [ ] Guard: completado → `/home`.
- [ ] Sin "Saltar" por step. Sólo "Saltar onboarding" en header con confirmación.
- [ ] Errores inline con copy humano.
- [ ] Validación en submit, no botón disabled silencioso.
- [ ] Outro con YnaraMark pulse violeta antes de entrar al home.

### Home vacío

- [ ] Saludo dinámico + displayName.
- [ ] Línea sutil con mood si lo declaró.
- [ ] Mode switcher con sólo modos elegidos.
- [ ] 4 SuggestionCards filtradas por modos.
- [ ] Toast bienvenida una vez, query limpio.
- [ ] Input deshabilitado con tooltip.

### A11y

- [ ] axe-core sin errores críticos en `/onboarding/*` y `/home`.
- [ ] Tab order coherente.
- [ ] Focus rings visibles con gradiente sutil.
- [ ] `prefers-reduced-motion` respetado + override manual desde Step 5.
- [ ] Contraste mínimo WCAG AA, AAA en textos críticos.

### Responsive

- [ ] 375 / 768 / 1280 verificado con screenshots adjuntos al PR.

---

## 9. Referencias cruzadas

- [`AGENTS.md`](../../AGENTS.md) — contrato del repo. Reglas #1 (OK humano), #5 (sin Supabase en frontend).
- [`IDENTITY.md`](../../IDENTITY.md) — 4 pilares de marca, lo que Ynara es / no es.
- [`DESIGN.md`](../../DESIGN.md) — sistema visual (a completar en Sesión 1).
- [`apps/web/AGENTS.md`](../../apps/web/AGENTS.md) — reglas duras del frontend web.
- [`apps/web/README.md`](../../apps/web/README.md) — stack y scripts.
- [`docs/product/MODES.md`](../product/MODES.md) — definición de los 5 modos.
- [`ynara.config.json`](../../ynara.config.json) — config canónica de modos.
- [`querques20/ynara`](https://github.com/querques20/ynara) — prototipo Expo de referencia.

---

> **Cómo usar este documento**:
> Cada sesión arranca con un PR scope claro y termina con un Done explícito. Si una sesión cambia de scope o cambian decisiones de diseño, editar este doc en el mismo PR y referenciarlo. Cuando todas las sesiones cierren, marcar este doc como "ejecutado" en el header y mover a `docs/planning/archive/`.
