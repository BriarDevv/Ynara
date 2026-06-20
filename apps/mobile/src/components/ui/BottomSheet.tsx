import type { ReactNode } from "react";
import { Modal, Pressable, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

type Props = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Se dispara cuando el sheet termina de aparecer (p. ej. lanzar un fetch). */
  onShow?: () => void;
};

/**
 * Sheet anclado abajo (RN no tiene el `Sheet` de web): `Modal` con backdrop
 * tappable y panel redondeado arriba sobre `bg`. El contenido —con su propio
 * padding— va como `children`. Centraliza el patrón repetido en RecapSheet,
 * WipeMemorySheet, ModePickerSheet y MemoryDetailActions.
 */
export function BottomSheet({ open, onClose, onShow, children }: Props) {
  return (
    <Modal
      visible={open}
      animationType="slide"
      transparent
      onRequestClose={onClose}
      onShow={onShow}
    >
      <View className="flex-1 justify-end bg-black/40">
        {/* Backdrop: tap fuera del panel cierra. */}
        <Pressable
          className="flex-1"
          accessibilityRole="button"
          accessibilityLabel="Cerrar"
          onPress={onClose}
        />
        <SafeAreaView edges={["bottom"]} className="rounded-t-xl bg-bg">
          {children}
        </SafeAreaView>
      </View>
    </Modal>
  );
}
