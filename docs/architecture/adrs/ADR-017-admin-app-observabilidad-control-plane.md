# ADR-017: App de administración interna (`apps/admin`): observabilidad y control plane

## Estado

Propuesto

## Fecha

2026-06-19

## Contexto

El equipo (operadores técnicos y founders) no tiene hoy ninguna superficie
para **observar ni operar** Ynara. Toda la API es mono-tenant: cada endpoint
resuelve por `user_id` extraído del JWT y no existe ningún eje de
autorización por encima del usuario (un `grep` de `is_admin|role|scope` sobre
`apps/backend` no devuelve nada en la capa de auth). No hay endpoints de
agregación cross-tenant: todos los `COUNT`/listados son por usuario propio.

Eso deja al equipo sin respuestas operativas básicas: cuántos usuarios hay y
cuántos son efímeros vs reales, qué modo se usa más, si el worker de
consolidación episódica está al día, qué pasó con el `audit_log`, si el guard
anti-prod está activo (incidente 2026-05-31), o si el serving LLM está sano.

Un relevamiento del esquema y de la API muestra dos realidades distintas:

**Lo que ya existe y solo falta exponer:**

- `audit_log` está escrito e indexado (`ix_audit_log_created_at`,
  `ix_audit_log_user_id`) pero **ningún endpoint lo lee**.
- Health checks (`GET /v1/health/ready` pinga DB + Redis;
  `GET /v1/modes` sirve el catálogo de modos) ya existen.
- `users`, `sessions` y las 3 capas de memoria permiten derivar métricas de
  negocio y de "salud del moat" (conteos, crecimiento, mix de modos, DAU/WAU/
  MAU cruzando `sessions.started_at`) — todo vía agregación SQL, sin instrumentación nueva.

**Lo que un dashboard de ops querría y hoy NO se persiste (gaps):**

- Latencia LLM (TTFT, tokens/seg, total), tokens in/out y costo por
  turno/sesión/modelo.
- Errores/timeouts/fallbacks de inferencia: el "turno degradado" no queda en DB.
- Telemetría de infra: GPU/VRAM, cola de inferencia, throughput.
- Estado de los workers Celery (jobs ok/fail/retry, backlog) — solo se
  aproxima indirectamente (lag `episodic.created_at - occurred_at`, backlog de
  `conversation_turns`).
- DAU/WAU/MAU como métrica de primera clase (no hay `users.last_active_at`).
- Histórico de profundidad de conversación (`conversation_turns` se **purga**
  al consolidar).
- Eventos de auth/seguridad (logins ok/fallidos, reuse-detection de refresh):
  la lógica existe en `security.py` pero no hay tabla.

Esta decisión amerita ADR por tres motivos acumulados (AGENTS regla #6
extendida; CONTRIBUTING "cambios arquitectónicos"):

1. **Estructura del monorepo**: una app nueva en `apps/` que sobrevive a esta
   etapa (mismo criterio que [ADR-016](./ADR-016-mobile-codigo-compartido-packages-core.md)).
2. **Nuevo eje de autorización**: introduce el concepto de "admin", que hoy no
   existe en el modelo de datos ni en la auth.
3. **Control plane sobre el serving**: el objetivo final incluye operar las
   IAs en runtime (cambiar de modelo, modo de bajo rendimiento), lo que muta
   configuración de serving — territorio arquitectónico y bajo el gate de
   regla #1 (toca `ynara.config.json`/serving, ver
   [ADR-013](./ADR-013-serving-endpoints-config.md)/[ADR-014](./ADR-014-serving-ollama-gguf-16gb.md)).

Restricciones duras que condicionan el diseño (AGENTS):

