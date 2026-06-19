import { z } from "zod";
import { Delta, TimePoint } from "@/features/_shared/schemas";

/**
 * Contrato de `GET /v1/admin/moat?range=` (blueprint §4.4).
 *
 * Pantalla F1.4 (insignia): salud del moat = lo que Ynara recuerda, en 3 capas
 * (semántica / episódica / procedural). Counts + deltas + crecimiento por capa +
 * salud procedural (confidence + stale) + backlog de consolidación.
 *
 * Privacidad (regla #6): SOLO metadata. Nunca se descifra `content`/`summary`;
 * `recentEpisodic` trae id + timestamp + flag de sensible, jamás el texto.
 */

/** Las 3 capas del moat. Reutilizado en counts, deltas y growth. */
export const MoatLayer = z.enum(["semantic", "episodic", "procedural"]);
export type MoatLayerT = z.infer<typeof MoatLayer>;

export const AdminMoatOut = z.object({
  counts: z.object({
    semantic: z.number().int(),
    episodic: z.number().int(),
    procedural: z.number().int(),
  }),
  deltas: z.object({
    semantic: Delta,
    episodic: Delta,
    procedural: Delta,
  }),
  growth: z.array(
    z.object({
      key: MoatLayer,
      points: z.array(TimePoint),
    }),
  ),
  procedural: z.object({
    stale_count: z.number().int(),
    healthy_count: z.number().int(),
    confidence_buckets: z.array(
      z.object({
        range: z.string(),
        count: z.number().int(),
      }),
    ),
  }),
  consolidation: z.object({
    backlog: z.number().int(),
    recent_episodic: z.array(
      z.object({
        id: z.string().uuid(),
        occurred_at: z.string(),
        is_sensitive: z.boolean(),
      }),
    ),
  }),
});

export type AdminMoatOutT = z.infer<typeof AdminMoatOut>;
