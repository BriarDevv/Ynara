# SCREENS.md — Las 6 pantallas del panel

Catálogo de las pantallas de `apps/admin` y de los datos que muestra cada una.
Todas viven bajo `app/(panel)/` y comparten el shell (sidebar + topbar con rango
temporal global + `PerimeterBadge`). El rango (`24h`/`7d`/`30d`/`90d`) vive en el
topbar y se inyecta como query param `range=` en todas las pantallas salvo
System Health.

> Invariante: cada pantalla muestra **agregados** o **metadata exponible**.
> Nunca contenido descifrado, `record_hash`, `target_id` ni PII (reglas #2/#4).
> El contrato de cada endpoint está en [`DATA-CONTRACTS.md`](./DATA-CONTRACTS.md).

---

## F1.1 — Overview · `/` (`(panel)/page.tsx`)

Vista de un vistazo del estado del sistema.

- **StatusHero**: `PerimeterBadge variant="hero"` + estado del perímetro
  (`intact`/`attention`/`verifying`) + `LivingField` ambiental con el rango activo.
- **KpiStrip** (4 KPIs): usuarios totales (+delta), sesiones en rango
  (+sparkline), memorias consolidadas (suma de las 3 capas), eventos de audit en
  rango.
- **AreaTimeSeries**: sesiones/día en el rango.
- **ModeBarChart** compacto: mix de modos + link a `/modos`.
- **AuditPreview**: 6 filas recientes de audit + link a `/audit`.
- **Datos**: `useOverview(range)` → `GET /v1/admin/overview?range=`.

## F1.2 — Usuarios & Actividad · `/usuarios`

Actividad y crecimiento de la base de usuarios.

- **ActivityKpis**: DAU/WAU/MAU, cada uno con sparkline + delta. Rotulado
  **"aprox. por sesiones"** (no hay `last_active_at`; es un proxy honesto).
- **UsageHeatmap**: grid 53×7 estilo GitHub, escala de opacidad de azul
  (`--heat-*`). `note` aclara que es actividad estimada por sesiones.
- **ConversionFunnel**: efímeros vs registrados + % conversión. Rotulado
  **"estimado"** (sin timestamp de conversión).
- **SignupsTable**: signups/día (de `users.created_at`).
- **Datos**: `useUsers(range)` → `GET /v1/admin/users?range=`.

## F1.3 — Modos · `/modos`

Cómo se reparte el uso entre los 5 modos.

- **ModeMix** (`ModeDonut`): mix de sesiones por modo, slices con los fills
  oficiales de modo, centro con el total, leyenda con count/%.
- **ModeDuration** (`ModeBarChart valueFormat="min"`): duración media por modo
  (`ended_at - started_at`), **solo sesiones cerradas**; rotula n cerradas / n
  abiertas.
- **ModeCardStrip**: 5 cards, barra de acento superior con el tint del modo,
  nombre + blurb (de `MODES`) + 2 métricas. Acá cantan los 5 tints oficiales.
- **Datos**: `useModes(range)` → `GET /v1/admin/modes?range=`.

## F1.4 — Salud del Moat · `/moat` (pantalla insignia)

El "moat": lo que Ynara recuerda, en tres capas.

- **MoatHealthHero** ("latido de la memoria"): `LivingField variant="network"`
  como anillos de nodos (externo=semántica, medio=episódica, interno=procedural;
  densidad ∝ count). Centro: total consolidado. Backlog = nodos pulsantes.
- **MoatTower** ×3: skyline de las 3 capas (count + delta + barra proporcional,
  color de capa `--layer-*`).
- **LayerGrowth** (`LineMultiSeries`): crecimiento de las 3 capas en el tiempo.
- **ProceduralHealth** (`ConfidenceHistogram`): distribución de `confidence` +
  % stale (sano=azul, stale=error).
- **ConsolidationHeartbeat**: orbe con `--orb-beat` mapeado al backlog +
  episodics recientes (solo `occurred_at` + flag sensitive, **sin** summary).
- **Datos**: `useMoat(range)` → `GET /v1/admin/moat?range=`. **Nunca descifra
  `content`/`summary` ni expone hash.**

## F1.5 — Audit Log · `/audit` (vista soberana)

El `audit_log` filtrable, respetando el perímetro.

- **AuditFilters** (sticky bajo topbar): `operation`, `target_layer`,
  `origin_mode`, `origin_model` (gemma/qwen), toggle `sensitive`. El rango hereda
  del topbar.
- **AuditTable** + **AuditRow**: tabla editorial (hairlines, header sticky,
  orden `created_at` desc, `tabular-nums` en tiempos). Chips por `operation`,
  badge por `target_layer`, `ModeChip` por `origin_mode`, `Diamond` si
  `sensitive`. **La fila NO incluye `record_hash` ni `target_id`** (omitidos en
  el Zod, no solo en render). Paginación `limit/offset`.
- Banner soberano: *"Vista soberana — sin hash de integridad ni contenido
  descifrado."*
- **Datos**: `useAudit(filters, page, range)` → `GET /v1/admin/audit?...`.

## F1.6 — System Health · `/sistema`

Estado de runtime e infra (sin métricas de negocio, sin `range`).

- **ProdGuardBanner**: lo primero que ve el operador. Guard activo → franja
  calma; DB de prod en dev → franja roja (incidente 2026-05-31).
- **StatusCard** ×2: Postgres (`SELECT 1`) + Redis (PING). Dot de estado
  (**azul plano = OK**, error = down), latencia `tabular-nums`, último check.
- **RuntimeInventory**: config no sensible — modelos LLM (gemma/qwen), los 5
  modos, head de Alembic, embedder/reranker cargados, build version.
- **Datos**: `useSystem()` → `GET /v1/admin/system` (sin `range`).