- **Soberanía** (regla #4): ningún dato de usuario sale del perímetro →
  prohibido cualquier analytics de terceros cloud (PostHog/Amplitude/Mixpanel).
- **Tablas sagradas** (regla #3): las 3 capas de memoria + `audit_log` son
  read-only para el admin; nunca se mutan desde acá.
- **Sin cliente JS de Supabase** (regla #5): todo acceso a datos pasa por
  FastAPI.
- **Cifrado per-user** (ADR-007): el contenido de memoria/chat está cifrado
  AES-256-GCM; el admin solo ve **conteos y metadata**, nunca texto descifrado,
  embeddings, `record_hash` ni email crudo.

## Decisión

### D1 — Nueva app `apps/admin` (`@ynara/admin`)

Se crea una app separada en `apps/admin`, paquete `@ynara/admin`, para el
**equipo interno** (operadores técnicos + founders en una sola app, separados
por sección y por rol). El monorepo nombra apps por superficie/función (`web`,
`mobile`, `backend`); `admin` sigue esa convención y dice *quién la usa*.

El panel del **end-user** (ver/editar/exportar/borrar su propia memoria) **no
es parte de este proyecto**: esa capacidad ya está soportada por la API
(`/v1/memory*`, `/v1/memory/export`) y es una feature del usuario autenticado
normal, que vive en `apps/web` (ruta `/cuenta` o `/memoria`), reusando su
propio JWT. Sacarla a una app aparte duplicaría auth sin razón.

Stack: Next.js 16, Tailwind v4 CSS-first reusando los tokens de `DESIGN.md`,
TanStack Query v5, Zustand, shadcn/ui, React Hook Form + Zod desde
`@ynara/shared-schemas` (mismos patrones que `apps/web`). Se sirve en
subdominio separado (`admin.ynara.*`) por higiene de seguridad (superficie
interna aislada del portal de cliente).

### D2 — Eje de autorización admin: columna `is_admin` + seed por config

Se agrega una columna **`is_admin BOOLEAN NOT NULL DEFAULT false`** en `users`
(tabla **operativa**: migración Alembic con review normal, sin el gate de
regla #3). La columna es la **fuente de verdad** del rol admin.

Para resolver el problema del huevo y la gallina (se necesita un admin para
nombrar a los demás desde el panel), una variable de config
`ADMIN_BOOTSTRAP_IDS` (lista de UUIDs) **siembra** de forma idempotente
`is_admin = true` en el arranque para los founders iniciales. La config es
solo para bootstrap; la gestión continua de admins vive en la DB y se opera
desde el panel.

Una dependencia **`require_admin`** reusa toda la maquinaria JWT existente
(validación de access token, `sid`, blocklist en Redis — ver
[ADR-011](./ADR-011-auth-layering-criterion.md)/[ADR-015](./ADR-015-auth-deps-pyjwt-bcrypt.md))
y, además, verifica `is_admin = true` en la fila. Fail-closed: ante la duda,
403.

Se elige `is_admin` boolean (y no una lista en `.env` como modelo, ni un enum
`role`) porque es el punto justo entre escalabilidad y simplicidad: gestión en
runtime, auditable, sobrevive a redeploys, y evoluciona a un enum `role` el
día que haga falta RBAC granular agregando una columna, sin rehacer nada.

### D3 — Tabla `admin_audit` (separada del `audit_log` sagrado)

Toda acción de operador (impersonation, export masivo, revocar la sesión de
otro usuario, suspender una cuenta, otorgar/revocar admin, y en el futuro
cualquier cambio de serving) escribe a una tabla **`admin_audit`** nueva,
**desde el día 1**. Es independiente del `audit_log` de memoria (que es
sagrado y registra solo operaciones de memoria). `admin_audit` registra:
actor admin, acción, target, timestamp y metadata no sensible.

### D4 — Endpoints `/v1/admin/*` de agregación (read-only sobre lo existente)

Se agrega un router admin protegido por `require_admin`:

- `GET /v1/admin/metrics/overview` — usuarios (total, efímeros/reales,
  onboarding), signups por día.
- `GET /v1/admin/metrics/sessions` — totales, abiertas/colgadas, mix de los 5
  modos, DAU/WAU/MAU (derivado de `sessions.started_at`), duración por modo.
- `GET /v1/admin/metrics/memory` — conteos y crecimiento por capa, % sensible
  (Bienestar), salud procedural (% stale, distribución de confidence,
  candidatas a purga), backlog y lag de consolidación.
- `GET /v1/admin/audit` — lectura filtrable del `audit_log` (read-only;
  `record_hash` y contenido **nunca** se exponen).
- `GET /v1/admin/health` — extiende `/health/ready` con estado del guard
  anti-prod y del entorno activo.

Los tipos de respuesta se espejan en `@ynara/shared-schemas` (Pydantic ↔ Zod),
igual que el resto del front.

### D5 — Frontera de privacidad (qué se puede mostrar)

Read-only sobre tablas sagradas. **Nunca**: contenido descifrado, embeddings,
`record_hash`, email crudo (se usa el UUID opaco; PII nunca). **Cero**
analytics de terceros cloud. Las únicas fuentes de "contenido" inspeccionables
son las columnas JSONB en claro por diseño (`episodic_memory.topics`,
`procedural_memory.value`).

### D6 — Buy vs build: build de producto+audit, build de infra-obs adentro

- **Producto/negocio + audit log**: app propia (`apps/admin`). Viven en
  Postgres propio, necesitan identidad de marca y respetan el perímetro.
- **Observabilidad de infra (latencia/tokens/costo/errores/GPU/Celery)**: se
  decide **construirla dentro de `apps/admin`** con toda la data persistida y
  prolija, en vez de embeber herramientas externas. Requiere instrumentación y
  persistencia nuevas (ver D8/F2). Como mitigación de costo, las **fuentes de
  datos** pueden apoyarse en estándares (exporters Prometheus, métricas de
  Celery) aunque la UI sea propia.

### D7 — Control plane sobre el serving (objetivo de fase tardía)

El admin será también un **control plane**: modo de bajo rendimiento,
selección de modelos más baratos y portabilidad operativa a otra máquina
(operar las IAs desde el panel). Hoy el serving se elige por env **al
arrancar** (`LLM_BACKEND`/`LLM_SERVING`, estático — ADR-013/014); el switch en
runtime requiere una API de control y que el router LLM soporte reconfig en
caliente.

Este ADR **registra la intención y el alcance** del control plane, pero el
**contrato concreto** del control de serving (mecanismo de reconfig, formato,
seguridad de las mutaciones) se define en un ADR posterior que refine
ADR-013/014, y su implementación cae bajo el gate de **regla #1** (toca
`ynara.config.json`/serving). No se implementa control plane sin ese ADR.

### D8 — Roadmap por fases (secuencia el riesgo)

- **F0 — Habilitadores**: migración `is_admin` (+ seed `ADMIN_BOOTSTRAP_IDS`),
  dependencia `require_admin`, tabla `admin_audit`, scaffold de `apps/admin`
  (shell con auth admin + layout editorial con tokens de `DESIGN.md`).
- **F1 — Ops + Negocio (data que ya existe)**: endpoints `/v1/admin/*` de D4 y
  su UI: overview, mix de modos (con el tint oficial de cada modo), salud del
  moat, audit log, badge "perímetro intacto", health, heatmap de uso derivado
  de `sessions.started_at`. Índices nuevos si la performance lo pide
  (`sessions.started_at`, `sessions.mode`, `users.created_at`).
- **F2 — Instrumentación + observabilidad de infra**: persistir los gaps
  (tabla de métricas por request con latencia/tokens/status/model/mode;
  sampleo de GPU; tracking de jobs Celery; `auth_events`;
  `users.last_active_at`) + UI completa de latencia/tokens/costo/errores.
- **F3 — Control plane**: D7, con su ADR de refinamiento y gate de regla #1.

El detalle táctil de cada fase (orden de PRs, pantallas para demo) vive como
plan de trabajo aparte, no en este ADR. F1 cubre ops + negocio juntos.

### D9 — Real-time vs polling

Polling con TanStack Query (refetch 60–300s para métricas de negocio, <30s
para health). Sin WebSocket en MVP. Cada widget con indicador de frescura
("actualizado hace 42s") y opción de pausar/snapshot para que los datos no
cambien mientras el operador lee.

## Consecuencias positivas

- El equipo gana por primera vez visibilidad y control operativo, con un
  quick-win barato en F1 (audit log + health ya tienen la data lista).
- Un solo eje de autorización admin sirve a ops y founders; construido una vez.
- Identidad de marca: charts con el tint de cada modo, "salud del moat" como
  North Star, audit log soberano como hero feature, badge de perímetro
  intacto. No es "otro Retool".
- Respeta las reglas duras: read-only sobre tablas sagradas, cero PII/contenido
  expuesto, cero analytics de terceros, todo vía FastAPI.
- Coherente con [ADR-001](./ADR-001-monorepo-vs-multirepo.md) (app nueva como
  superficie del monorepo) y con la separación apps/packages.

## Consecuencias negativas

- F2 (observabilidad de infra construida adentro) es **mucho** backend nuevo:
  instrumentación por request, persistencia de métricas, sampleo de GPU,
  tracking de Celery. Se re-implementa parte de lo que Grafana/Prometheus dan
  de fábrica; el costo de mantenimiento queda del lado del equipo.
- El control plane (F3) introduce mutación de configuración de serving en
  runtime: superficie de riesgo nueva (un cambio mal hecho degrada o tumba el
  serving) que obliga a auditar cada acción y a un ADR adicional.
- Otra app en el grafo de Turborepo: `exports`, `tsconfig`, lugar en
  `pnpm-workspace.yaml`, y un pipeline de CI/deploy propio.
- Migraciones nuevas sobre `users` (operativa) y tablas nuevas: aunque no
  tocan tablas sagradas, suman superficie de esquema.

## Mitigaciones

- **Fail-closed** en `require_admin` y subdominio aislado: la superficie admin
  no se expone junto al portal de cliente.
- **`admin_audit` desde el día 1**: ninguna acción de operador queda sin
  rastro (después es tarde para agregarlo).
- **Frontera de privacidad mecánica**: los schemas de respuesta admin (Zod/
  Pydantic) **no incluyen** campos sensibles (`record_hash`, contenido, email),
  así un leak por descuido rompe el contrato, no pasa silencioso.
- **F2 apoyada en estándares**: aunque la UI sea propia, las fuentes pueden ser
  exporters Prometheus / métricas de Celery, evitando reinventar la recolección.
- **Control plane detrás de su propio ADR + gate regla #1**: no se toca serving
  sin la decisión escrita y la aprobación humana explícita.

## Alternativas descartadas

- **Nombre `apps/dashboard`**: el research de UX marca "dashboard confundido
  con admin panel" como antipatrón; sugiere solo-lectura y no comunica las
  acciones de operador (suspender, revocar, controlar serving). `apps/console`
  queda como segunda opción válida; `apps/ops` se descarta por angosto (deja
  afuera la vista de negocio de founders).
- **Rol admin como enum `role` desde el inicio**: RBAC granular es over-
  engineering para 3 founders hoy; `is_admin` cubre el caso y evoluciona a
  `role` sin rehacer.
- **Rol admin como lista en `.env` (como modelo)**: no escala (redeploy para
  agregar un admin), no es auditable y mezcla config con dato. Se usa solo como
  **bootstrap seed**, no como fuente de verdad.
- **Meter el panel del end-user en esta app**: duplicaría auth y rompería el
  modelo mono-tenant; esa capacidad ya existe en la API y va en `apps/web`.
- **Buy para la capa de producto/audit (Retool/Forest/Metabase cloud)**: o
  saca dato del perímetro (prohibido por regla #4) o requiere self-host sin
  aportar la identidad de marca que se busca; para producto+audit la app propia
  gana claro.
- **Analytics de terceros cloud (PostHog/Amplitude/Mixpanel)**: prohibido por
  soberanía (regla #4). Solo self-hosted sería admisible, e innecesario en MVP.
- **Embeber Grafana self-hosted para la observabilidad de infra**: era la
  recomendación de menor esfuerzo (no reinventar Grafana), pero se descarta a
  favor de construir adentro (D6) para tener toda la data unificada y prolija
  en una sola superficie y habilitar el control plane integrado (D7). El
  trade-off de costo queda registrado en Consecuencias negativas.

## Relación con otros ADRs

- **Se apoya en** [ADR-001](./ADR-001-monorepo-vs-multirepo.md) (estructura del
  monorepo, app como superficie) y [ADR-016](./ADR-016-mobile-codigo-compartido-packages-core.md)
  (criterio para introducir una superficie nueva).
- **Reusa** [ADR-011](./ADR-011-auth-layering-criterion.md) y
  [ADR-015](./ADR-015-auth-deps-pyjwt-bcrypt.md) (maquinaria JWT/blocklist para
  `require_admin`).
- **Respeta** [ADR-007](./ADR-007-memory-decay-retention-encryption.md)
  (cifrado per-user, retention) y [ADR-010](./ADR-010-memory-architecture-v2.md)
  (arquitectura de memoria) como frontera de lo observable.
- **Anticipa un refinamiento de** [ADR-013](./ADR-013-serving-endpoints-config.md)/
  [ADR-014](./ADR-014-serving-ollama-gguf-16gb.md) para el contrato del control
  plane de serving (D7), pendiente de ADR propio.
