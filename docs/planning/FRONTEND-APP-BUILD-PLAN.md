# FRONTEND-APP-BUILD-PLAN — Construcción de todas las vistas de Ynara

> **Propósito.** Construir **todas las vistas** del producto Ynara según los
> wireframes de media fidelidad (`C:\Users\mateo\Desktop\Uni\Tesis-Ynara\wireframes`,
> archivo `.pen` de Pencil, 20 pantallas) y **conectarlas al backend donde se
> pueda**, mockeando con contratos tipados lo que todavía no existe.
>
> **Fidelidad.** Los wireframes son **media fidelidad**: se toma la
> **estructura, jerarquía y contenido**, NO el estilo. La fidelidad visual la
> da el design system v2 de Ynara (`DESIGN.md`, tokens de `globals.css`,
> primitives de Capa 0/1).
>
> **Relación con planes existentes.**
> - **Supersede** la noción de "home" del [`FRONTEND-REDESIGN-PLAN.md`](./FRONTEND-REDESIGN-PLAN.md)
>   §F2.2: lo que ahí era "home = saludo + recomendaciones + input deshabilitado"
>   era un **placeholder**. La home real es el **dashboard "Hoy"** (tab dentro de
>   una nav de 4 tabs). La Capa 1 (primitives) y F2.1 (onboarding) del redesign
>   plan **siguen válidas y ya están mergeadas**.
> - **Coordina con** el [`FRONTEND-CHAT-PLAN.md`](./FRONTEND-CHAT-PLAN.md): la
>   vista Chat de este plan = las fases W3–W6 de ese plan (streaming, actions,
>   integración). No se duplican: este plan referencia W3+ para el detalle del chat.
>
> **Cómo se ejecuta.** Una fase a la vez, PRs atómicas, gates antes de cantar
> verde (`biome` · `tsc` · `next build` · `vitest`), review con `code-reviewer`
> en lane separado, merge a `main` por rebase. Reglas no negociables en
> [`AGENTS.md`](../../AGENTS.md). **Backend: toda migración/tabla nueva requiere
> OK humano (regla #1) y, si toca tablas sagradas, aprobación formal (regla #3).**

---

## 0. TL;DR — el mapa en una pantalla

**Producto = onboarding + app de 4 tabs (`Hoy / Chat / Agenda / Tú`) con sub-vistas.**

| Vista | Wireframe | Backend hoy | Estrategia |
|---|---|---|---|
| Onboarding (auth→nombre→día→modos→a11y→outro) | 1–5 | **Auth REAL** | Ya hecho (F2.1). Conectar auth real (hoy mock MSW). Gaps: Splash, Permisos. |
| **Hoy** (dashboard) | 6, 7, 13, 16 | Tareas/sugerencias/recap **INEXISTENTE** | UI + **mock tipado**; backend Tasks después. |
| Mode Switcher (sheet) | 12 | Modos = config, sin endpoint | `GET /v1/modes` (bajo esfuerzo) o mock. |
| Check-in / Recap (sheets) | 14, 15 | **INEXISTENTE** (necesita LLM) | UI + mock; backend cuando haya LLM real. |
| **Chat** (activo/vacío) | 8, 9 | **FUNCIONAL, LLM fake** + SSE real | = Chat plan **W3–W6**. Conectar streaming real (mock SSE primero). |
| **Agenda** (día/semana) | 10, 11 | **STUB** (solo tools calendar) | UI + mock; backend Events después. |
| **Memoria** (timeline/detalle) | 17, 20 | **REAL** (CRUD memoria completo) | **Conectar al backend real.** |
| **Búsqueda** | 18, 19 | search = solo tool LLM | `GET /v1/memory/search` (bajo esfuerzo) → conectar. |
| **Tú** (perfil/ajustes) | *(no wireframeado)* | `GET /me` real; `PATCH` falta | `PATCH /v1/users/me` (bajo esfuerzo). **Diseño pendiente.** |

**Gradiente de connectabilidad:**
- **Conectar YA (real):** Auth · Sesiones · **Memoria (timeline/detalle)** · Chat (LLM fake pero funcional + SSE).
- **Endpoint chico + conectar:** `GET /v1/modes` · `GET /v1/memory/search` · `PATCH /v1/users/me`.
- **Build backend grande (mock primero):** Tareas (Hoy) · Events (Agenda) · Sugerencias/Check-in/Recap (dependen de LLM real) · modelo `Message` (persistir turnos).

---

## 1. Inventario de pantallas (20 wireframes → arquitectura)

Wireframes en el `.pen` (abrir con tools de Pencil; ids entre paréntesis). Mobile 375×812. **Cada `nav*` confirma la tab bar de 4 ítems: `Hoy / Chat / Agenda / Tú`.**

### Onboarding (flujo lineal, fuera de las tabs)
| # | Wireframe (id) | Qué es | Estado web actual |
|---|---|---|---|
| 1 | Splash (`WFN0T`) | Marca + tagline al abrir | **No existe** en web (gap menor) |
| 2 | Captura contexto (`nr66J`) | Capturar nombre/contexto inicial | Cubierto por `NameStep` (slug `nombre`) |
| 3 | Modos (`ddUih`) | Elegir modos de interés | Cubierto por `ModesStep` (slug `modos`) |
| 4 | Permisos (`gdJBg`) | Permisos (notificaciones, etc.) | **No existe** en web (gap; decidir si aplica web) |
| 5 | Primer Hoy (`pT5ot`) | Primer "Hoy" con empty + nav | Cubierto parcialmente por `CelebrationOutro` → `/home` |

> El onboarding web real es `auth → nombre → día → modos → a11y → outro`
> (ya rediseñado en F2.1). El wireframe agrega **Splash** y **Permisos** y un
> "Primer Hoy". **Decisión a tomar:** ¿se suman Splash/Permisos a web, o son
> mobile-only? (web no necesita permisos de notificaciones todavía).

### Tab **Hoy** (dashboard proactivo)
| # | Wireframe (id) | Qué es | Secciones (del wireframe) |
|---|---|---|---|
| 6 | **Hoy normal** (`oHwhH`) | **La home real.** | Header (chip modo + "Hoy" + fecha + avatar) · **Prioridades del día** (lista con check + hora/contexto) · **Sugerencias** (cards proactivas con "porqué") · **Recap pendiente** (CTA oscuro) · nav |
| 7 | Hoy vacío (`TYcDU`) | Hoy sin tareas/sugerencias | header · empty state · nav |
| 13 | Modo Estudio (`N2XXW8`) | Variante de Hoy con tint estudio | header · secciones a/b/c (contenido por modo) · nav |
| 16 | Modo Bienestar (`Qn7AQ`) | Variante con tint bienestar | **banner "Sin conexión · trabajando local"** · header · card "respiración" (160px) · secciones · nav |

> Las variantes por modo (13, 16) son la **misma estructura de Hoy** re-tintada
> y con contenido adaptado al modo activo. No son pantallas separadas: son
> estados de la misma vista Hoy. **16 muestra un banner offline** (relevante:
> Ynara funciona local) y una card de "respiración" (bienestar).

### Tab **Hoy** — sheets (modales sobre Hoy)
| # | Wireframe (id) | Qué es | Forma |
|---|---|---|---|
| 12 | Mode Switcher (`bCiSI`) | Cambiar de modo | **bottom sheet** (handle 40×4, lista de modos) sobre Hoy en ghost |
| 14 | Check-in matinal (`TkVE5`) | Check-in de la mañana | **bottom sheet** sobre Hoy |
| 15 | Recap del día (`o1ZG3`) | Cierre del día con Ynara | **bottom sheet** sobre Hoy |

### Tab **Chat**
| # | Wireframe (id) | Qué es | Secciones |
|---|---|---|---|
| 8 | Chat activo (`qkUOK`) | Conversación con mensajes | header (modo) · lista de mensajes · input · nav |
| 9 | Chat vacío (`dadnz`) | Chat sin mensajes (welcome) | header · welcome body · input · nav |

### Tab **Agenda**
| # | Wireframe (id) | Qué es | Secciones |
|---|---|---|---|
| 10 | Agenda día (`X1xQf`) | Vista de día | header · grid de bloques horarios · nav |
| 11 | Agenda semana (`TFcwY`) | Vista de semana | header · selector de días · grid · nota · nav |

### Tab **Tú** / sección Memoria + Búsqueda
| # | Wireframe (id) | Qué es | Secciones |
|---|---|---|---|
| 17 | Memoria Timeline (`ZDeFS`) | Timeline de recuerdos | header · search bar · filtros · lista cronológica · nav |
| 18 | Búsqueda vacía (`T0QjOW`) | Búsqueda sin query | search bar · sugerencias/secciones · empty · nav |
| 19 | Búsqueda resultados (`ghrtV`) | Resultados de búsqueda | search bar · skeleton de carga · "N RESULTADOS" · lista · nav |
| 20 | Detalle memoria (`Z5sxU`) | Detalle de un recuerdo | back bar · meta · **quote grande** ("Decidiste arrancar la tesis por el cap. 3…") · cita · contexto · relacionados |

> **No hay wireframe explícito de "Tú" (perfil/ajustes).** La 4ª tab necesita
> diseño: probablemente perfil + acceso a Memoria/Búsqueda + ajustes (a11y,
> retención, export/wipe de memoria, logout). **Decisión de producto pendiente.**

---

## 2. Estado del backend (resumen de la investigación)

Stack: **FastAPI + SQLAlchemy 2 async + Postgres/pgvector + Alembic + Celery/Redis + JWT**. Detalle en `apps/backend/docs/ENDPOINTS.md` y `MODELS.md`.

### Lo que YA es real y connectable
| Dominio | Endpoints | Notas |
|---|---|---|
| **Auth** | `POST /v1/auth/register`, `POST /v1/auth/token`, `GET /v1/auth/me` | JWT + bcrypt reales contra DB. Falta refresh/logout (diferidos). |
| **Sesiones** | `GET /v1/sessions`, `GET /v1/sessions/{id}`, `POST /v1/sessions/{id}/close` | Reales. **No hay modelo `Message`**: la sesión es solo metadata (los turnos no se persisten individualmente). |
| **Memoria** | `GET /v1/memory`, `GET /v1/memory/{layer}/{ref}`, `GET /v1/memory/export`, `PATCH …`, `DELETE …`, `GET/POST /v1/memory/wipe` | CRUD completo, cifrado AES-256-GCM real. Embeddings/reranker son **fakes deterministas** (sin GPU). |
| **Chat** | `POST /v1/chat`, `POST /v1/chat/stream` (SSE) | **Funcional pero LLM FAKE** (`FakeLlmClient`, respuestas programadas). El SSE es "replay streaming" (no token-by-token real del modelo). Contrato SSE en `packages/shared-schemas/src/sse.ts`. |

### Endpoints chicos a agregar (bajo esfuerzo, desbloquean vistas)
| Endpoint | Para | Esfuerzo |
|---|---|---|
| `GET /v1/modes` | Mode Switcher (12), chips de modo | Bajo — leer `ynara.config.json` y devolver lista. |
| `GET /v1/memory/search?q=` | Búsqueda (18/19), Memoria | Bajo — el store `search()` (embed+ANN+decrypt+rerank) ya existe como tool del LLM; exponerlo como endpoint HTTP del dueño. |
| `PATCH /v1/users/me` | Tú/perfil (display_name, retention, onboarding_completed) | Bajo — el schema `UserUpdate` ya existe (`apps/backend/app/schemas/user.py`); falta endpoint + service. |

### Builds grandes (UI con mock primero, backend después, **gate de aprobación**)
| Dominio | Qué falta | Bloqueos |
|---|---|---|
| **Tareas/Prioridades** (Hoy) | Modelo `Task` + migración + schema + service + CRUD (`GET/POST/PATCH/DELETE /v1/tasks`) + lógica "prioridades del día" | Migración → **regla #1** (OK humano). |
| **Events/Agenda** | Modelo `CalendarEvent` (o integración CalDAV/Google) + migración + CRUD + cablear tools `calendar.*` (hoy stub) | Migración + decisión "modelo propio vs integración". |
| **Sugerencias / Check-in / Recap** | Generación por LLM a partir de memoria + tareas + agenda + tiempo | **Dependen de LLM real.** Más complejos. |
| **`Message` model** | Persistir turnos dentro de la sesión (para recap, historial, check-in) | Migración. Hoy el chat no guarda mensajes. |
| **LLM real** | Swap `FakeLlmClient`→`ResilientClient`/vLLM en `apps/backend/app/main.py` lifespan | Requiere infra GPU/vLLM **on-prem** (la regla #4 exige inferencia/datos dentro del perímetro, sin APIs externas). Desbloquea calidad de chat + sugerencias + recap. |

---

## 3. Arquitectura a introducir en el frontend

### 3.1 App shell + navegación por tabs (lo más estructural)
Hoy `apps/web` **no tiene navegación por tabs**. Hay que introducir un **shell de app** con las 4 tabs `Hoy / Chat / Agenda / Tú`.

- **Rutas nuevas** (App Router):
  - `/hoy` (o redefinir `/home` → `/hoy`) — tab Hoy.
  - `/chat` y `/chat/[sessionId]` — tab Chat (ya existe la dinámica).
  - `/agenda` — tab Agenda.
  - `/tu` — tab Tú (perfil + memoria + ajustes).
  - `/memoria`, `/memoria/[id]`, `/buscar` — sub-vistas (bajo Tú o accesibles desde Hoy).
- **Layout de shell** (`app/(app)/layout.tsx` con route group): renderiza la tab bar + el contenido. Guard de auth/onboarding.
- **Responsive (clave, pedido del usuario "como Claude/ChatGPT"):**
  - **Mobile:** bottom tab bar fija (los `nav*` del wireframe). `safe-area-inset-bottom`.
  - **Desktop:** la tab bar se convierte en **sidebar** (izquierda) o top-nav; el contenido usa el ancho con un max-width cómodo. Mismo árbol, distinto chrome por breakpoint.
- **Sheets** (Mode Switcher / Check-in / Recap): patrón bottom-sheet en mobile, modal/popover centrado en desktop. Usar `<dialog>` (como `SkipConfirmDialog` del onboarding) o un primitive `Sheet` nuevo.

### 3.2 Data layer
- **Estandarizar TanStack Query** (ya está instalado, con provider en `app/providers.tsx`, y en uso con `useMutation` en auth/chat/onboarding): falta estandarizar el patrón **`useQuery` para server-state** (sesiones, memoria, tareas): query keys, defaults de `staleTime`/`gcTime`, e invalidación consistente.
- **Inyección de token**: `apps/web/src/lib/api.ts` debe mandar `Authorization: Bearer <token>` desde `useUserStore` (hoy es un TODO). **Esto es prerrequisito para conectar cualquier endpoint real.**
- **Contratos tipados**: extender `@ynara/shared-schemas` con los schemas Zod de cada dominio nuevo (Task, Event, Suggestion, Memory list/detail, Modes) — fuente única de verdad front/back.
- **Mock-first con MSW**: para dominios sin backend (tasks/agenda/suggestions/recap), agregar handlers MSW que devuelvan data tipada contra los mismos schemas Zod. **La UI se construye contra el mock; cuando el backend exista, se apaga el handler y queda real sin tocar la UI.** Toggle por env (`EXPO_PUBLIC_ENABLE_MOCKS`).

### 3.3 Principio de connectabilidad por vista
Cada vista declara su **fuente de datos**: `real` (endpoint existe) · `endpoint-chico` (agregar y conectar) · `mock` (MSW tipado hasta que exista backend). Así se puede avanzar todo el frontend sin esperar el backend, y conectar incrementalmente.

### 3.4 Derivación: pantallas sin wireframe y layouts desktop ⭐
**Principio rector (decisión del usuario): no bloquear por falta de diseño — derivar del resto.**

- **Pantallas sin wireframe** (hoy: **Tú/perfil**; y cualquier otra que falte o aparezca): se **diseñan extrapolando del resto** de las pantallas ya wireframeadas + el design system v2. Reusar los mismos patrones: header (chip de modo + título + fecha/avatar), tab bar, cards de sección, tints por modo, tipografía editorial, sheets. **Se propone y se construye** con criterio y consistencia — NO se espera un wireframe nuevo. Si hay una duda de producto fuerte, se marca y se sigue con un default razonable.
- **Layouts desktop**: **todos los wireframes son mobile (375px).** El desktop **se deriva** del mobile + el patrón responsive del shell (§3.1): **mismo contenido y jerarquía**, chrome adaptado — sidebar en vez de bottom-tabs, anchos cómodos con max-width, grids que aprovechan el ancho (Agenda día/semana, Memoria timeline, Hoy), sheets que pasan a modal/popover centrado. **No se esperan wireframes de desktop**; se derivan con consistencia (referencia de responsividad: apps tipo Claude/ChatGPT). **Cada vista se entrega mobile-first Y responsive a desktop en la misma PR** — no es un paso aparte.

> Regla práctica: ante "falta el diseño de X" (pantalla nueva o breakpoint desktop),
> el default es **derivarlo del lenguaje ya establecido y avanzar**, no frenar.

---

## 4. Fases de ejecución (PRs)

> Orden pensado para **destrabar la navegación primero**, después las vistas
> conectables al backend real, después las mockeadas. Cada fase = varias PRs
> atómicas. Las fases de backend corren en un **track paralelo** con sus gates.

### Fase A — App shell + navegación (fundación) ⭐ empezar acá
- **A1** `TabBar` / `AppShell` responsive (bottom tabs mobile / sidebar desktop) + route group `app/(app)/`.
- **A2** Rutas stub de las 4 tabs + sub-vistas (`/hoy`, `/agenda`, `/tu`, `/memoria`, `/buscar`) con placeholders. Migrar `/home` → `/hoy` (o alias). Guard de auth/onboarding en el layout.
- **A3** Primitive `Sheet` (bottom-sheet mobile / modal desktop) reutilizable para 12/14/15.
- **Sin backend.** Desbloquea todo lo demás.

### Fase B — Data foundations (prerrequisito de "conectar al back")
- **B1** Inyección de `Authorization: Bearer` en `lib/api.ts` desde `useUserStore`.
- **B2** Estandarizar el patrón de hooks de TanStack Query (ya instalado + provider): definir query keys, `useQuery` para server-state (hoy solo se usa `useMutation`), defaults de cache, y manejo de errores/loading estándar.
- **B3** Conectar **auth real** (hoy el front usa MSW para `/v1/auth/*`): apuntar a backend real detrás del toggle de mocks; validar register/login/me end-to-end.
- **B4** Extender `@ynara/shared-schemas` con los schemas base de los dominios nuevos.

### Fase C — Tab **Memoria + Búsqueda** (la más conectable: backend REAL) ⭐ alto valor
- **C1** `GET /v1/memory` → **Memoria Timeline** (17): lista cronológica, filtros por capa, estados loading/empty. *(real)*
- **C2** `GET /v1/memory/{layer}/{ref}` → **Detalle memoria** (20): quote grande, contexto, relacionados, acciones (editar `PATCH`, borrar `DELETE`). *(real)*
- **C3** Backend `GET /v1/memory/search?q=` *(endpoint-chico, backend PR)* + **Búsqueda** (18 vacía / 19 resultados): search bar, skeleton, "N RESULTADOS", empty. *(real tras endpoint)*
- Es la vista con backend más completo → conectar de verdad da una victoria temprana.

### Fase D — Tab **Chat** (= Chat plan W3–W6)
- Seguir [`FRONTEND-CHAT-PLAN.md`](./FRONTEND-CHAT-PLAN.md): **W3** (streaming SSE: mock handler `/v1/chat/stream` + `useChatStream` + auto-scroll inteligente + botón detener), **W4** (`ActionCard` para tools), **W5** (integración Hoy→Chat: crear sesión + prefill desde una sugerencia/tarea), **W6** (tests).
- Vistas: **Chat activo** (8) y **Chat vacío** (9, welcome editorial + PromptChips).
- *(funcional con LLM fake; SSE real disponible)*. **F2.3 del redesign plan va antes de W3** (rediseño UI primero) — acá se unifican.

### Fase E — Tab **Hoy** (dashboard) — mock-first
- **E1** Estructura de Hoy: header (chip modo + "Hoy" + fecha + avatar) + layout responsive.
- **E2** **Prioridades del día**: componente lista con check + hora/contexto. *(mock tipado `tasks`)* → backend Tasks después.
- **E3** **Sugerencias**: cards proactivas con "porqué". *(mock)* → backend Suggestions (necesita LLM).
- **E4** **Recap pendiente** CTA → abre sheet Recap (15). *(mock)*
- **E5** Variantes por modo (13 Estudio, 16 Bienestar) + banner offline + estado vacío (7).
- Backend track paralelo: **Tasks model + CRUD** (gate migración) para conectar E2.

### Fase F — Tab **Agenda** — mock-first
- **F1** **Agenda día** (10): grid de bloques horarios. *(mock `events`)*
- **F2** **Agenda semana** (11): selector de días + grid + nota. *(mock)*
- Backend track: **CalendarEvent model + CRUD** + cablear tools `calendar.*` (gate migración + decisión modelo-propio-vs-integración).

### Fase G — Tab **Tú** (perfil/ajustes)
- **G1** **Diseño de la pantalla Tú** (no hay wireframe) — proponer: perfil (nombre, avatar), acceso a Memoria/Búsqueda, ajustes a11y (ya existe el store), retención/export/wipe de memoria (endpoints reales), logout.
- **G2** Backend `PATCH /v1/users/me` *(endpoint-chico)* + conectar edición de perfil. *(real tras endpoint)*
- **G3** Conectar export/wipe de memoria (endpoints reales) con confirmaciones.

### Fase H — Sheets de modo (Mode Switcher / Check-in / Recap)
- **H1** **Mode Switcher** (12): sheet con lista de modos (cada uno su gradiente). *(`GET /v1/modes` endpoint-chico, o mock)*. Cambia el modo activo global.
- **H2** **Check-in matinal** (14) y **Recap del día** (15): sheets con contenido generado. *(mock; backend cuando haya LLM real — probablemente variantes del chat con system prompt dedicado)*.

### Track Backend (paralelo, con sus gates) 
1. `GET /v1/modes` (bajo) · `GET /v1/memory/search` (bajo) · `PATCH /v1/users/me` (bajo) — **desbloquean C3, G2, H1**.
2. `Task` model + migración + CRUD — **conecta E2**. *(gate regla #1)*
3. `Message` model + migración — **persistir turnos** (historial chat, recap). *(gate regla #1)*
4. `CalendarEvent` model + CRUD + tools — **conecta F**. *(gate regla #1 + decisión)*
5. **LLM real** (swap lifespan) — **calidad chat + sugerencias + check-in + recap**. *(infra GPU/vLLM on-prem; regla #4 = inferencia/datos dentro del perímetro)*

---

## 5. Riesgos y gates

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **LLM fake** en todo el chat | Chat/sugerencias/recap son stubs hasta conectar vLLM | Construir UI contra el fake (contrato estable); el swap es solo el lifespan. Marcar como "demo" hasta LLM real. |
| **Migraciones nuevas** (Tasks, Events, Message) | **Regla #1**: OK humano antes de cada migración | Aislar cada modelo en su PR; pedir confirmación explícita con qué/por qué. |
| **Tablas sagradas** (memoria/audit) | **Regla #3**: aprobación formal + tests + commit aislado | Las vistas de Memoria solo **leen/editan vía endpoints existentes** — NO tocar `app/memory/` ni los modelos sagrados salvo PR dedicado aprobado. |
| **Sin `Message` model** | Recap/check-in/historial no tienen de dónde leer turnos | Mock primero; priorizar el modelo `Message` si esas vistas se vuelven reales. |
| **Navegación nueva** rompe rutas/guards actuales | Onboarding/redirects existentes | A2 con cuidado: preservar el guard de `/` y el cierre de onboarding; tests de routing. |
| **Mobile esqueleto** | `apps/mobile` no tiene nada | Este plan es **web**. Mobile es su propio plan (Capa 4 / chat plan M0–M5), reusando primitives RN-portables. |
| **Token injection** ausente | Nada real conecta sin auth header | B1 es prerrequisito duro de toda conexión real. |
| **Gaps de wireframe** (Tú, Splash, Permisos) | Pantallas sin spec | Decidir con el usuario (sección 6). |

---

## 6. Decisiones pendientes (para resolver con el usuario antes/durante)

1. **Pantalla "Tú"**: sin wireframe → **se deriva** del resto (§3.4). Default propuesto: perfil + ajustes a11y + memoria/export/wipe + logout (diseño en G1). Confirmá el alcance o dejá que lo proponga y avance.
2. **Splash y Permisos** (wireframes 1, 4): ¿se suman al onboarding web o son mobile-only? (web no pide permisos de notificaciones todavía). Si se suman, se derivan al estilo del onboarding ya hecho (§3.4).
3. **Desktop**: se **deriva** del mobile en cada vista (§3.4), sin esperar wireframes de desktop. Solo confirmar si hay alguna vista donde quieras un layout desktop específico distinto del derivado.
4. **Tasks/Agenda — modelo propio vs integración**: ¿Ynara tiene su propia DB de tareas/eventos, o integra con Google Calendar/CalDAV? Cambia el backend.
5. **`/home` → `/hoy`**: ¿renombrar la ruta o mantener `/home` como alias de Hoy?
6. **Orden de prioridad de vistas**: ¿el usuario quiere primero las conectables (Memoria/Chat) o primero la Hoy (la cara de la app)? Recomendación: **A → B → (C Memoria ‖ E Hoy mock) → D Chat → F → G → H**.
7. **LLM real**: ¿hay infra vLLM/Ollama on-prem disponible para el swap, o seguimos con fake un tiempo?

---

## 7. Recomendación de arranque (para la sesión de ejecución)

1. **Fase A (shell + tabs responsive)** — es la fundación; sin esto no hay app multi-vista. Empezar por `AppShell`/`TabBar` + route group + el primitive `Sheet`.
2. **Fase B (data foundations)** en paralelo — token injection + TanStack Query (prerrequisito de conectar al back).
3. Después, **la primera vista conectada de verdad: Memoria (Fase C)** — backend real, victoria temprana y tangible.
4. En paralelo, **Hoy (Fase E) mock-first** — es la cara de la app y lo que el usuario quería ver lleno.
5. Backend track: arrancar por los **3 endpoints chicos** (`/modes`, `/memory/search`, `/users/me`) que desbloquean varias vistas con poco esfuerzo.

Cada vista: tomar el wireframe (Pencil, screenshot del id correspondiente), subirlo de fidelidad con el design system, mobile-first + responsive a desktop, gates + reviewer, merge por rebase.

---

## Apéndice — referencias

- **Wireframes**: `C:\Users\mateo\Desktop\Uni\Tesis-Ynara\wireframes` (`.pen`, abrir con tools de Pencil). Ids por pantalla en la sección 1.
- **Backend**: `apps/backend/docs/ENDPOINTS.md`, `apps/backend/docs/MODELS.md`, `apps/backend/AGENTS.md`. Lifespan con fakes: `apps/backend/app/main.py`. Stub calendar/reminder: `apps/backend/app/llm/tools/{calendar,reminder}.py`. `UserUpdate` sin endpoint: `apps/backend/app/schemas/user.py`.
- **Frontend**: rutas `apps/web/src/app/`, features `apps/web/src/features/{onboarding,home,chat}`, API `apps/web/src/lib/api.ts` + mocks `api.mocks.ts`, primitives `apps/web/src/components/ui/`, `@ynara/ui`, tokens `apps/web/src/app/globals.css`.
- **Contratos compartidos**: `packages/shared-schemas/` (incl. `src/sse.ts` para el streaming).
- **Planes**: [`FRONTEND-REDESIGN-PLAN.md`](./FRONTEND-REDESIGN-PLAN.md) (Capa 0/1 done, F2.1 onboarding done), [`FRONTEND-CHAT-PLAN.md`](./FRONTEND-CHAT-PLAN.md) (S0 done, W3+ pendiente), [`DESIGN.md`](../../DESIGN.md) (sistema visual v2, §10 chat).
- **Reglas**: [`AGENTS.md`](../../AGENTS.md) (10 no negociables; #1 OK humano para commits/migraciones, #3 tablas sagradas, #4 datos on-prem, #5 sin Supabase en front).
