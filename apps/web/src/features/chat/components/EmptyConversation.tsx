import type { ModeId } from "@/components/ui/modes";
import { MODE_INTRO } from "../constants";

/**
 * Estado vacío de una conversación recién creada: saludo + intro del modo
 * (copy en `constants.ts`, tono por modo según `docs/product/MODES.md`).
 */
export function EmptyConversation({ mode }: { mode: ModeId }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
      <p className="text-subtitle text-[var(--color-ink)]">Arranquemos.</p>
      <p className="max-w-[420px] text-body text-[var(--color-ink-soft)]">{MODE_INTRO[mode]}</p>
    </div>
  );
}
