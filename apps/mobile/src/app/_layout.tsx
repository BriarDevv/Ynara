import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import "../global.css";
// Side-effect: configura el cliente API (baseUrl + token) una vez al boot, antes
// de que cualquier pantalla haga un request. Ver apps/mobile/src/lib/api.ts.
import "@/lib/api";
import { Providers } from "./providers";

export default function RootLayout() {
  return (
    <Providers>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }} />
    </Providers>
  );
}
