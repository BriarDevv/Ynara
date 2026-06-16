import { Redirect, Tabs } from "expo-router";
import { View } from "react-native";
import { useUserStore } from "@/stores/user";

// Tints del tab bar: van como valores crudos porque React Navigation no toma
// classNames de NativeWind. Espejan los tokens de tailwind.config.js.
const ACTIVE_TINT = "#2f5aa6"; // colors.azul
const INACTIVE_TINT = "rgba(36,44,63,0.45)"; // colors.ink.muted

/**
 * Layout de tabs — la home post-onboarding: **Hoy** + **Chat**. Hace de gate:
 * sin onboarding completo manda al wizard. La conversación (`/chat/[sessionId]`)
 * vive en el stack raíz, así que abre full-screen por encima del tab bar.
 *
 * Iconos geométricos con Views (sin `@expo/vector-icons`, que no es dep directa
 * de mobile): cuadrado redondeado = Hoy, pill = Chat; se rellenan al estar activo.
 */
export default function TabsLayout() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);
  if (!onboardingCompleted) return <Redirect href="/onboarding" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: ACTIVE_TINT,
        tabBarInactiveTintColor: INACTIVE_TINT,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Hoy",
          tabBarIcon: ({ color, focused }) => (
            <View
              style={{
                width: 16,
                height: 16,
                borderRadius: 5,
                borderWidth: 2,
                borderColor: color,
                backgroundColor: focused ? color : "transparent",
              }}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title: "Chat",
          tabBarIcon: ({ color, focused }) => (
            <View
              style={{
                width: 18,
                height: 13,
                borderRadius: 999,
                borderWidth: 2,
                borderColor: color,
                backgroundColor: focused ? color : "transparent",
              }}
            />
          ),
        }}
      />
    </Tabs>
  );
}
