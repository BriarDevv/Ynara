import { type ComponentRef, type ReactNode, useEffect, useRef } from "react";
import { AccessibilityInfo, findNodeHandle, ScrollView, View } from "react-native";
import { Text } from "@/components/ui/Text";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot al pie (StepFooter). */
  footer?: ReactNode;
  /**
   * Al montar el step, mueve el foco del lector de pantalla al título para que
   * VoiceOver/TalkBack anuncien el paso nuevo (espejo del `<h1>` enfocable del
   * StepShell web). Se apaga (`false`) en los pasos que ya enfocan un input
   * propio (auth/nombre), para no robarles el foco — equivale al guard de
   * `activeElement === body` del web.
   */
  focusOnMount?: boolean;
};

/**
 * Container del contenido de un step (mobile). Header (eyebrow → title →
 * subtitle) + body scrolleable + footer fijo abajo. Espejo del StepShell web,
 * sin la variante card de desktop.
 */
export function StepShell({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
  focusOnMount = true,
}: Props) {
  const titleRef = useRef<ComponentRef<typeof Text>>(null);

  useEffect(() => {
    if (!focusOnMount) return;
    const tag = findNodeHandle(titleRef.current);
    if (tag != null) AccessibilityInfo.setAccessibilityFocus(tag);
  }, [focusOnMount]);

  return (
    <View className="flex-1">
      <ScrollView contentContainerClassName="gap-8 px-6 py-8" keyboardShouldPersistTaps="handled">
        <View className="gap-3">
          {eyebrow ? <Text className="text-caption text-ink-soft">{eyebrow}</Text> : null}
          <Text
            ref={titleRef}
            accessibilityRole="header"
            className="text-title font-display text-ink-deep"
          >
            {title}
          </Text>
          {subtitle ? <Text className="text-body text-ink-soft">{subtitle}</Text> : null}
        </View>
        <View className="gap-6">{children}</View>
      </ScrollView>
      {footer ? <View className="border-t border-border px-6 py-4">{footer}</View> : null}
    </View>
  );
}
