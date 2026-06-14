import { View } from "react-native";
import { cn } from "@/lib/cn";

type Props = {
  total: number;
  current: number;
  className?: string;
};

/**
 * Indicador de progreso del onboarding (RN). Espejo del `ProgressDots` web:
 * el dot actual es una pill ancha azul de marca, los completados ink, los
 * pendientes faint.
 */
export function ProgressDots({ total, current, className }: Props) {
  const dots = Array.from({ length: total }, (_, i) => ({
    id: `dot-${i}`,
    active: i <= current,
    isCurrent: i === current,
  }));

  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 1, max: total, now: Math.max(1, Math.min(total, current + 1)) }}
      className={cn("flex-row items-center gap-2", className)}
    >
      {dots.map((dot) => (
        <View
          key={dot.id}
          className={cn(
            "h-1.5 rounded-pill",
            dot.isCurrent
              ? "w-8 bg-blue-flat"
              : dot.active
                ? "w-1.5 bg-ink-deep"
                : "w-1.5 bg-ink-faint",
          )}
        />
      ))}
    </View>
  );
}
