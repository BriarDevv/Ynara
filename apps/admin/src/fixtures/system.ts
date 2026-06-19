import { AdminSystemOut, type AdminSystemOutT } from "@/features/system/schemas";
import { FIXTURE_NOW, minutesBack } from "./seed";

/**
 * Fixture de `GET /v1/admin/system` (blueprint §4.7).
 *
 * guard active=true / isProdInDev=false (estado sano: dev apunta a la DB de dev),
 * Postgres up 3.2ms, Redis up 0.8ms, runtime con modelos gemma/qwen, 5 modos,
 * schema head Alembic, embedder/reranker cargados, buildVersion.
 *
 * No lleva `range`: es runtime/config, una sola foto.
 */

export function systemFixture(now: Date = FIXTURE_NOW): AdminSystemOutT {
  const data: AdminSystemOutT = {
    guard: {
      active: true,
      db_target: "ynara_dev@localhost:5432",
      is_prod_in_dev: false,
    },
    services: {
      postgres: {
        up: true,
        latency_ms: 3.2,
        detail: "SELECT 1 · pgvector OK",
        checked_at: minutesBack(0, now),
      },
      redis: {
        up: true,
        latency_ms: 0.8,
        detail: "PING → PONG",
        checked_at: minutesBack(0, now),
      },
    },
    runtime: {
      models: ["gemma", "qwen"],
      modes: ["productividad", "estudio", "bienestar", "vida", "memoria"],
      schema_head: "20260615_0200",
      embedder: "bge-m3 (1024d)",
      reranker: "bge-reranker-v2-m3",
      build_version: "admin@0.1.0",
    },
  };

  return AdminSystemOut.parse(data);
}
