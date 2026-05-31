# Plan de rediseño del frontend — Sistema visual v2

> **Objetivo.** Llevar todo el frontend web existente al sistema de diseño v2
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
| **Alcance** | **Web + fundaciones compartidas** en `packages/ui` (sirven a web y, después, a mobile). Mobile-only queda fuera. |
| **Estructura** | **Por capas**: sistema gráfico → primitives → pantallas. Minimiza retrabajo. |
| **Logo (`YnaraMark`)** | **Revisar con marca primero** (@BriarDevv/@querques20) antes de tocarlo. Bloqueante para la fase de logo, no para el resto. |
| **Verificación visual** | **En hitos clave** (no en cada PR chico): fin de cada fase de pantallas, light + dark. |

## Principios de ejecución (heredados del flujo actual)

- Una **rama por fase/PR**, partiendo siempre de `origin/main`.
- **Commits atómicos** en español (Conventional Commits), trailer de co-autoría.
- **Review con agente independiente** (`code-reviewer`) antes de cada merge — nunca
  auto-aprobación en el mismo contexto.
- **Cadena de calidad** verde antes de mergear: biome · `tsc` · `next build` ·
  `vitest` · `ynara-doctor`. En hitos: + verificación visual.
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
- `GrainOverlay`: capa de grano reutilizable (envuelve el utility `.bg-grain` ya
  creado en globals).
- Performance: SVG estático o canvas liviano; **nada de loops infinitos**; respeta
  `prefers-reduced-motion`.
- **Verificación visual** (densidades, light/dark) en este PR.

### F0.4 — Helpers de motion — [DESIGN.md §8]
- Evaluar `motion` (Framer Motion) para springs perceptuales + microinteracciones, o
  CSS puro si alcanza. Decisión técnica en el PR (bundle vs. ergonomía).
- Hooks/utilidades: `useReducedMotion`, presets `spring-snappy`/`spring-soft`,
  helper de View Transitions con progressive enhancement.

> **Hito visual 0:** íconos + MemoryField + grano revisados en pantalla (light/dark)
> antes de seguir.

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
- `EmptyStateCard` (con `MemoryField` de fondo).
- **`PromptChip`** (nuevo) — chip de prompt accionable para empty states de chat.

### F1.3 — Tipografía editorial
- Aplicar `.text-display` y la escala fluida donde corresponda; revisar tracking/
  measure en todos los primitives con texto.

> **Hito visual 1:** página de showcase de primitives (o Storybook ligero) revisada
> light/dark.

---

## Capa 2 — Pantallas

Rediseñar cada pantalla usando primitives + sistema gráfico. Orden por dependencia.

### F2.1 — Onboarding (`features/onboarding`, 6 steps)
- `OnboardingFlow` + steps (Welcome, Identity, Modes, Memory, Accessibility, Outro).
- **Welcome/Outro como piezas editoriales** (big type `.text-display` + `MemoryField`
  de fondo + copy con voz de marca, estilo posters del slide 09).
- Motion con significado: nodos que se encienden, vínculos que se dibujan, diamante
  de foco. Stagger sutil entre steps con View Transitions.
- **Hito visual.**

### F2.2 — Home (`app/home/page.tsx`)
- Layout intencional (no centrado-en-todo). Jerarquía por peso/contraste.
- `SuggestionCard`s con tints de modo; sin emojis.
- **Hito visual.**

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
- **Hito visual.**

### F2.4 — Pantallas de soporte
- `/a11y` (settings), `/` (landing/redirect), estados de error/404.
- **Hito visual** (cierre).

---

## Capa 3 — Logo (bloqueada por marca)

### F3.1 — `YnaraMark` alineado a marca
- Migrar a colores/formas reales de la presentación (diamante, rampa de memoria real
  en vez de `--color-violet-*` legacy).
- **Requiere OK de @BriarDevv/@querques20** antes de implementar (decisión de marca).
- Al cerrarse: eliminar `--color-violet-*` legacy si ya nadie los usa, y unificar en
  la rampa de memoria.

---

## Riesgos y notas

- **Jade/ámbar (modos Bienestar/Vida):** no están en la presentación. Revalidar con
  marca durante F1.2; si se reencuadran en la familia azul-violeta, ajustar tokens.
- **Logo:** bloqueante de F3, no del resto. El resto del rediseño convive con el logo
  actual sin problema.
- **Chat streaming (W3+):** este plan rediseña la **UI** del chat; la lógica de
  streaming/acciones sigue el [`FRONTEND-CHAT-PLAN.md`](./FRONTEND-CHAT-PLAN.md)
  (pausado en W2). Coordinar para no pisarse: el rediseño de `MessageList`/`Composer`
  debe dejar enganches para W3.
- **Mobile:** las fundaciones (F0) se crean en `packages/ui` pensando en portabilidad
  RN, pero el rediseño de pantallas mobile es un plan aparte.
- **Verificación visual:** "en hitos clave" — se hace en navegador real (light+dark),
  no solo gates automáticos.

## Secuencia de PRs (resumen)

1. F0.1 guía de marca al repo
2. F0.2 set de íconos `packages/ui` ⟶ *hito visual*
3. F0.3 MemoryField + grano ⟶ *hito visual*
4. F0.4 helpers de motion
5. F1.1 primitives base
6. F1.2 primitives de marca + PromptChip
7. F1.3 tipografía editorial ⟶ *hito visual (showcase)*
8. F2.1 onboarding ⟶ *hito visual*
9. F2.2 home ⟶ *hito visual*
10. F2.3 chat ⟶ *hito visual*
11. F2.4 soporte ⟶ *hito visual (cierre)*
12. F3.1 logo *(bloqueado por marca)*

> Cada PR: rama desde `origin/main` · commits atómicos · review con `code-reviewer` ·
> cadena de calidad verde · merge por rebase.
