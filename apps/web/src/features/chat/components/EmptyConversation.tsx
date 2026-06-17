import type { ModeId } from "@/components/ui/modes";
import { CHAT_PROMPTS, MODE_INTRO } from "../constants";

type Props = {
  mode: ModeId;
  /** Callback al hacer click en un prompt sugerido: manda ese texto. */
  onSend: (text: string) => void;
};

/**
 * Estado vacío de una conversación recién creada: saludo + intro del modo
 * (copy en `constants.ts`) + fila horizontal de prompts sugeridos que envían
 * ese texto al hacer click.
 *
 * Pills: teñidas con `color-mix` sobre el tint del modo (sin gradiente —
 * guard `gradient-guard.test.ts`). Scroll horizontal en mobile. Accesibles
 * por teclado (botones nativos, `type="button"`).
 */
export function EmptyConversation({ mode, onSend }: Props) {
  const prompts = CHAT_PROMPTS[mode];

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
      {/* Saludo + intro del modo */}
      <div className="flex flex-col items-center gap-3">
        <h2 className="text-title text-[var(--color-ink-deep)]">Arranquemos.</h2>
        <p className="max-w-[420px] text-body text-[var(--color-ink-soft)]">{MODE_INTRO[mode]}</p>
      </div>

      {/* Prompts sugeridos — fila horizontal scrolleable en mobile */}
      <ul
        className="flex w-full max-w-[640px] list-none gap-2 overflow-x-auto pb-1 scrollbar-none"
        aria-label="Prompts sugeridos"
      >
        {prompts.map((prompt) => (
          <li key={prompt} className="shrink-0">
            <button
              type="button"
              onClick={() => onSend(prompt)}
              className="rounded-[var(--radius-pill)] border px-4 py-2 text-sm transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 active:opacity-70"
              style={{
                borderColor: `color-mix(in srgb, var(--mode-${mode}) 35%, transparent)`,
                backgroundColor: `color-mix(in srgb, var(--mode-${mode}) 10%, transparent)`,
                color: `color-mix(in srgb, var(--mode-${mode}) 70%, var(--color-ink))`,
                outlineColor: `var(--mode-${mode})`,
              }}
            >
              {prompt}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
