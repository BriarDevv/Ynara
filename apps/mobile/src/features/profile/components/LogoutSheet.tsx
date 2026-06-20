import { View } from "react-native";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Button } from "@/components/ui/Button";
import { Text } from "@/components/ui/Text";

type Props = {
  open: boolean;
  /** Cuenta de invitado (efímera): el logout borra todo sin recuperación. */
  isEphemeral: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

/**
 * Confirmación de cierre de sesión (auditoría H4), sobre el `BottomSheet`
 * compartido. Espeja el `LogoutDialog` de web: para cuentas efímeras
 * ("invitado") el logout es destructivo —borra la memoria y los datos del
 * dispositivo sin vuelta atrás—, así que el copy lo explicita y el botón cambia
 * de label.
 *
 * El tono de error visual del botón (que sí tiene web) se omite a propósito:
 * el resto de los sheets de mobile —incluido el de borrar TODA la memoria— usan
 * `primary`, y la confirmación en sí ya es la red de seguridad. Unificar a un
 * botón destructivo sería un cambio del `Button` para ambos sheets, fuera de
 * este chunk.
 */
export function LogoutSheet({ open, isEphemeral, onClose, onConfirm }: Props) {
  return (
    <BottomSheet open={open} onClose={onClose}>
      <View className="gap-5 px-6 pb-6 pt-5">
        <View className="gap-1">
          <Text className="text-title font-display text-ink-deep">Cerrar sesión</Text>
          {isEphemeral ? (
            <Text className="text-body-sm text-ink-soft">Tu cuenta es de invitado.</Text>
          ) : null}
        </View>

        <Text className="text-body text-ink">
          {isEphemeral
            ? "Como invitado, al cerrar sesión se borran tu memoria y tus datos de este dispositivo, y no se pueden recuperar."
            : "Vas a salir de tu cuenta. Vas a tener que volver a entrar para seguir."}
        </Text>

        <View className="flex-row gap-3">
          <Button variant="secondary" onPress={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button
            variant="primary"
            onPress={onConfirm}
            className="flex-1"
            accessibilityLabel={isEphemeral ? "Cerrar sesión y borrar mis datos" : "Cerrar sesión"}
          >
            {isEphemeral ? "Cerrar sesión y borrar" : "Cerrar sesión"}
          </Button>
        </View>
      </View>
    </BottomSheet>
  );
}
