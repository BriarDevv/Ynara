import { z } from "zod";
import { ModeId } from "@/features/_shared/schemas";

/**
 * Contrato de `GET /v1/admin/audit?...` (blueprint §4.5).
 *
 * Pantalla F1.5: vista **soberana** del audit log. Tabla filtrable + paginada.
 *
 * PRIVACIDAD DURA (regla #6, "vista soberana"): `AdminAuditRow` **NO incluye**
 * `record_hash` ni `target_id`. No es que la UI no los pinte: están OMITIDOS del
 * schema, así que aunque el backend los mandara, el `.parse()` los descarta y
 * nunca llegan al cliente. El backend además NO debe SELECT-earlos. El hash de
 * integridad y el id del registro tocado no salen del perímetro.
 */

/** Operación auditada. Pinta el chip plano por color en la tabla. */
export const AuditOperation = z.enum(["read", "write", "update", "delete"]);
export type AuditOperationT = z.infer<typeof AuditOperation>;

/** Capa de memoria sobre la que actuó la operación. */
export const AuditTargetLayer = z.enum(["semantic", "episodic", "procedural"]);
export type AuditTargetLayerT = z.infer<typeof AuditTargetLayer>;

/** Modelo LLM de origen del evento. */
export const AuditOriginModel = z.enum(["gemma", "qwen"]);
export type AuditOriginModelT = z.infer<typeof AuditOriginModel>;

/**
 * Fila del audit log — SOLO campos exponibles.
 * Deliberadamente SIN `record_hash` y SIN `target_id`.
 */
export const AdminAuditRow = z.object({
  id: z.string().uuid(),
  created_at: z.string(),
  operation: AuditOperation,
  target_layer: AuditTargetLayer,
  origin_mode: ModeId.nullable(),
  origin_model: AuditOriginModel.nullable(),
  origin_tool: z.string().nullable(),
  sensitive: z.boolean(),
});
export type AdminAuditRowT = z.infer<typeof AdminAuditRow>;

/** Página de resultados: filas + total (para paginación) + % de sensibles. */
export const AdminAuditPage = z.object({
  items: z.array(AdminAuditRow),
  total: z.number().int(),
  sensitive_pct: z.number(),
});
export type AdminAuditPageT = z.infer<typeof AdminAuditPage>;

/**
 * Estado de los filtros de la tabla (cliente). `null`/`"all"` = sin filtrar.
 * No es parte del payload del backend; vive acá porque describe la query que el
 * hook arma hacia `/v1/admin/audit`. Se serializa a query params.
 */
export type AuditFilterState = {
  operation: AuditOperationT | null;
  targetLayer: AuditTargetLayerT | null;
  originMode: z.infer<typeof ModeId> | null;
  originModel: AuditOriginModelT | null;
  sensitive: boolean | null;
};

/** Filtros vacíos (todo en null). Estado inicial de `AuditFilters`. */
export const EMPTY_AUDIT_FILTERS: AuditFilterState = {
  operation: null,
  targetLayer: null,
  originMode: null,
  originModel: null,
  sensitive: null,
};
