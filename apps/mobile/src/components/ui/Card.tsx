import type { ReactNode } from "react";
import { Pressable, type PressableProps, View, type ViewProps } from "react-native";
import { cn } from "@/lib/cn";

const BASE = "bg-bg border border-border rounded-lg p-6";

type CardProps = ViewProps & {
  children: ReactNode;
  className?: string;
};

/** Card base (RN). Espejo del `Card` de la web. Superficie blanca elevada. */
export function Card({ children, className, ...rest }: CardProps) {
  return (
    <View className={cn(BASE, className)} {...rest}>
      {children}
    </View>
  );
}

type PressableCardProps = Omit<PressableProps, "children"> & {
  children: ReactNode;
  className?: string;
};

/**
 * Variante interactiva: card tappable (reemplaza el hover/scale de la web por
 * feedback de press, ya que RN no tiene hover).
 */
export function PressableCard({ children, className, ...rest }: PressableCardProps) {
  return (
    <Pressable className={cn(BASE, "active:opacity-90 active:scale-[0.99]", className)} {...rest}>
      {children}
    </Pressable>
  );
}
