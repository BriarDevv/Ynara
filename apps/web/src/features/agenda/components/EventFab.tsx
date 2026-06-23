"use client";

import { useReducer, useRef } from "react";
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

/** Default del campo fecha/hora: ahora redondeado a la hora siguiente, en hora
 *  local (datetime-local interpreta el string como local). Se recomputa en cada
 *  apertura para que un segundo evento no nazca con la hora del primero. */
function defaultStartAt(): string {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 1);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

/** Estado del FAB + form de creación, agrupado en un solo reducer (un cambio
 *  lógico no abanica en renders separados). */
type FabState = {
  open: boolean;
  title: string;
  startAt: string;
  durationMin: string;
  modeId: ModeId;
  titleError: string | null;
  durationError: string | null;
  submitError: string | null;
};

type FabAction =
  | { type: "open" }
  | { type: "close" }
  | { type: "setTitle"; value: string }
  | { type: "setStartAt"; value: string }
  | { type: "setDurationMin"; value: string }
  | { type: "setModeId"; value: ModeId }
  | { type: "setTitleError"; value: string | null }
  | { type: "setDurationError"; value: string | null }
  | { type: "clearErrors" }
  | { type: "submitError"; value: string }
  | { type: "reset"; activeMode: ModeId };

/** Estado inicial: el selector de modo arranca preseleccionado en el modo
 *  activo de la pantalla (seed del prop; el usuario puede cambiarlo). */
function initFabState(activeMode: ModeId): FabState {
  return {
    open: false,
    title: "",
    startAt: defaultStartAt(),
    durationMin: "60",
    modeId: activeMode,
    titleError: null,
    durationError: null,
    submitError: null,
  };
}

function fabReducer(state: FabState, action: FabAction): FabState {
  switch (action.type) {
    case "open":
      // Recomputar la fecha/hora por defecto en cada apertura (si no, el segundo
      // evento nace con la hora calculada al montar la pantalla).
      return {
        ...state,
        startAt: defaultStartAt(),
        titleError: null,
        durationError: null,
        submitError: null,
        open: true,
      };
    case "close":
      return { ...state, open: false };
    case "setTitle":
      return { ...state, title: action.value };
    case "setStartAt":
      return { ...state, startAt: action.value };
    case "setDurationMin":
      return { ...state, durationMin: action.value };
    case "setModeId":
      return { ...state, modeId: action.value };
    case "setTitleError":
      return { ...state, titleError: action.value };
    case "setDurationError":
      return { ...state, durationError: action.value };
    case "clearErrors":
      return { ...state, titleError: null, durationError: null, submitError: null };
    case "submitError":
      return { ...state, submitError: action.value };
    case "reset":
      // Limpiar y cerrar (incluido startAt, recomputado fresco) tras crear.
      return initFabState(action.activeMode);
    default:
      return state;
  }
}

/**
 * FAB redondo "+" fijo en la esquina inferior derecha + Sheet de creación
 * rápida de eventos (título + fecha/hora + duración + modo).
 *
 * El FAB se tiñe con el modo activo de la pantalla. El Sheet usa `useCreateEvent`
 * y cierra al crear exitosamente.
 */
export function EventFab({ fillVar, activeMode }: Props) {
  // Estado del FAB + form en un solo reducer. El selector de modo se seedea con
  // `activeMode` (el usuario puede cambiarlo). Los errores por campo (aria-invalid
  // + describedby vía TextField) van separados del error de red, que es global.
  const [state, dispatch] = useReducer(fabReducer, activeMode, initFabState);
  const { open, title, startAt, durationMin, modeId, titleError, durationError, submitError } =
    state;

  const { mutateAsync, isPending } = useCreateEvent();
  const titleRef = useRef<HTMLInputElement>(null);

  function handleOpen() {
    dispatch({ type: "open" });
  }

  function handleClose() {
    dispatch({ type: "close" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    dispatch({ type: "clearErrors" });
    if (!title.trim()) {
      dispatch({ type: "setTitleError", value: "El título es obligatorio." });
      titleRef.current?.focus();
      return;
    }
    const dur = Number(durationMin);
    if (!Number.isFinite(dur) || dur <= 0) {
      dispatch({ type: "setDurationError", value: "La duración debe ser un número positivo." });
      return;
    }
    try {
      await mutateAsync({
        title: title.trim(),
        start_at: new Date(startAt).toISOString(),
        duration_min: dur,
        mode: modeId,
      });
      // Limpiar y cerrar (incluido startAt, recomputado fresco).
      dispatch({ type: "reset", activeMode });
    } catch {
      dispatch({ type: "submitError", value: "No pudimos crear el evento. Intentá de nuevo." });
    }
  }

  return (
    <>
      {/* FAB */}
      <button
        type="button"
        aria-label="Crear evento"
        onClick={handleOpen}
        className="fixed bottom-[calc(4.5rem_+_env(safe-area-inset-bottom))] right-6 z-20 flex h-12 w-12 items-center justify-center rounded-full text-[var(--color-on-dark)] shadow-[0_8px_20px_-8px_var(--color-accent)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)] active:scale-95 md:right-8 lg:bottom-8"
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
            onChange={(e) => {
              dispatch({ type: "setTitle", value: e.target.value });
              if (titleError) dispatch({ type: "setTitleError", value: null });
            }}
            error={titleError ?? undefined}
            required
            autoFocus
          />

          <TextField
            label="Fecha y hora"
            type="datetime-local"
            value={startAt}
            onChange={(e) => dispatch({ type: "setStartAt", value: e.target.value })}
            required
          />

          <TextField
            label="Duración (minutos)"
            type="number"
            min="1"
            step="5"
            value={durationMin}
            onChange={(e) => {
              dispatch({ type: "setDurationMin", value: e.target.value });
              if (durationError) dispatch({ type: "setDurationError", value: null });
            }}
            error={durationError ?? undefined}
            required
          />

          {/* Selector de modo — fieldset/legend = grupo con nombre accesible */}
          <fieldset className="flex flex-col gap-1.5 border-none p-0">
            <legend className="text-caption text-[var(--color-ink-soft)]">Modo</legend>
            <div className="flex flex-wrap gap-2">
              {MODES.map((m) => {
                const selected = m.id === modeId;
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => dispatch({ type: "setModeId", value: m.id as ModeId })}
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
          </fieldset>

          {/* Error global solo para el fallo de red; los de validación van por
              campo (aria-invalid + describedby en el TextField). */}
          {submitError ? (
            <p role="alert" className="text-body-sm text-[var(--color-error)]">
              {submitError}
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
