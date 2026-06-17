"use client";

import { useState } from "react";
import { Sheet } from "@/components/ui/Sheet";
import { Textarea } from "@/components/ui/Textarea";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { useActiveMode } from "@/hooks/useActiveMode";

type MoodId = "tranquilo" | "ocupado" | "estresado" | "cansado" | "energia";

type Mood = { id: MoodId; label: string };

const MOODS: Mood[] = [
  { id: "tranquilo", label: "Tranquilo" },
  { id: "ocupado", label: "Ocupado" },
  { id: "estresado", label: "Estresado" },
  { id: "cansado", label: "Cansado" },
  { id: "energia", label: "Con energía" },
];

type Props = {
  open: boolean;
  onClose: () => void;
};

/**
 * Sheet de check-in matinal (wireframe 14 / build-plan §3): mood 5 opciones,
 * slider de energía 0-10, nota opcional. Estado local — sin backend por ahora.
 */
export function CheckinSheet({ open, onClose }: Props) {
  const activeMode = useActiveMode();
  const [mood, setMood] = useState<MoodId | null>(null);
  const [energy, setEnergy] = useState(6);
  const [note, setNote] = useState("");

  function handleClose() {
    onClose();
  }

  return (
    <Sheet open={open} onClose={handleClose} title="Check-in matinal" titleHidden>
      <div className="flex flex-col gap-6">
        {/* Header: orbe + saludo */}
        <div className="flex items-center gap-3.5">
          <YnaraOrb size={42} modeId={activeMode} thinking />
          <div className="min-w-0">
            <h2 className="text-[1.3rem] font-semibold leading-[1.08] tracking-tight text-[var(--color-ink)]">
              ¿Cómo arrancás el día?
            </h2>
            <p className="mt-0.5 text-[13px] leading-snug text-[var(--color-ink-soft)]">
              Un check-in rápido para arrancar bien.
            </p>
          </div>
        </div>

        {/* Mood */}
        <fieldset className="flex flex-col gap-3 border-none p-0">
          <legend className="mb-1 text-[11px] font-bold uppercase tracking-[.14em] text-[var(--color-ink-faint)]">
            Mood
          </legend>
          <div className="flex justify-between gap-2">
            {MOODS.map((m) => {
              const selected = mood === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setMood(m.id)}
                  className="flex flex-1 flex-col items-center gap-2 rounded-[var(--radius-md)] border px-1 py-3 text-center transition-[border-color,background-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-soft)]"
                  style={
                    selected
                      ? {
                          borderColor: "var(--color-blue-flat)",
                          backgroundColor: "var(--color-bg-soft)",
                          boxShadow: "0 0 0 2px inset var(--color-blue-flat)",
                        }
                      : {
                          borderColor: "var(--color-border)",
                          backgroundColor: "var(--color-bg)",
                        }
                  }
                >
                  {/* Diamante visual de estado */}
                  <span
                    aria-hidden
                    className="inline-block rotate-45 transition-all duration-[var(--duration-base)]"
                    style={{
                      width: selected ? 16 : 12,
                      height: selected ? 16 : 12,
                      borderRadius: 3,
                      backgroundColor: selected
                        ? "var(--color-blue-flat)"
                        : "var(--color-border-strong)",
                    }}
                  />
                  <span
                    className="text-[10.5px] font-semibold leading-tight"
                    style={{
                      color: selected ? "var(--color-ink-deep)" : "var(--color-ink-faint)",
                    }}
                  >
                    {m.label}
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Energía */}
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between px-0.5">
            <span className="text-[11px] font-bold uppercase tracking-[.14em] text-[var(--color-ink-faint)]">
              Energía
            </span>
            <span className="text-[16px] font-semibold text-[var(--color-blue-flat)]">
              {energy} <span className="text-[13px] text-[var(--color-ink-faint)]">/ 10</span>
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={10}
            value={energy}
            onChange={(e) => setEnergy(Number(e.target.value))}
            aria-label="Nivel de energía"
            aria-valuenow={energy}
            aria-valuemin={0}
            aria-valuemax={10}
            className="w-full accent-[var(--color-blue-flat)]"
          />
        </div>

        {/* Nota opcional */}
        <Textarea
          label="Nota rápida (opcional)"
          placeholder="¿Algo en la cabeza esta mañana?"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />

        <button
          type="button"
          onClick={handleClose}
          className="text-button w-full rounded-[var(--radius-md)] bg-[var(--color-blue-flat)] px-6 py-3 text-[var(--color-on-dark)] shadow-soft transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-blue-flat-hover)] active:bg-[var(--color-blue-flat-active)]"
        >
          Listo
        </button>
      </div>
    </Sheet>
  );
}
