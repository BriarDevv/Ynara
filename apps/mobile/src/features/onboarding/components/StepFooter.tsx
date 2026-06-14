import { View } from "react-native";
import { Button } from "@/components/ui/Button";

type Props = {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
};

/**
 * Pie de navegación de un step (mobile): CTA primario full-width arriba,
 * "Atrás" (ghost) abajo. Espejo del StepFooter web.
 */
export function StepFooter({ onBack, onNext, nextLabel = "Seguir", nextDisabled = false }: Props) {
  return (
    <View className="gap-2">
      <Button variant="primary" fullWidth onPress={onNext} disabled={nextDisabled}>
        {nextLabel}
      </Button>
      {onBack ? (
        <Button variant="ghost" fullWidth onPress={onBack}>
          Atrás
        </Button>
      ) : null}
    </View>
  );
}
