"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { ModeId } from "@/components/ui/modes";
import { MODE_BY_ID, MODES } from "@/components/ui/modes";
import { Sheet } from "@/components/ui/Sheet";
import { TextField } from "@/components/ui/TextField";
import { useCreateEvent } from "../api";

type Props = {
  /** Tono AA-safe del modo activo (fill) para el FAB con el "+" blanco. */
  fillVar: string;
  /** Modo activo de la pantalla: preselecciona el selector de modo del Sheet. */
  activeMode: ModeId;
};

/**
 * FAB redondo "+" fijo en la esquina inferior derecha + Sheet de creación
 * rápida de eventos (título + fecha/hora + duración + modo).
 *
 * El FAB se tiñe con el modo activo de la pantalla. El Sheet usa `useCreateEvent`
 * y cierra al crear exitosamente.
 */
export function EventFab({ fillVar, activeMode }: Props) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [startAt, setStartAt] = useState(() => {
    // Valor inicial: ahora redondeado a la hora siguiente
    const d = new Date();
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() + 1);
    // datetime-local interpreta el string como hora LOCAL; compensamos el
    // offset antes de serializar para no correr la hora por timezone.
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });
  const [durationMin, setDurationMin] = useState("60");
  const [modeId, setModeId] = useState<ModeId>(activeMode);
  const [error, setError] = useState<string | null>(null);

  const { mutateAsync, isPending } = useCreateEvent();
  const titleRef = useRef<HTMLInputElement>(null);

  function handleOpen() {
    setError(null);
    setOpen(true);
  }

  function handleClose() {
    setOpen(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("El título es obligatorio.");
      titleRef.current?.focus();
      return;
    }
    const dur = Number(durationMin);
    if (!Number.isFinite(dur) || dur <= 0) {
      setError("La duración debe ser un número positivo.");
      return;
    }
    setError(null);
    try {
      await mutateAsync({
        title: title.trim(),
        start_at: new Date(startAt).toISOString(),
        duration_min: dur,
        mode: modeId,
      });
      // Limpiar y cerrar
      setTitle("");
      setDurationMin("60");
      setModeId(activeMode);
      setOpen(false);
    } catch {
      setError("No pudimos crear el evento. Intentá de nuevo.");
    }
  }

  return (
    <>
      {/* FAB */}
      <button
        type="button"
        aria-label="Crear evento"
        onClick={handleOpen}
        className="fixed bottom-6 right-6 z-20 flex h-12 w-12 items-center justify-center rounded-full text-[var(--color-on-dark)] shadow-[0_8px_20px_-8px_var(--color-accent)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)] active:scale-95 md:bottom-8 md:right-8"
        style={{ backgroundColor: fillVar }}
      >
        <span aria-hidden className="text-2xl font-light leading-none">
          +
        </span>
      </button>

      {/* Sheet de creación */}
      <Sheet open={open} onClose={handleClose} title="Nuevo evento">
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <TextField
            ref={titleRef}
            label="Título"
            placeholder="Ej: Reunión con cátedra"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            autoFocus
          />

          <TextField
            label="Fecha y hora"
            type="datetime-local"
            value={startAt}
            onChange={(e) => setStartAt(e.target.value)}
            required
          />

          <TextField
            label="Duración (minutos)"
            type="number"
            min="1"
            step="5"
            value={durationMin}
            onChange={(e) => setDurationMin(e.target.value)}
            required
          />

          {/* Selector de modo */}
          <div className="flex flex-col gap-1.5">
            <span className="text-caption text-[var(--color-ink-soft)]">Modo</span>
            <div className="flex flex-wrap gap-2">
              {MODES.map((m) => {
                const selected = m.id === modeId;
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setModeId(m.id as ModeId)}
                    className="text-caption rounded-[var(--radius-pill)] border px-3 py-1 transition-colors duration-[var(--duration-fast)]"
                    style={
                      selected
                        ? {
                            backgroundColor: `color-mix(in srgb, ${MODE_BY_ID[m.id].tintVar} 20%, var(--color-bg))`,
                            borderColor: MODE_BY_ID[m.id].tintVar,
                            color: "var(--color-ink)",
                          }
                        : {
                            borderColor: "var(--color-border)",
                            color: "var(--color-ink-soft)",
                          }
                    }
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>

          {error ? (
            <p role="alert" className="text-body-sm text-[var(--color-error)]">
              {error}
            </p>
          ) : null}

          <div className="flex gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={handleClose} className="flex-1">
              Cancelar
            </Button>
            <Button variant="primary" type="submit" disabled={isPending} className="flex-1">
              {isPending ? "Creando…" : "Crear"}
            </Button>
          </div>
        </form>
      </Sheet>
    </>
  );
}
