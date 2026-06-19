import { HttpResponse, http } from "msw";
import { ModeId, RangeId } from "@/features/_shared/schemas";
import {
  type AuditFilterState,
  AuditOperation,
  AuditOriginModel,
  AuditTargetLayer,
  EMPTY_AUDIT_FILTERS,
} from "@/features/audit/schemas";
import { env } from "@/lib/env";
import type { RangeId as RangeIdStore } from "@/stores/range";
import { auditPage } from "./audit";
import { moatFixture } from "./moat";
import { modesFixture } from "./modes";
import { overviewFixture } from "./overview";
import { systemFixture } from "./system";
import { usersFixture } from "./users";

/**
 * Handlers MSW de `/v1/admin/*` (blueprint §4.7 + §6 paso 8).
 *
 * Cada handler lee los query params (`range`, filtros de audit, `limit`/`offset`)
 * y devuelve el fixture **ya parseado por su Zod** (el parse vive dentro de cada
 * `*Fixture`/`auditPage`). Así el handler es la última garantía de que lo que
 * sale por la red cumple el contrato que el hook va a re-parsear.
 *
 * El panel desarrolla 100% sobre estos handlers hasta que existan los endpoints
 * reales; el gate de activación (solo dev + `NEXT_PUBLIC_ENABLE_MOCKS`) está en
 * `lib/env.ts#shouldEnableMocks` y se respeta en `app/providers.tsx`.
 */

const apiUrl = (path: string) => `${env.NEXT_PUBLIC_API_URL}${path}`;

/** Lee `range` de la URL; cae a `7d` (default del panel) si falta o es inválido. */
function readRange(url: URL): RangeIdStore {
  const raw = url.searchParams.get("range");
  const parsed = RangeId.safeParse(raw);
  return parsed.success ? (parsed.data as RangeIdStore) : "7d";
}

/** Entero de query param con default y piso (evita `limit=0`/negativos raros). */
function readInt(url: URL, key: string, fallback: number, min = 0): number {
  const raw = url.searchParams.get(key);
  if (raw === null) return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n >= min ? n : fallback;
}

/** Reconstruye `AuditFilterState` desde los query params (cada uno opcional). */
function readAuditFilters(url: URL): AuditFilterState {
  const sp = url.searchParams;
  const op = AuditOperation.safeParse(sp.get("operation"));
  const layer = AuditTargetLayer.safeParse(sp.get("target_layer"));
  const mode = ModeId.safeParse(sp.get("origin_mode"));
  const model = AuditOriginModel.safeParse(sp.get("origin_model"));
  const sensitiveRaw = sp.get("sensitive");

  return {
    ...EMPTY_AUDIT_FILTERS,
    operation: op.success ? op.data : null,
    targetLayer: layer.success ? layer.data : null,
    originMode: mode.success ? mode.data : null,
    originModel: model.success ? model.data : null,
    sensitive: sensitiveRaw === null ? null : sensitiveRaw === "true",
  };
}

export const adminHandlers = [
  // GET /v1/admin/overview?range=
  http.get(apiUrl("/v1/admin/overview"), ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(overviewFixture(readRange(url)));
  }),

  // GET /v1/admin/users?range=
  http.get(apiUrl("/v1/admin/users"), ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(usersFixture(readRange(url)));
  }),

  // GET /v1/admin/modes?range=
  http.get(apiUrl("/v1/admin/modes"), ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(modesFixture(readRange(url)));
  }),

  // GET /v1/admin/moat?range=
  http.get(apiUrl("/v1/admin/moat"), ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(moatFixture(readRange(url)));
  }),

  // GET /v1/admin/audit?range=&operation=&target_layer=&origin_mode=&origin_model=&sensitive=&limit=&offset=
  http.get(apiUrl("/v1/admin/audit"), ({ request }) => {
    const url = new URL(request.url);
    const filters = readAuditFilters(url);
    const limit = readInt(url, "limit", 50, 1);
    const offset = readInt(url, "offset", 0, 0);
    return HttpResponse.json(auditPage(filters, limit, offset));
  }),

  // GET /v1/admin/system  (sin range: runtime/config)
  http.get(apiUrl("/v1/admin/system"), () => HttpResponse.json(systemFixture())),
];
