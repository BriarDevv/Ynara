import { Redirect, Tabs } from "expo-router";
import { View } from "react-native";
import { useUserStore } from "@/stores/user";

// Tints del tab bar: van como valores crudos porque React Navigation no toma
// classNames de NativeWind. Espejan los tokens de tailwind.config.js.
const ACTIVE_TINT = "#6e92cc"; // colors.celeste (resalta sobre el tab bar oscuro)
const INACTIVE_TINT = "rgba(243,240,234,0.45)"; // marfil tenue (ink-muted en oscuro)
// Fondo y borde del tab bar en oscuro (React Navigation no toma classNames).
const TAB_BAR_BG = "#2b3346"; // colors.bg (surface)
const TAB_BAR_BORDER = "rgba(243,240,234,0.10)"; // colors.border

/**
 * Layout de tabs — la home post-onboarding: **Hoy** · **Agenda** · **Chat** ·
 * **Tú** (Memoria accesible desde Tú). Hace de gate: sin onboarding completo
 * manda al wizard. El Chat vive dentro de su tab (entrás directo a la conversación).
 *
 * Iconos geométricos con Views (sin `@expo/vector-icons`, que no es dep directa
 * de mobile): cuadrado redondeado = Hoy, círculo con aguja = Agenda, pill = Chat,
 * persona (círculo + base) = Tú; se rellenan al estar activo. Memoria sigue siendo
 * una ruta navegable (`/memoria`, `/buscar`) pero no aparece como tab
 * (`href: null`); se accede desde la sección Memoria de Tú.
 */
export default function TabsLayout() {
  const onboardingCompleted = useUserStore((s) => s.onboardingCompleted);
  if (!onboardingCompleted) return <Redirect href="/welcome" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: ACTIVE_TINT,
        tabBarInactiveTintColor: INACTIVE_TINT,
        tabBarStyle: { backgroundColor: TAB_BAR_BG, borderTopColor: TAB_BAR_BORDER },
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
        name="agenda"
        options={{
          title: "Agenda",
          tabBarIcon: ({ color, focused }) => (
            // Reloj / calendario: círculo con una línea horizontal (aguja).
            <View
              style={{
                width: 16,
                height: 16,
                borderRadius: 999,
                borderWidth: 2,
                borderColor: color,
                backgroundColor: focused ? color : "transparent",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {!focused ? (
                <View
                  style={{
                    width: 6,
                    height: 1.5,
                    borderRadius: 1,
                    backgroundColor: color,
                  }}
                />
              ) : null}
            </View>
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
      {/* Memoria: ruta navegable desde Tú, pero sin tab visible en el bar. */}
      <Tabs.Screen name="memoria" options={{ href: null }} />

      <Tabs.Screen
        name="tu"
        options={{
          title: "Tú",
          tabBarIcon: ({ color, focused }) => (
            // Persona: círculo (cabeza) + semicírculo (base/hombros).
            <View style={{ width: 16, height: 16, alignItems: "center" }}>
              <View
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  borderWidth: 2,
                  borderColor: color,
                  backgroundColor: focused ? color : "transparent",
                }}
              />
              <View
                style={{
                  width: 14,
                  height: 7,
                  borderTopLeftRadius: 7,
                  borderTopRightRadius: 7,
                  borderWidth: 2,
                  borderBottomWidth: 0,
                  borderColor: color,
                  backgroundColor: focused ? color : "transparent",
                  marginTop: 1,
                }}
              />
            </View>
          ),
        }}
      />
    </Tabs>
  );
}
