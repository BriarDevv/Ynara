# Plan de rediseño del frontend — Sistema visual v2

> **Objetivo.** Llevar el frontend (web ahora, mobile habilitado vía fundaciones
> compartidas) al sistema de diseño v2
> ([`DESIGN.md`](../../DESIGN.md)), sacándolo del look "maqueta de trainee / generado
> por IA" y dándole la identidad editorial/serena de marca (universo Ynara 2026).
>
> **Fuentes.** [`DESIGN.md`](../../DESIGN.md) (sistema v2, fuente de verdad) ·
> [`design-research-2026.md`](./design-research-2026.md) (research + universo de marca).
>
> **Base ya hecha.** PR #97 migró los **tokens** de `globals.css` (marfil, nocturna,
> rampa de memoria, motion, `.text-display`, grano, DM Sans 600). Este plan construye
> **encima** de esos tokens.

## Decisiones de alcance (validadas con el usuario)

| Decisión | Elegido |
|---|---|
| **Alcance** | **Web + mobile.** Las fundaciones (íconos, sistema gráfico, tokens) se crean RN-portables en `packages/ui` y sirven a ambas plataformas. **Realidad importante:** `apps/mobile` hoy es un **esqueleto** (solo `app/index.tsx` + `_layout.tsx`; el resto son `.gitkeep`) — no hay pantallas mobile para rediseñar todavía, así que mobile = construir sobre las fundaciones a medida que sus pantallas existan (ver Capa 4). |
| **Estructura** | **Por capas**: sistema gráfico → primitives → pantallas. Minimiza retrabajo. |
| **Logo (`YnaraMark`)** | **Sí, alinearlo a la marca** (diamante + rampa de memoria real). Es cambio de identidad → el PR igual lleva review de @BriarDevv/@querques20 como CODEOWNERS, pero **entra en el rediseño** (no se difiere). |
| **Verificación visual** | **No por ahora**: se confía en los gates automáticos (biome · tsc · build · vitest · doctor). La verificación visual en navegador queda para una pasada de QA al final, si el usuario la pide. |

## Principios de ejecución (heredados del flujo actual)

- Una **rama por fase/PR**, partiendo siempre de `origin/main`.
- **Commits atómicos** en español (Conventional Commits), trailer de co-autoría.
- **Review con agente independiente** (`code-reviewer`) antes de cada merge — nunca
  auto-aprobación en el mismo contexto.
- **Cadena de calidad** verde antes de mergear: biome · `tsc` · `next build` ·
  `vitest` · `ynara-doctor`. **Leer los resultados antes de afirmar que pasaron.**
- Merge por **rebase** vía PR en GitHub. Nunca push directo a `main`.
- **Sin hardcodear** valores: todo vía tokens de `globals.css` (anti-pattern §13).

---

## Capa 0 — Preparación y fundaciones de marca

Antes de tocar pantallas: crear los recursos nuevos que el sistema v2 necesita y que
hoy no existen.

### F0.1 — Versionar la guía de marca
- Mover `Ynara-Universo-de-Marca.html` al repo (`docs/brand/`) — hoy vive solo en
  Downloads del usuario. Fuente del sistema gráfico, iconografía y aplicaciones.
- **PR chico, sin código.**

### F0.0 — Verificar wiring de `packages/ui`
- Antes de poblarlo: confirmar que el package está listo para recibir componentes y
  ser consumido desde `apps/web` **y** `apps/mobile` (tsconfig, `exports`, imports).
  Hoy `packages/ui/src/index.ts` es solo `export {};`. Pequeño, pero bloquea F0.2/F0.3.

### F0.2 — Set de iconografía propia (`packages/ui`) — [DESIGN.md §9]
- Crear `packages/ui/src/icons/` con el set de marca: **Idea, Conexión, Memoria,
  Nota, Buscar, Diálogo, Recordatorio, Adaptación, Foco, Red** + utilitarios mínimos
  (enviar, detener, atrás, cerrar, chevron).
- Trazo uniforme, el **diamante** como acento donde aplique. Componente `Icon`
  (web: `<svg>`; portable a RN después con `react-native-svg`).
- **Fallback Lucide** controlado para utilitarios no cubiertos, mismo grosor de trazo.
- Esto mata el tell "emojis/flechas como íconos" de raíz.
- **Verificación visual** (grid de íconos) en este PR — es fundación.

### F0.3 — Sistema gráfico "Red de memoria" (`packages/ui`) — [DESIGN.md §2]
- `MemoryField` (SVG): nodos + vínculos + diamantes, con props de **densidad**
  (dispersa/media/densa) y variante clara/nocturna. Para fondos ambientales.
