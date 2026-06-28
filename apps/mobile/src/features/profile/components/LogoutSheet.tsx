import { View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Text } from "@/components/ui/Text";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

/**
 * Confirmación de cierre de sesión (auditoría H4), sobre el `BottomSheet`
 * compartido. Espeja el `LogoutDialog` de web: aviso suave antes de salir de la
 * cuenta. El usuario tiene que volver a entrar para seguir.
 */
export function LogoutSheet({ open, onClose, onConfirm }: Props) {
  return (
    <BottomSheet open={open} onClose={onClose}>
      <View className="gap-5 px-6 pb-6 pt-5">
        <View className="gap-1">
          <Text className="text-title font-display text-ink-deep">Cerrar sesión</Text>
        </View>

        <Text className="text-body text-ink">
          Vas a salir de tu cuenta. Vas a tener que volver a entrar para seguir.
        </Text>

        <View className="flex-row gap-3">
          <Button variant="secondary" onPress={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button
            variant="primary"
            onPress={onConfirm}
            className="flex-1"
            accessibilityLabel="Cerrar sesión"
          >
            Cerrar sesión
          </Button>
        </View>
      </View>
    </BottomSheet>
  );
}
