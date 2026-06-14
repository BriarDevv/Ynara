import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import "../global.css";
import { Providers } from "./providers";

export default function RootLayout() {
  return (
    <Providers>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }} />
    </Providers>
  );
}