- `GrainOverlay`: capa de grano reutilizable. En web envuelve el utility `.bg-grain`
  (pseudo-elemento) ya creado en globals; **para RN no sirve el pseudo-elemento** →
  necesita estrategia propia (overlay SVG de ruido o imagen). Definir en el PR; si la
  versión RN se complica, scopear web-first con TODO de portabilidad.
- Performance: SVG estático o canvas liviano; **nada de loops infinitos**; respeta
  `prefers-reduced-motion`.

### F0.4 — Helpers de motion — [DESIGN.md §8]
- Evaluar `motion` (Framer Motion) para springs perceptuales + microinteracciones, o
  CSS puro si alcanza. Decisión técnica en el PR (bundle vs. ergonomía). En mobile el
  equivalente es Reanimated — los presets (`spring-snappy`/`spring-soft`) se definen
  como valores compartidos, no como implementación atada a una lib.
- Hooks/utilidades: `useReducedMotion`, presets de spring,
  helper de View Transitions (web) con progressive enhancement.

---

## Capa 1 — Primitives (`components/ui`)

Rediseñar los primitives existentes contra el sistema v2. Cada uno: tokens v2,
microinteracciones (§8.2), foco accesible, estados completos, dark co-protagonista.

### F1.1 — Primitives base
- `Button` (hover `scale(1.02)`, press `scale(0.97)`, gradiente azul en primary).
- `Card` / `OptionCard` (elevación por luz en dark, hover).
- `TextField` / `Textarea` (estados, error inline, foco con anillo de identidad).
- `Toggle`, `ChipGroup`, `ProgressDots`.

### F1.2 — Primitives de marca
- `ModeChip` / `SuggestionCard` (tints por modo con la rampa nueva; memoria usa
  `--gradient-memory`).
- `Toast` (entrada/salida 300/200ms, variantes).
- `EmptyStateCard` (con `MemoryField` de fondo). **Depende de `MemoryField` desde
  `@ynara/ui`** — import direction web → `packages/ui` (correcto; explicitarlo al
  implementar).
- **`PromptChip`** (nuevo) — chip de prompt accionable para empty states de chat.

> Nota de ubicación: estos primitives son **web-only** y viven en
> `apps/web/src/components/ui/` (regla del repo, DESIGN.md §11). Solo las fundaciones
> portables (íconos, `MemoryField`, grano) van en `packages/ui`.

### F1.3 — Tipografía editorial
- Aplicar `.text-display` y la escala fluida donde corresponda; revisar tracking/
  measure en todos los primitives con texto.
- Actualizar **`app/test-ds/`** como showcase de primitives (banco de prueba que ya
  existe) en vez de crear uno nuevo.

---

## Capa 2 — Pantallas

Rediseñar cada pantalla usando primitives + sistema gráfico. Orden por dependencia.

### F2.1 — Onboarding (`features/onboarding`)
Estructura **real** hoy: 5 steps en `[step]/page.tsx` (dispatcher) + `StepShell` +
`StepFooter`/`OnboardingHeader`. Slugs: **`auth` (AuthStep), `nombre` (NameStep),
`dia` (MoodStep), `modos` (ModesStep), `a11y` (A11yStep)**, más `CelebrationOutro`
(transición final, no es un step). No existe un `OnboardingFlow` ni un step "Welcome"
— el primer contacto es `auth` ("Antes que nada").
- Rediseñar `StepShell` / `OnboardingHeader` / `StepFooter` + los 5 steps con tokens
  v2, `ProgressDots`, microinteracciones.
- **`auth` y `CelebrationOutro` como piezas editoriales** (big type `.text-display` +
  `MemoryField` de fondo + copy de marca, estilo posters del slide 09).
- Motion con significado: nodos que se encienden, vínculos que se dibujan, diamante
  de foco. Stagger sutil entre steps con View Transitions.
- Mantener verdes los tests existentes (`A11yStep.test`, `ModesStep.test`,
  `MoodStep.test`, `schemas.test`, `store.test`) — actualizar si el rediseño cambia
  estructura.

### F2.2 — Home (`app/home/page.tsx` + `features/home/components/*`)
- Layout intencional (no centrado-en-todo). Jerarquía por peso/contraste.
- Componentes a rediseñar: `Greeting`, `ModeSwitcher`, `RecommendationsGrid`
  (+ `SuggestionCard` con tints de modo), `EmptySessions`, `ChatInputDocked`.
- ⚠️ `ChatInputDocked` toca el chat (W5 del chat plan) — coordinar para no duplicar
  el composer (ver nota de coordinación abajo).
- Sin emojis (hoy `ChatInputDocked` usa `→` y `EmptySessions` usa `↓`).

### F2.3 — Chat (`features/chat/*`) — [DESIGN.md §10]
La pantalla más crítica. Es donde el rediseño se nota más.
- **Mensajes como documento**: `MessageBubble` → asistente sin burbuja (prosa a
  measure 60-70ch), usuario con contenedor liviano.
