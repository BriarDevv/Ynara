# DATA-CONTRACTS.md — Endpoints `/v1/admin/*` + Zod

Contratos de datos del panel. Cada pantalla consume un endpoint `/v1/admin/*`
del backend FastAPI y valida la respuesta con un Zod schema antes de renderizar.

## Convenciones

- **Auth**: todos requieren `Authorization: Bearer <jwt admin>` + gate
  `require_admin` en el backend (carga `User`, chequea `is_admin`).
- **Range**: query `range ∈ {24h,7d,30d,90d}` (default `7d`) en todas salvo
  `/system`.
- **Validación cliente**: `Schema.parse(await api.get<unknown>(...))` en el hook
  de cada feature. El `parse` es el **gate de privacidad**: el Zod omite todo lo
  no exponible (ver nota abajo).
- **Fechas**: ISO 8601 UTC.

> ⚠️ **Nota de privacidad (reglas #2/#4 + #3).** Estos contratos exponen
> **agregados** (`COUNT`/`GROUP BY`) y **metadata exponible**. **Nunca**:
> contenido descifrado de memoria (`content`/`summary`), `record_hash`,
> `target_id`, mensajes, emails ni otra PII. Las omisiones se hacen en el **Zod
> schema** (no solo en el render) — si el backend devolviera un campo sensible,
> el schema no lo parsea y por lo tanto no llega a la UI. El backend, a su vez,
> hace `SELECT` solo de las columnas exponibles y **nunca descifra** memoria.

---

## Tipos base (comunes)

```ts
import { z } from "zod";
export const ModeId = z.enum(["productividad","estudio","bienestar","vida","memoria"]);
export const RangeId = z.enum(["24h","7d","30d","90d"]);
export const Delta = z.object({ pct: z.number(), direction: z.enum(["up","down","flat"]) });
export const TimePoint = z.object({ date: z.string(), value: z.number().int().nonnegative() });
```

---

## `GET /v1/admin/overview?range=7d`

```ts
export const AdminOverviewOut = z.object({
  perimeter: z.object({
    status: z.enum(["intact","attention","verifying"]),
    detail: z.string().nullable(),
    checkedAt: z.string(),
  }),
  kpis: z.object({
    usersTotal:  z.object({ value: z.number().int(), delta: Delta }),
    sessions:    z.object({ value: z.number().int(), delta: Delta, spark: z.array(z.number()) }),
    memories:    z.object({ value: z.number().int(), delta: Delta }), // suma de las 3 capas
    auditEvents: z.object({ value: z.number().int(), delta: Delta }),
  }),
  sessionsSeries: z.array(TimePoint),
  modeMix: z.array(z.object({ mode: ModeId, value: z.number().int() })),
  auditPreview: z.array(z.object({
    id: z.string().uuid(), createdAt: z.string(),
    operation: z.enum(["read","write","update","delete"]),
    targetLayer: z.enum(["semantic","episodic","procedural"]),
    originMode: ModeId.nullable(), sensitive: z.boolean(),
  })),
});
```

Backend: COUNT users; COUNT/serie de sessions por ventana; COUNT 3 capas; COUNT
audit en ventana (+ GROUP BY mode; LIMIT 6 desc para preview).

## `GET /v1/admin/users?range=7d`

```ts
export const AdminUsersOut = z.object({
  activity: z.object({
    dau: z.object({ value: z.number().int(), delta: Delta, spark: z.array(z.number()) }),
    wau: z.object({ value: z.number().int(), delta: Delta, spark: z.array(z.number()) }),
    mau: z.object({ value: z.number().int(), delta: Delta, spark: z.array(z.number()) }),
    isApproximate: z.literal(true), // proxy por sesiones (no hay last_active_at)
  }),
  heatmap: z.array(z.object({
    date: z.string(), count: z.number().int().nonnegative(),
    level: z.number().int().min(0).max(5),
  })),
  conversion: z.object({
    ephemeral: z.number().int(), registered: z.number().int(),
    conversionPct: z.number(), isEstimate: z.literal(true),
  }),
  signups: z.array(z.object({ date: z.string(), count: z.number().int() })),
});
```

Backend: DAU/WAU/MAU = `COUNT(DISTINCT user_id)` sobre `sessions.started_at`
(rotulado approximate); heatmap = sesiones/día últimas 53 sem; conversion =
COUNT `is_ephemeral`; signups = COUNT `users.created_at`/día.

## `GET /v1/admin/modes?range=7d`

```ts
export const AdminModesOut = z.object({
  total: z.number().int(),
  mix: z.array(z.object({ mode: ModeId, sessions: z.number().int(), pct: z.number() })),
  duration: z.array(z.object({
    mode: ModeId, avgMinutes: z.number(),
    closedSessions: z.number().int(), openSessions: z.number().int(),
  })),
});
```

Backend: GROUP BY `sessions.mode`; duración = `AVG(ended_at - started_at)` WHERE
`ended_at IS NOT NULL`, abiertas contadas aparte.

## `GET /v1/admin/moat?range=7d`

```ts
export const AdminMoatOut = z.object({
  counts: z.object({ semantic: z.number().int(), episodic: z.number().int(), procedural: z.number().int() }),
  deltas: z.object({ semantic: Delta, episodic: Delta, procedural: Delta }),
  growth: z.array(z.object({
    key: z.enum(["semantic","episodic","procedural"]), points: z.array(TimePoint),
  })),
  procedural: z.object({
    staleCount: z.number().int(), healthyCount: z.number().int(),
    confidenceBuckets: z.array(z.object({ range: z.string(), count: z.number().int() })),
  }),
  consolidation: z.object({
    backlog: z.number().int(),
    recentEpisodic: z.array(z.object({
      id: z.string().uuid(), occurredAt: z.string(), isSensitive: z.boolean(),
    })), // SOLO metadata: sin summary ni content
  }),
});
```

Backend: COUNT por tabla de memoria (**NUNCA** descifra `content`/`summary`);
growth = COUNT por `created_at`/día por capa; procedural = COUNT `stale` +
histograma de `confidence`; backlog = sesiones cerradas sin episodic
consolidado; recentEpisodic = LIMIT por `occurred_at`, solo metadata.

## `GET /v1/admin/audit?range=7d&operation=&targetLayer=&originMode=&originModel=&sensitive=&limit=50&offset=0`

```ts
export const AdminAuditRow = z.object({
  // ⚠️ SIN record_hash, SIN target_id — omitidos en el schema, no solo en render
  id: z.string().uuid(),
  createdAt: z.string(),
  operation: z.enum(["read","write","update","delete"]),
  targetLayer: z.enum(["semantic","episodic","procedural"]),
  originMode: ModeId.nullable(),
  originModel: z.enum(["gemma","qwen"]).nullable(),
  originTool: z.string().nullable(),
  sensitive: z.boolean(),
});
export const AdminAuditPage = z.object({
  items: z.array(AdminAuditRow),
  total: z.number().int(),
  sensitivePct: z.number(),
});
```

Backend: `SELECT` de los campos exponibles de `audit_log` WHERE filtros, ORDER
BY `created_at` DESC, LIMIT/OFFSET. **El `SELECT` no incluye `record_hash` ni
`target_id`.** `audit_log` es tabla sagrada (regla #3): el panel es read-only.

## `GET /v1/admin/system`

```ts
export const AdminSystemOut = z.object({
  guard: z.object({ active: z.boolean(), dbTarget: z.string(), isProdInDev: z.boolean() }),
  services: z.object({
    postgres: z.object({ up: z.boolean(), latencyMs: z.number(), detail: z.string(), checkedAt: z.string() }),
    redis:    z.object({ up: z.boolean(), latencyMs: z.number(), detail: z.string(), checkedAt: z.string() }),
  }),
  runtime: z.object({
    models: z.array(z.string()), modes: z.array(z.string()),
    schemaHead: z.string(), embedder: z.string(), reranker: z.string(), buildVersion: z.string(),
  }),
});
```

Backend: `SELECT 1` (Postgres+pgvector), PING Redis (`app.state.redis`), guard
`db_guard.guard_against_prod_db_in_dev`, modos del enum `Mode`, head de Alembic,
singletons embedder/reranker. Sin queries de negocio, sin `range`.

---

## Dev sin backend (MSW)

En dev (`NEXT_PUBLIC_ENABLE_MOCKS=true`), `fixtures/handlers.ts` sirve estos
endpoints con datos deterministas (`fixtures/seed.ts` + un fixture por pantalla).
Cada handler devuelve el fixture **parseado por su propio Zod**, así el fixture
queda garantizado contra el contrato (y contra la nota de privacidad). El test
`admin-schemas.test.ts` parsea todos los fixtures con sus schemas en CI.
