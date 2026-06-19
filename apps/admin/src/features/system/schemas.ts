import { z } from "zod";

/**
 * Contrato de `GET /v1/admin/system` (blueprint §4.6).
 *
 * Pantalla F1.6: System Health. NO lleva `range` (es runtime/config, no
 * negocio): guard anti-prod-en-dev + estado de servicios (Postgres/Redis) +
 * inventario de runtime (modelos, modos, schema head, embedder/reranker).
 *
 * Sin queries de negocio ni datos de usuario: `SELECT 1`, PING Redis, lectura de
 * config. El `guard` es lo primero que ve el operador (banner): si una DB de
 * prod está apuntada en dev, `isProdInDev=true` y el banner se pone en rojo.
 */

/** Salud de un servicio de infra (DB / cache). OK se pinta azul plano, no verde. */
const ServiceStatus = z.object({
  up: z.boolean(),
  latency_ms: z.number(),
  detail: z.string(),
  checked_at: z.string(),
});

export const AdminSystemOut = z.object({
  guard: z.object({
    active: z.boolean(),
    db_target: z.string(),
    is_prod_in_dev: z.boolean(),
  }),
  services: z.object({
    postgres: ServiceStatus,
    redis: ServiceStatus,
  }),
  runtime: z.object({
    models: z.array(z.string()),
    modes: z.array(z.string()),
    schema_head: z.string(),
    embedder: z.string(),
    reranker: z.string(),
    build_version: z.string(),
  }),
});

export type AdminSystemOutT = z.infer<typeof AdminSystemOut>;
