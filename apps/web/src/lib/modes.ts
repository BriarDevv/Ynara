/**
 * Lector de modos declarados en `ynara.config.json`.
 *
 * **Fuente de verdad** de "qué modos existen" (IDs y metadata semántica:
 * model, memory layers, tools, tone) es el `ynara.config.json` raíz del
 * monorepo. Este archivo lo parsea con Zod en build/runtime y expone
 * `AVAILABLE_MODES` (orden de declaración) y `MODE_TONE`.
 *
 * NO confundir con `@/components/ui/modes` — ese sólo expone datos
 * visuales (label, blurb, gradientClass) para componentes UI. Si en
 * algún momento divergen los IDs, este archivo es el canónico y
 * `components/ui/modes.ts` debe alinearse.
 *
 * Path relativo al config: `apps/web/src/lib/` → `lib → src → web →
 * apps → root` = 4 niveles arriba.
 */

import { z } from "zod";
import { type Mode, ModeSchema } from "@ynara/shared-schemas";
import config from "../../../../ynara.config.json";

const ConfigModeSchema = z.object({
  model: z.string(),
  memory_layers: z.array(z.string()),
  tools_enabled: z.array(z.string()),
  tone: z.string(),
});

const ConfigSchema = z.object({
  modes: z.record(ModeSchema, ConfigModeSchema),
});

const parsed = ConfigSchema.parse(config);

/** IDs de modos definidos en `ynara.config.json`, en orden de declaración. */
export const AVAILABLE_MODES: readonly Mode[] = Object.keys(parsed.modes) as Mode[];

/** Tono declarado para cada modo (uso futuro: copy adaptativo). */
export const MODE_TONE: Record<Mode, string> = Object.fromEntries(
  Object.entries(parsed.modes).map(([id, def]) => [id, def.tone]),
) as Record<Mode, string>;
