"use client";

import type { MemoryItemOut, MemoryLayer, SemanticMemoryOut } from "@ynara/shared-schemas";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { Textarea } from "@/components/ui/Textarea";
import { useDeleteMemory, usePatchMemory } from "../api";

type Props = {
  layer: MemoryLayer;
  item: MemoryItemOut;
};

/** El identificador de detalle del ítem: `key` en procedural, `id` si no. */
function refOf(layer: MemoryLayer, item: MemoryItemOut): string {
  return layer === "procedural" && "key" in item ? item.key : "id" in item ? item.id : "";
}

/**
 * Acciones del detalle (build-plan C2): editar (`PATCH`) y borrar (`DELETE`).
 * La edición de contenido aplica a la capa **semántica** (el hecho en texto);
 * episódica no se edita (el backend responde 405) y la procedural —editar un
 * objeto `value`— queda para más adelante, así que sólo muestran "Borrar".
 * El borrado aplica a las 3 capas, con confirmación previa.
 */
export function MemoryDetailActions({ layer, item }: Props) {
  const router = useRouter();
  const ref = refOf(layer, item);
  const patch = usePatchMemory(layer, ref);
  const remove = useDeleteMemory(layer, ref);

  const canEdit = layer === "semantic";
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [draft, setDraft] = useState(() => (canEdit ? (item as SemanticMemoryOut).content : ""));

  const saveEdit = () => {
    patch.mutate(
      { content: draft.trim() },
      {
        onSuccess: () => setEditOpen(false),
      },
    );
  };

  const confirmDelete = () => {
    remove.mutate(undefined, {
      onSuccess: () => router.push("/memoria"),
    });
  };

  return (
    <>
      {canEdit ? (
        <Button
          variant="secondary"
          onClick={() => {
            setDraft((item as SemanticMemoryOut).content);
            patch.reset();
            setEditOpen(true);
          }}
        >
          Editar
        </Button>
      ) : null}
      <Button variant="ghost" onClick={() => setDeleteOpen(true)}>
        Borrar
      </Button>

      <Sheet
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Editar el recuerdo"
        description="Ajustá lo que Ynara guardó. Se vuelve a indexar al guardar."
      >
        <div className="flex flex-col gap-4">
          <Textarea
            label="Texto del recuerdo"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={5}
            maxLength={4096}
            error={patch.isError ? "No se pudo guardar. Probá de nuevo." : undefined}
          />
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setEditOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={saveEdit} disabled={patch.isPending || draft.trim().length === 0}>
              {patch.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </div>
      </Sheet>

      <Sheet
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="¿Borrar este recuerdo?"
        description="Se va para siempre. Ynara no lo va a volver a tener en cuenta."
      >
        <div className="flex flex-col gap-4">
          {remove.isError ? (
            <p role="alert" className="text-body-sm text-[var(--color-error)]">
              No se pudo borrar. Probá de nuevo.
            </p>
          ) : null}
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="secondary"
              onClick={confirmDelete}
              disabled={remove.isPending}
              className="border-[var(--color-error)] text-[var(--color-error)] hover:bg-[var(--color-error-soft)]"
            >
              {remove.isPending ? "Borrando…" : "Borrar"}
            </Button>
          </div>
        </div>
      </Sheet>
    </>
  );
}
