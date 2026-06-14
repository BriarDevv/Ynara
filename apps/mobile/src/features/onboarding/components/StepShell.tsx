import type { ReactNode } from "react";
import { ScrollView, Text, View } from "react-native";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot al pie (StepFooter). */
  footer?: ReactNode;
};

/**
 * Container del contenido de un step (mobile). Header (eyebrow → title →
 * subtitle) + body scrolleable + footer fijo abajo. Espejo del StepShell web,
 * sin la variante card de desktop.
 */
export function StepShell({ eyebrow, title, subtitle, children, footer }: Props) {
  return (
    <View className="flex-1">
      <ScrollView contentContainerClassName="gap-8 px-6 py-8" keyboardShouldPersistTaps="handled">
        <View className="gap-3">
          {eyebrow ? <Text className="text-caption text-ink-soft">{eyebrow}</Text> : null}
          <Text className="text-title font-semibold text-ink-deep">{title}</Text>
          {subtitle ? <Text className="text-body text-ink-soft">{subtitle}</Text> : null}
        </View>
        <View className="gap-6">{children}</View>
      </ScrollView>
      {footer ? <View className="border-t border-border px-6 py-4">{footer}</View> : null}
    </View>
  );
}
