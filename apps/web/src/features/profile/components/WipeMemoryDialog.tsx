"use client";

import { ApiError } from "@ynara/core/api";
import type { MemoryWipePreview } from "@ynara/shared-schemas";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { TextField } from "@/components/ui/TextField";
import { useMemoryWipeExecute, useMemoryWipePreview } from "@/features/memory/api";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Callback opcional al completar el wipe con éxito. */
  onSuccess?: () => void;
};

const CONFIRM_WORD = "BORRAR";

/**
 * Dialog de confirmación del wipe total de memoria (SAGRADO — regla #3).
 *
 * Flujo:
 *  1. Al abrirse, dispara el preview (`POST /v1/memory/wipe?dry_run=true`) para
 *     obtener los conteos actuales.
 *  2. Muestra cuántos recuerdos se borrarían por capa.
 *  3. Requiere que el usuario escriba exactamente "BORRAR" para habilitar el botón.
 *  4. Al confirmar, ejecuta el wipe con los `expected_*` del preview fresco.
 *  5. Si el backend responde 409 (los conteos cambiaron), re-trae el preview y
 *     muestra el aviso. No borra nada.
 */
export function WipeMemoryDialog({ open, onClose, onSuccess }: Props) {
  const [confirmText, setConfirmText] = useState("");
  const [preview, setPreview] = useState<MemoryWipePreview | null>(null);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);

  const wipePreview = useMemoryWipePreview();
  const wipeExecute = useMemoryWipeExecute();

  // Refs estables de las funciones de mutation: las identidades de
  // `mutateAsync` y `reset` cambian en cada render de la mutation, así que
  // las capturamos en refs para usarlas dentro de effects sin incluirlas en
  // las deps (y disparar loops). Mismo patrón que el `onDismissRef` del Toast.
  const previewMutateRef = useRef(wipePreview.mutateAsync);
  previewMutateRef.current = wipePreview.mutateAsync;
  const previewResetRef = useRef(wipePreview.reset);
  previewResetRef.current = wipePreview.reset;
  const executeResetRef = useRef(wipeExecute.reset);
  executeResetRef.current = wipeExecute.reset;

  // Al abrir, trae el preview fresco; al cerrar, limpia el estado local.
  useEffect(() => {
    if (!open) {
      setConfirmText("");
      setPreview(null);
      setConflictMessage(null);
      previewResetRef.current();
      executeResetRef.current();
      return;
    }
    previewMutateRef
      .current()
      .then(setPreview)
      .catch(() => {});
  }, [open]);

  const canConfirm = confirmText === CONFIRM_WORD && preview !== null && !wipeExecute.isPending;

  async function handleConfirm() {
    if (!preview) return;
    setConflictMessage(null);
    try {
      await wipeExecute.mutateAsync({
        expected_semantic: preview.semantic,
        expected_episodic: preview.episodic,
        expected_procedural: preview.procedural,
      });
      onClose();
      onSuccess?.();
    } catch (err) {
      // 409: los conteos cambiaron desde el preview; re-trae y avisa.
      if (err instanceof ApiError && err.status === 409) {
        const body = err.body as {
          message?: string;
          semantic?: number;
          episodic?: number;
          procedural?: number;
          total?: number;
        };
        setConflictMessage(body.message ?? "Los conteos cambiaron, revisá de nuevo.");
        // Re-trae el preview con los conteos actuales para re-confirmar.
        try {
          const fresh = await previewMutateRef.current();
          setPreview(fresh);
        } catch {
          // Si el preview también falla, mantenemos el mensaje de 409.
        }
        setConfirmText("");
      }
      // Otros errores: `wipeExecute.error` ya está disponible para mostrar.
    }
  }

  const loadingPreview = wipePreview.isPending && !preview;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Borrar toda mi memoria"
      description="Esta acción es permanente e irreversible."
    >
      <div className="flex flex-col gap-5">
        {/* Conteos del preview */}
        {loadingPreview ? (
          <p className="text-body-sm text-[var(--color-ink-soft)]">Calculando conteos…</p>
        ) : preview ? (
          <div
            className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] p-4"
            aria-live="polite"
          >
            <p className="text-body text-[var(--color-ink)]">
              Vas a borrar{" "}
              <strong className="text-[var(--color-error)]">{preview.total} recuerdos</strong> en
              total:
            </p>
            <ul className="text-body-sm mt-2 list-inside list-disc space-y-0.5 text-[var(--color-ink-soft)]">
              <li>{preview.semantic} hechos (semántica)</li>
              <li>{preview.episodic} momentos (episódica)</li>
              <li>{preview.procedural} costumbres (procedural)</li>
            </ul>
          </div>
        ) : null}

        {/* Aviso de 409 */}
        {conflictMessage ? (
          <p role="alert" className="text-body-sm text-[var(--color-error)]">
            {conflictMessage}
          </p>
        ) : null}

        {/* Error del execute (no 409) */}
        {wipeExecute.error &&
        !(wipeExecute.error instanceof ApiError && wipeExecute.error.status === 409) ? (
          <p role="alert" className="text-body-sm text-[var(--color-error)]">
            Ocurrió un error al borrar. Intentá de nuevo.
          </p>
        ) : null}

        {/* Campo de confirmación */}
        <TextField
          label={`Escribí "${CONFIRM_WORD}" para confirmar`}
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder={CONFIRM_WORD}
          autoComplete="off"
          disabled={wipeExecute.isPending}
        />

        {/* Acciones */}
        <div className="flex flex-col gap-3 sm:flex-row-reverse">
          <Button
            variant="primary"
            fullWidth
            disabled={!canConfirm}
            onClick={handleConfirm}
            aria-label="Confirmar borrado permanente de toda la memoria"
            className="bg-[var(--color-error)] hover:opacity-90 disabled:hover:opacity-50"
          >
            {wipeExecute.isPending ? "Borrando…" : "Borrar para siempre"}
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose} disabled={wipeExecute.isPending}>
            Cancelar
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
