import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/Text";

/**
 * CTA "Recap pendiente" (wireframe 06): card azul de marca, full-width, que
 * invita a cerrar el día con Ynara. Abre el sheet del recap. Espejo del
 * `RecapCta` de web (el ícono de @ynara/ui se reemplaza por un chevron carácter,
 * ya que `@ynara/ui` no es dep de mobile).
 */
export function RecapCta({ onOpen }: { onOpen: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onOpen}
      className="flex-row items-center gap-4 rounded-lg bg-blue-flat p-4 active:bg-blue-flat-active"
    >
      <View className="flex-1 gap-0.5">
        <Text className="text-caption text-on-dark opacity-80">Recap pendiente</Text>
        <Text className="text-body font-body-medium text-on-dark">Cerrá el día con Ynara</Text>
      </View>
      <Text className="text-body text-on-dark opacity-80">›</Text>
    </Pressable>
  );
}
