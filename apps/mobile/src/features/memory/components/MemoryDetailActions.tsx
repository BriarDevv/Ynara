import { useDeleteMemory, usePatchMemory } from "@ynara/core/features/memory";
import type { MemoryItemOut, MemoryLayer, SemanticMemoryOut } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Text } from "@/components/ui/Text";
import { Textarea } from "@/components/ui/Textarea";

type Props = {
  layer: MemoryLayer;
  item: MemoryItemOut;
};

/** El identificador de detalle del ítem: `key` en procedural, `id` si no. */
function refOf(layer: MemoryLayer, item: MemoryItemOut): string {
  return layer === "procedural" && "key" in item ? item.key : "id" in item ? item.id : "";
}

/**
 * Acciones del detalle: **editar** (`PATCH`, solo capa semántica — episódica da
 * 405 y procedural queda para después) y **borrar** (`DELETE`, las 3 capas, con
 * confirmación). Ambos sobre el `BottomSheet` compartido. Espejo de
 * `MemoryDetailActions` de web. Borrar → vuelve a la lista.
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
    patch.mutate({ content: draft.trim() }, { onSuccess: () => setEditOpen(false) });
  };

  const confirmDelete = () => {
    remove.mutate(undefined, { onSuccess: () => router.back() });
  };

  return (
    <>
      {canEdit ? (
        <Button
          variant="secondary"
          onPress={() => {
            setDraft((item as SemanticMemoryOut).content);
            patch.reset();
            setEditOpen(true);
          }}
        >
          Editar
        </Button>
      ) : null}
      <Button variant="ghost" onPress={() => setDeleteOpen(true)}>
        Borrar
      </Button>

      {/* Editar (solo semántica) */}
      <BottomSheet open={editOpen} onClose={() => setEditOpen(false)}>
        <View className="gap-4 px-6 pb-6 pt-5">
          <View className="gap-1">
            <Text className="text-title font-display text-ink-deep">Editar el recuerdo</Text>
            <Text className="text-body-sm text-ink-soft">
              Ajustá lo que Ynara guardó. Se vuelve a indexar al guardar.
            </Text>
          </View>
          <Textarea
            label="Texto del recuerdo"
            value={draft}
            onChangeText={setDraft}
            maxLength={4096}
            error={patch.isError ? "No se pudo guardar. Probá de nuevo." : undefined}
          />
          <View className="flex-row justify-end gap-3">
            <Button variant="ghost" onPress={() => setEditOpen(false)}>
              Cancelar
            </Button>
            <Button onPress={saveEdit} disabled={patch.isPending || draft.trim().length === 0}>
              {patch.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </View>
        </View>
      </BottomSheet>

      {/* Borrar (con confirmación) */}
      <BottomSheet open={deleteOpen} onClose={() => setDeleteOpen(false)}>
        <View className="gap-4 px-6 pb-6 pt-5">
          <View className="gap-1">
            <Text className="text-title font-display text-ink-deep">¿Borrar este recuerdo?</Text>
            <Text className="text-body-sm text-ink-soft">
              Se va para siempre. Ynara no lo va a volver a tener en cuenta.
            </Text>
          </View>
          {remove.isError ? (
            <Text className="text-body-sm text-error">No se pudo borrar. Probá de nuevo.</Text>
          ) : null}
          <View className="flex-row justify-end gap-3">
            <Button variant="ghost" onPress={() => setDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="secondary"
              className="border-error"
              onPress={confirmDelete}
              disabled={remove.isPending}
            >
              {remove.isPending ? "Borrando…" : "Borrar"}
            </Button>
          </View>
        </View>
      </BottomSheet>
    </>
  );
}
