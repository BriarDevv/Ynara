import { useMemoryWipeExecute, useMemoryWipePreview } from "@ynara/core/features/memory";
import type { MemoryWipePreview } from "@ynara/shared-schemas";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
import { ApiError } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
};

/** Palabra que el usuario debe escribir para habilitar el borrado. */
const CONFIRM_WORD = "BORRAR";

/**
 * Sheet de confirmación del wipe total de memoria (mobile), sobre el `BottomSheet`
 * compartido. Espeja la lógica del `WipeMemoryDialog` de web:
 *
 * 1. Al abrir → `useMemoryWipePreview` para mostrar conteos (lo que se borraría).
 * 2. El usuario escribe "BORRAR" para habilitar el botón.
 * 3. Confirmar → `useMemoryWipeExecute` con los `expected_*` del preview.
 * 4. Si el backend devuelve 409 (ApiError, conteos cambiaron) → re-preview + aviso.
 * 5. Éxito → cerrar + mensaje de confirmación al padre.
 */
export function WipeMemorySheet({ open, onClose }: Props) {
  const [confirmText, setConfirmText] = useState("");
  const [preview, setPreview] = useState<MemoryWipePreview | null>(null);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const wipePreview = useMemoryWipePreview();
  const wipeExecute = useMemoryWipeExecute();

  // Al abrir el sheet dispara el preview automáticamente.
  function handleOpen() {
    setConfirmText("");
    setPreview(null);
    setConflictMsg(null);
    setSuccessMsg(null);
    wipePreview
      .mutateAsync()
      .then(setPreview)
      .catch(() => null);
  }

  async function handleConfirm() {
    if (!preview) return;
    setConflictMsg(null);
    try {
      const result = await wipeExecute.mutateAsync({
        expected_semantic: preview.semantic,
        expected_episodic: preview.episodic,
        expected_procedural: preview.procedural,
      });
      setSuccessMsg(
        `Se borraron ${result.total} recuerdos (${result.semantic} hechos, ${result.episodic} momentos, ${result.procedural} costumbres).`,
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // 409: los conteos cambiaron — re-preview con los conteos actuales.
        const body = err.body as {
          message?: string;
          semantic?: number;
          episodic?: number;
          procedural?: number;
          total?: number;
        };
        setConflictMsg(body.message ?? "Los conteos cambiaron. Revisá y confirmá de nuevo.");
        // Actualiza el preview con los conteos frescos del 409.
        if (
          typeof body.semantic === "number" &&
          typeof body.episodic === "number" &&
          typeof body.procedural === "number" &&
          typeof body.total === "number"
        ) {
          setPreview({
            semantic: body.semantic,
            episodic: body.episodic,
            procedural: body.procedural,
            total: body.total,
          });
        }
        setConfirmText("");
      } else {
        // Cualquier otro error (500, timeout, red): avisar en vez de tragarlo —
        // es una acción irreversible y el usuario tiene que saber que falló.
        setConflictMsg("No pudimos borrar la memoria. Revisá la conexión y probá de nuevo.");
      }
    }
  }

  function handleClose() {
    setConfirmText("");
    setPreview(null);
    setConflictMsg(null);
    setSuccessMsg(null);
    onClose();
  }

  const canConfirm = confirmText === CONFIRM_WORD && preview !== null && !wipeExecute.isPending;

  return (
    <BottomSheet open={open} onClose={handleClose} onShow={handleOpen}>
      <View className="gap-5 px-6 pb-6 pt-5">
        <View className="gap-1">
          <Text className="text-title font-display text-ink-deep">Borrar toda la memoria</Text>
          <Text className="text-body-sm text-ink-soft">
            Esta acción es irreversible. Ynara olvidará todo lo que guardó con vos.
          </Text>
        </View>

        {/* Estado: cargando preview */}
        {wipePreview.isPending && !preview ? (
          <Text className="text-body text-ink-soft">Calculando conteos…</Text>
        ) : wipePreview.isError && !preview ? (
          <View className="gap-2 rounded-lg border border-border bg-bg p-4">
            <Text className="text-body text-ink">No pudimos calcular los conteos</Text>
            <Pressable
              onPress={() =>
                wipePreview
                  .mutateAsync()
                  .then(setPreview)
                  .catch(() => null)
              }
            >
              <Text className="text-button text-ink underline">Reintentar</Text>
            </Pressable>
          </View>
        ) : successMsg ? (
          // Estado: wipe exitoso.
          <View className="gap-4">
            <View className="rounded-lg border border-border bg-bg p-4">
              <Text className="text-body text-ink-soft">{successMsg}</Text>
            </View>
            <Button variant="secondary" onPress={handleClose}>
              Listo
            </Button>
          </View>
        ) : preview ? (
          // Estado normal: preview disponible.
          <View className="gap-4">
            {/* Conteos de lo que se borraría */}
            <View className="rounded-lg border border-border bg-bg p-4 gap-1">
              <Text className="text-body text-ink">
                Se borrarán <Text className="font-body-semibold">{preview.total} recuerdos</Text> en
                total:
              </Text>
              <Text className="text-body-sm text-ink-soft">
                {preview.semantic} hechos · {preview.episodic} momentos · {preview.procedural}{" "}
                costumbres
              </Text>
            </View>

            {/* Aviso de 409 */}
            {conflictMsg ? (
              <View className="rounded-lg border border-border bg-bg p-3">
                <Text className="text-body-sm text-error">{conflictMsg}</Text>
              </View>
            ) : null}

            {/* Campo de confirmación */}
            <TextField
              label={`Escribí "${CONFIRM_WORD}" para confirmar`}
              value={confirmText}
              onChangeText={setConfirmText}
              autoCapitalize="characters"
              autoCorrect={false}
              placeholder={CONFIRM_WORD}
            />

            <View className="flex-row gap-3">
              <Button variant="secondary" onPress={handleClose} className="flex-1">
                Cancelar
              </Button>
              <Button
                variant="primary"
                onPress={handleConfirm}
                disabled={!canConfirm}
                className="flex-1"
              >
                {wipeExecute.isPending ? "Borrando…" : "Borrar todo"}
              </Button>
            </View>
          </View>
        ) : null}
      </View>
    </BottomSheet>
  );
}