- `ChatComposer`: íconos propios; send → **stop** durante streaming; estados.
- `ChatHeader`: ícono de atrás propio (no `←`).
- `MessageList`: **auto-scroll inteligente** (sigue solo si está cerca del fondo +
  botón "ir al final") → **corrige el bug de W2**.
- `EmptyConversation`: welcome editorial + `PromptChip`s.
- `Markdown`: estilos editoriales; preparar buffer de markdown incompleto (la lógica
  fina de streaming llega con W3 del chat plan).

### F2.4 — Superficies de soporte y bancos de prueba
- `/` (landing/redirect, `app/page.tsx`), `_not-found` / estados de error.
- Config de a11y: **no hay ruta `/a11y` dedicada** — vive en el step `a11y` del
  onboarding + el store de a11y + `globals.css`. Cubierta por F2.1; una pantalla de
  settings standalone sería **scope nuevo** a decidir, no existe hoy.
- **`test-ds`** ya se actualiza en F1.3. **`test-mock`** (`app/test-mock/`): smoke del
  mock del chat — mantener funcional tras el rediseño del chat (F2.3).

---

## Capa 3 — Logo (`YnaraMark`) — alineado a marca

### F3.1 — Migrar el logo a la identidad de marca
- Migrar a colores/formas reales de la presentación (diamante, rampa de memoria real
  en vez de `--color-violet-*` legacy).
- Es cambio de identidad → el PR lleva review de @BriarDevv/@querques20 (CODEOWNERS),
  pero **entra en el rediseño** (no se difiere).
- Al cerrarse: eliminar `--color-violet-*` legacy si ya nadie los usa, y unificar en
  la rampa de memoria.

---

## Capa 4 — Mobile (`apps/mobile`)

`apps/mobile` hoy es un **esqueleto** (Expo Router: `app/index.tsx` + `_layout.tsx`;
features/components/lib son `.gitkeep`). No hay pantallas para "rediseñar" — hay que
**construirlas** consumiendo las fundaciones de Capa 0 (íconos, `MemoryField`, tokens
vía NativeWind `vars()`).
- **Esto es un plan en sí mismo** (paridad con onboarding/home/chat web) y excede el
  rediseño web. Se deja **enganchado** acá: cuando las fundaciones (F0) estén en
  `packages/ui` y RN-portables, el track mobile arranca con su propio plan de
  pantallas, reusando primitives portados.
- Riesgo conocido (del chat plan): el fetch de RN no tiene `ReadableStream` → el
  streaming mobile usa `expo/fetch`.

---

## Riesgos y notas

- **Jade/ámbar (modos Bienestar/Vida):** no están en la presentación. Revalidar con
  marca durante F1.2; si se reencuadran en la familia azul-violeta, ajustar tokens.
- **Logo:** bloqueante de F3, no del resto. El resto del rediseño convive con el logo
  actual sin problema.
- **Chat streaming (W3) — orden explícito:** F2.3 (rediseño UI) y W3 (streaming, del
  [`FRONTEND-CHAT-PLAN.md`](./FRONTEND-CHAT-PLAN.md)) tocan los **mismos** componentes
  (`MessageList`, `ChatComposer`, `MessageBubble`). W2 ya está mergeado; W3 está
  pendiente. **Decisión: F2.3 va primero** y deja los enganches de streaming (cursor,
  buffer de markdown, estados del composer) contemplados en la estructura; W3 se
  retoma **después**, sobre la UI nueva. **No correr F2.3 y W3 en paralelo.**
- **Mobile:** es Capa 4 — construir, no rediseñar (el esqueleto no tiene pantallas).
  Las fundaciones (F0) se crean RN-portables para habilitarlo.
- **Verificación visual:** no se hace por PR; se confía en los gates automáticos. Una
  pasada de QA visual al final queda disponible si el usuario la pide.

## Secuencia de PRs (resumen)

1. F0.1 guía de marca al repo · F0.0 wiring de `packages/ui`
2. F0.2 set de íconos `packages/ui`
3. F0.3 MemoryField + grano
4. F0.4 helpers de motion
5. F1.1 primitives base
6. F1.2 primitives de marca + PromptChip
7. F1.3 tipografía editorial + showcase en `test-ds`
8. F2.1 onboarding (5 steps + outro)
9. F2.2 home
10. F2.3 chat *(antes de W3)*
11. F2.4 soporte + `test-mock`
12. F3.1 logo (review de marca como CODEOWNERS)
13. Capa 4 — mobile *(plan propio; arranca tras F0–F3)*

> Cada PR: rama desde `origin/main` · commits atómicos · review con `code-reviewer` ·
> cadena de calidad verde (leída, no asumida) · merge por rebase.
