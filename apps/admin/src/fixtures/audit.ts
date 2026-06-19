import type { ModeIdT } from "@/features/_shared/schemas";
import {
  AdminAuditPage,
  type AdminAuditPageT,
  type AdminAuditRowT,
  type AuditFilterState,
} from "@/features/audit/schemas";
import { FIXTURE_NOW, minutesBack, mulberry32, pick, seededUuid } from "./seed";

/**
 * Fixture de `GET /v1/admin/audit` (blueprint §4.7).
 *
 * Genera ~200 filas deterministas (mezcla de operations/layers/modes/models,
 * ~18% sensibles) y expone `auditPage(filters, limit, offset)` que filtra y
 * pagina EN MEMORIA — el mismo contrato que el backend hará con WHERE + LIMIT/
 * OFFSET, pero del lado del fixture para que la pantalla de audit sea navegable
 * sin backend.
 *
 * PRIVACIDAD: las filas se construyen contra `AdminAuditRow` (sin `record_hash`,
 * sin `target_id`). Esos campos NO existen ni siquiera en el fixture.
 */

const ROW_COUNT = 200;

const OPERATIONS = ["read", "write", "update", "delete"] as const;
const LAYERS = ["semantic", "episodic", "procedural"] as const;
const MODES: ModeIdT[] = ["productividad", "estudio", "bienestar", "vida", "memoria"];
const MODELS = ["gemma", "qwen"] as const;
const TOOLS = [
  "memory.search",
  "memory.write",
  "memory.consolidate",
  "agenda.read",
  "agenda.write",
  null,
] as const;

/**
 * Las ~200 filas, ordenadas `createdAt` DESC (la fila 0 es la más reciente).
 * Se generan una sola vez (módulo cargado = dataset estable durante la sesión).
 */
function buildRows(now: Date): AdminAuditRowT[] {
  const rand = mulberry32(9001);
  const rows: AdminAuditRowT[] = [];
  for (let i = 0; i < ROW_COUNT; i++) {
    rows.push({
      id: seededUuid(9001 + i),
      // i creciente = más viejo → minutos hacia atrás crecientes → DESC por created_at
      created_at: minutesBack(i * 11 + Math.floor(rand() * 7), now),
      operation: pick(OPERATIONS, Math.floor(rand() * OPERATIONS.length)),
      target_layer: pick(LAYERS, Math.floor(rand() * LAYERS.length)),
      origin_mode: rand() < 0.15 ? null : pick(MODES, Math.floor(rand() * MODES.length)),
      origin_model: rand() < 0.1 ? null : pick(MODELS, Math.floor(rand() * MODELS.length)),
      origin_tool: pick(TOOLS, Math.floor(rand() * TOOLS.length)),
      sensitive: rand() < 0.18,
    });
  }
  return rows;
}

const ALL_ROWS: AdminAuditRowT[] = buildRows(FIXTURE_NOW);

/** Aplica los filtros del cliente (campo `null` = sin filtrar por ese campo). */
function matchesFilters(row: AdminAuditRowT, f: AuditFilterState): boolean {
  if (f.operation && row.operation !== f.operation) return false;
  if (f.targetLayer && row.target_layer !== f.targetLayer) return false;
  if (f.originMode && row.origin_mode !== f.originMode) return false;
  if (f.originModel && row.origin_model !== f.originModel) return false;
  if (f.sensitive !== null && row.sensitive !== f.sensitive) return false;
  return true;
}

/**
 * Filtra + pagina en memoria y devuelve una `AdminAuditPage` parseada por su
 * Zod. `total` es el conteo de la query CON filtros (no la tabla entera), igual
 * que haría el backend; `sensitive_pct` se calcula sobre ese conjunto filtrado.
 */
export function auditPage(
  filters: AuditFilterState,
  limit: number,
  offset: number,
): AdminAuditPageT {
  const filtered = ALL_ROWS.filter((row) => matchesFilters(row, filters));
  const total = filtered.length;
  const sensitiveCount = filtered.filter((r) => r.sensitive).length;
  const sensitive_pct = total === 0 ? 0 : Number(((sensitiveCount / total) * 100).toFixed(1));
  const items = filtered.slice(offset, offset + limit);

  return AdminAuditPage.parse({ items, total, sensitive_pct });
}

/** Dataset completo (read-only) por si una preview lo necesita sin paginar. */
export const allAuditRows: readonly AdminAuditRowT[] = ALL_ROWS;
