"use client";

import type { FormEvent } from "react";
import { useReducer, useState } from "react";
import { Button } from "@/components/ui/Button";
import { MODE_BY_ID, MODES, type ModeId } from "@/components/ui/modes";
import { Sheet } from "@/components/ui/Sheet";
import { TextField } from "@/components/ui/TextField";
import { type AgendaEvent, useDeleteEvent, usePatchEvent } from "../api";

/** ISO con offset → string `datetime-local` en hora local (sin offset). */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

const STATUSES = [
  { value: "confirmed", label: "Confirmado" },
  { value: "tentative", label: "Tentativo" },
  { value: "cancelled", label: "Cancelado" },
] as const;

/** Campos editables del form, agrupados en un solo estado (useReducer). */
type FormState = {
  title: string;
  startAt: string;
  durationMin: string;
  modeId: ModeId | null;
  status: AgendaEvent["status"];
  location: string;
};

/** Estado inicial derivado del evento. Como `EditForm` se remonta keyeado por
 *  `event.id`, esto se recomputa fresco al cambiar de evento (sin staleness). */
function initFormState(event: AgendaEvent): FormState {
  return {
    title: event.title,
    startAt: toLocalInput(event.start_at),
    durationMin: String(event.duration_min),
    modeId: event.mode,
    status: event.status,
    location: event.location ?? "",
  };
}

/** Patch parcial de un solo campo del form (un cambio por interacción). */
type FormAction = { [K in keyof FormState]: { field: K; value: FormState[K] } }[keyof FormState];

function formReducer(state: FormState, action: FormAction): FormState {
  return { ...state, [action.field]: action.value };
}

type Props = {
  /** Evento en edición; `null` mantiene el sheet cerrado. */
  event: AgendaEvent | null;
  onClose: () => void;
};

/**
 * Sheet de **edición** de un evento (tap-para-editar). Reusa el `Sheet` + form
 * del create del FAB, pero con `usePatchEvent`/`useDeleteEvent`. El form vive en
 * un sub-componente keyeado por `event.id` para reinicializar sus campos al
 * cambiar de evento; los hooks de mutación sólo montan cuando hay evento abierto.
 */
export function EventEditSheet({ event, onClose }: Props) {
  return (
    <Sheet open={event !== null} onClose={onClose} title="Editar evento">
      {event ? <EditForm key={event.id} event={event} onClose={onClose} /> : null}
    </Sheet>
  );
}

function EditForm({ event, onClose }: { event: AgendaEvent; onClose: () => void }) {
  // Campos del form en un solo reducer (un cambio por interacción no abanica en
  // renders separados). Derivado de `event` vía initializer; el remount keyeado
  // por `event.id` en el padre lo recomputa fresco al cambiar de evento.
  const [form, dispatch] = useReducer(formReducer, event, initFormState);
  const { title, startAt, durationMin, modeId, status, location } = form;
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const patch = usePatchEvent(event.id);
  const del = useDeleteEvent(event.id);
  const busy = patch.isPending || del.isPending;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("El título es obligatorio.");
      return;
    }
    const dur = Number(durationMin);
    if (!Number.isFinite(dur) || dur <= 0) {
      setError("La duración debe ser un número positivo.");
      return;
    }
    setError(null);
    try {
      await patch.mutateAsync({
        title: title.trim(),
        start_at: new Date(startAt).toISOString(),
        duration_min: dur,
        mode: modeId,
        status,
        location: location.trim() || null,
      });
      onClose();
    } catch {
      setError("No pudimos guardar los cambios. Intentá de nuevo.");
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await del.mutateAsync();
      onClose();
    } catch {
      setError("No pudimos eliminar el evento. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <TextField
        label="Título"
        value={title}
        onChange={(e) => dispatch({ field: "title", value: e.target.value })}
        required
        autoFocus
      />

      <TextField
        label="Fecha y hora"
        type="datetime-local"
        value={startAt}
        onChange={(e) => dispatch({ field: "startAt", value: e.target.value })}
        required
      />

      <TextField
        label="Duración (minutos)"
        type="number"
        min="1"
        step="5"
        value={durationMin}
        onChange={(e) => dispatch({ field: "durationMin", value: e.target.value })}
        required
      />

      <TextField
        label="Lugar (opcional)"
        value={location}
        onChange={(e) => dispatch({ field: "location", value: e.target.value })}
      />

      {/* Selector de modo (incluye "Sin modo" para `null`) */}
      <fieldset className="flex flex-col gap-1.5 border-none p-0">
        <legend className="text-caption text-[var(--color-ink-soft)]">Modo</legend>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-pressed={modeId === null}
            onClick={() => dispatch({ field: "modeId", value: null })}
            className="text-caption rounded-[var(--radius-pill)] border px-3 py-1 transition-colors duration-[var(--duration-fast)]"
            style={
              modeId === null
                ? { borderColor: "var(--color-ink)", color: "var(--color-ink)" }
                : { borderColor: "var(--color-border)", color: "var(--color-ink-soft)" }
            }
          >
            Sin modo
          </button>
          {MODES.map((m) => {
            const selected = m.id === modeId;
            return (
              <button
                key={m.id}
                type="button"
                aria-pressed={selected}
                onClick={() => dispatch({ field: "modeId", value: m.id })}
                className="text-caption rounded-[var(--radius-pill)] border px-3 py-1 transition-colors duration-[var(--duration-fast)]"
                style={
                  selected
                    ? {
                        backgroundColor: `color-mix(in srgb, ${MODE_BY_ID[m.id].tintVar} 20%, var(--color-bg))`,
                        borderColor: MODE_BY_ID[m.id].tintVar,
                        color: "var(--color-ink)",
                      }
                    : { borderColor: "var(--color-border)", color: "var(--color-ink-soft)" }
                }
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Selector de estado */}
      <fieldset className="flex flex-col gap-1.5 border-none p-0">
        <legend className="text-caption text-[var(--color-ink-soft)]">Estado</legend>
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((s) => {
            const selected = s.value === status;
            return (
              <button
                key={s.value}
                type="button"
                aria-pressed={selected}
                onClick={() => dispatch({ field: "status", value: s.value })}
                className="text-caption rounded-[var(--radius-pill)] border px-3 py-1 transition-colors duration-[var(--duration-fast)]"
                style={
                  selected
                    ? { borderColor: "var(--color-ink)", color: "var(--color-ink)" }
                    : { borderColor: "var(--color-border)", color: "var(--color-ink-soft)" }
                }
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      {error ? (
        <p role="alert" className="text-body-sm text-[var(--color-error)]">
          {error}
        </p>
      ) : null}

      {/* Acciones: eliminar (con confirmación) + guardar */}
      {confirmDelete ? (
        <div className="flex flex-col gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] p-3">
          <p className="text-body-sm text-[var(--color-ink)]">¿Eliminar este evento?</p>
          <div className="flex gap-3">
            <Button
              variant="ghost"
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="flex-1"
            >
              No
            </Button>
            <Button
              variant="primary"
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="flex-1"
            >
              {del.isPending ? "Eliminando…" : "Sí, eliminar"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-3 pt-2">
          <Button
            variant="ghost"
            type="button"
            onClick={() => setConfirmDelete(true)}
            disabled={busy}
            className="flex-1"
          >
            Eliminar
          </Button>
          <Button variant="primary" type="submit" disabled={busy} className="flex-1">
            {patch.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      )}
    </form>
  );
}
