import type { ReactNode } from "react";
import { Pressable, type PressableProps } from "react-native";
import { Text } from "@/components/ui/Text";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "subtle";

type Props = Omit<PressableProps, "children"> & {
  variant?: Variant;
  fullWidth?: boolean;
  /** Texto del botón (string). Para contenido custom, usar children. */
  children: ReactNode;
  className?: string;
};

// Contenedor por variante. La altura efectiva sale de py-3 (~44px), dentro
// del rango táctil de Apple/WCAG. `active:` mapea al pressed de Pressable.
const CONTAINER: Record<Variant, string> = {
  primary: "px-6 py-3 rounded-md bg-blue-flat active:bg-blue-flat-active",
  secondary: "px-6 py-3 rounded-md bg-transparent border border-border-strong active:bg-bg-soft",
  ghost: "px-4 py-3 rounded-md bg-transparent active:bg-bg-soft",
  subtle: "px-1 py-1 bg-transparent",
};

// Color/estilo del texto por variante.
const LABEL: Record<Variant, string> = {
  primary: "text-on-dark",
  secondary: "text-ink",
  ghost: "text-ink-soft",
  subtle: "text-ink-soft underline",
};

/**
 * Botón base (RN). Espejo del `Button` de la web (apps/web/src/components/ui),
 * portado a Pressable + Text con NativeWind. El feedback de press es
 * `active:opacity` (respeta reduce-motion del SO a nivel sistema).
 */
export function Button({
  variant = "primary",
  fullWidth = false,
  children,
  className,
  disabled,
  ...rest
}: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      className={cn(
        "flex-row items-center justify-center gap-2 active:opacity-90",
        CONTAINER[variant],
        fullWidth && "w-full",
        disabled && "opacity-50",
        className,
      )}
      {...rest}
    >
      <Text className={cn("text-button font-body-semibold text-center", LABEL[variant])}>
        {children}
      </Text>
    </Pressable>
  );
}
