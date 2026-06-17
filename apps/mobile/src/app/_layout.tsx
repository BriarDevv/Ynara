import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import "../global.css";
// Side-effect: polyfill de crypto.randomUUID (RN no lo trae) — lo usa el chat
// store de @ynara/core. Va primero, antes de tocar cualquier store.
import "@/lib/polyfills";
// Side-effect: configura el cliente API (baseUrl + token) una vez al boot, antes
// de que cualquier pantalla haga un request. Ver apps/mobile/src/lib/api.ts.
import "@/lib/api";
import { FONT_MAP } from "@/lib/fonts";
import { Providers } from "./providers";

// Mantiene el splash hasta que las fuentes de marca estén listas (evita el
// "flash" de la fuente del sistema en el primer render).
SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(FONT_MAP);

  useEffect(() => {
    if (fontsLoaded || fontError) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded, fontError]);

  // Espera a las fuentes antes de pintar (con el splash todavía visible).
  if (!fontsLoaded && !fontError) return null;

  return (
    <Providers>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false }} />
    </Providers>
  );
}
