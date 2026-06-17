import { type ComponentRef, forwardRef } from "react";
import { Text as RNText, type TextProps } from "react-native";
import { cn } from "@/lib/cn";

type Props = TextProps & { className?: string };

/**
 * Text de la app con la tipografía de marca. Aplica **DM Sans** (cuerpo) por
 * default; si el `className` ya trae una familia (`font-display*` para
 * titulares, o un `font-body*` explícito), se respeta y no se pisa. Reemplaza el
 * `Text` de react-native en toda la app (RN no hereda `fontFamily`, así que la
 * fuente se fija acá una sola vez en vez de repetir la clase en cada `<Text>`).
 */
export const Text = forwardRef<ComponentRef<typeof RNText>, Props>(function Text(
  { className, ...props },
  ref,
) {
  const hasFamily = className?.includes("font-display") || className?.includes("font-body");
  return <RNText ref={ref} className={cn(!hasFamily && "font-body", className)} {...props} />;
});
