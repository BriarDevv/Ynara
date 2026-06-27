import { useMemoryExport } from "@ynara/core/features/memory";
import { useUpdateMe } from "@ynara/core/features/profile";
import type { TextSize } from "@ynara/core/stores";
import { DisplayNameSchema } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Share, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { LivingField } from "@/components/ui/LivingField";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
import { Toggle } from "@/components/ui/Toggle";
import { useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";
import { LogoutSheet } from "./components/LogoutSheet";
import { WipeMemorySheet } from "./components/WipeMemorySheet";

// ChipGroup es string-genérico; los valores de retención viajan como strings
// y se convierten a número antes de llamar a la API.
const RETENTION_OPTIONS = [
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
  { value: "180", label: "180 días" },
  { value: "365", label: "1 año" },
] as const satisfies readonly { value: string; label: string }[];

type RetentionStr = "30" | "90" | "180" | "365";

const TEXT_SIZE_OPTIONS: readonly { value: TextSize; label: string }[] = [
  { value: "sm", label: "Chico" },
  { value: "md", label: "Normal" },
  { value: "lg", label: "Grande" },
];

/**
 * Pantalla **Tú** (mobile) — perfil y ajustes post-onboarding. Espeja la lógica
 * de `TuView` de web, adaptada a React Native + NativeWind + expo-router.
 *
 * Secciones:
 * - **Perfil**: editar display_name (→ PATCH /v1/users/me + store).
 * - **Retención**: días de retención de memoria sensible (ChipGroup 30/90/180/365).
 * - **Memoria**: links a /memoria y /buscar, export JSON, borrar toda la memoria.
 * - **Accesibilidad**: textSize / highContrast / motion (espeja A11yStep).
 * - **Cuenta**: cerrar sesión (→ store.reset() + /onboarding).
 */
export function TuScreen() {
  const router = useRouter();

  // ----- User store -----
  const displayNameStored = useUserStore((s) => s.displayName);
  const setDisplayName = useUserStore((s) => s.setDisplayName);
  const reset = useUserStore((s) => s.reset);
  const isEphemeral = useUserStore((s) => s.isEphemeral);

  // ----- A11y store -----
  const textSize = useA11yStore((s) => s.textSize);
  const highContrast = useA11yStore((s) => s.highContrast);
  const motion = useA11yStore((s) => s.motion);
  const setTextSize = useA11yStore((s) => s.setTextSize);
  const setHighContrast = useA11yStore((s) => s.setHighContrast);
  const setMotion = useA11yStore((s) => s.setMotion);

  // ----- Perfil -----
  const [nameInput, setNameInput] = useState(displayNameStored);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);
  const updateMe = useUpdateMe();

  async function handleSaveName() {
    setNameError(null);
    setNameSaved(false);
    const parsed = DisplayNameSchema.safeParse(nameInput);
    if (!parsed.success) {
      setNameError(parsed.error.issues[0]?.message ?? "Nombre inválido");
      return;
    }
    try {
      const out = await updateMe.mutateAsync({ display_name: parsed.data });
      // display_name puede venir null del backend; el store espera string.
      // Fallback vacío, igual que el TuView web.
      setDisplayName(out.display_name ?? "");
      setNameSaved(true);
    } catch {
      setNameError("No pudimos guardar el nombre. Intentá de nuevo.");
    }
  }

  // ----- Retención -----
  // El ChipGroup es string-genérico; convertimos a número antes de la API.
  const [retention, setRetention] = useState<RetentionStr>("365");
  const [retentionSaved, setRetentionSaved] = useState(false);
  const [retentionError, setRetentionError] = useState<string | null>(null);

  async function handleRetentionChange(days: RetentionStr) {
    setRetention(days);
    setRetentionSaved(false);
    setRetentionError(null);
    try {
      await updateMe.mutateAsync({ retention_sensitive_days: Number(days) });
      setRetentionSaved(true);
    } catch {
      setRetentionError("No pudimos guardar. Intentá de nuevo.");
    }
  }

  // ----- Export -----
  const memoryExport = useMemoryExport();
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  async function handleExport() {
    setExportMsg(null);
    try {
      const data = await memoryExport.mutateAsync();
      const total = data.semantic.length + data.episodic.length + data.procedural.length;
      // En mobile no hay descarga de archivo directa; usamos Share para compartir
      // el JSON o mostramos un resumen si Share no es viable.
      // TODO: guardar en el sistema de archivos con expo-file-system cuando sea dep.
      try {
        await Share.share({
          message: JSON.stringify(data, null, 2),
          title: "Mi memoria de Ynara",
        });
      } catch {
        setExportMsg(
          `Export listo: ${total} recuerdos (${data.semantic.length} hechos, ${data.episodic.length} momentos, ${data.procedural.length} costumbres).`,
        );
      }
    } catch {
      setExportMsg("No pudimos exportar tu memoria. Intentá de nuevo.");
    }
  }

  // ----- Wipe sheet -----
  const [wipeOpen, setWipeOpen] = useState(false);

  // ----- Logout -----
  const [logoutOpen, setLogoutOpen] = useState(false);
  function handleLogout() {
    reset();
    router.replace("/welcome");
  }

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="depth" />
      <SafeAreaView className="flex-1" edges={["top"]}>
        <ScrollView contentContainerClassName="gap-6 px-6 py-8">
          {/* Título */}
          <View className="gap-1">
            <Text className="text-title font-display text-ink-deep">Tú</Text>
            <Text className="text-body text-ink-soft">Tu perfil y preferencias de Ynara.</Text>
          </View>

          {/* ──── Sección: Perfil ──── */}
          <View className="gap-4 rounded-xl border border-border bg-bg p-5">
            <Text className="text-caption text-ink-soft">PERFIL</Text>
            <TextField
              label="Nombre"
              value={nameInput}
              onChangeText={(v) => {
                setNameInput(v);
                setNameError(null);
                setNameSaved(false);
              }}
              error={nameError ?? undefined}
              autoCapitalize="words"
              autoCorrect={false}
              placeholder="Tu nombre"
            />
            {nameSaved ? (
              <Text className="text-body-sm text-ink-soft">Nombre guardado.</Text>
            ) : null}
            <Button variant="primary" onPress={handleSaveName} disabled={updateMe.isPending}>
              {updateMe.isPending ? "Guardando…" : "Guardar"}
            </Button>
          </View>

          {/* ──── Sección: Retención ──── */}
          <View className="gap-4 rounded-xl border border-border bg-bg p-5">
            <View className="gap-1">
              <Text className="text-caption text-ink-soft">RETENCIÓN</Text>
              <Text className="text-body-sm text-ink-soft">
                Tiempo que Ynara guarda tus recuerdos sensibles.
                {/* Nota: sin GET /me el valor reflejado es la selección local de esta sesión. */}
              </Text>
            </View>
            <ChipGroup
              options={RETENTION_OPTIONS}
              value={retention}
              onChange={handleRetentionChange}
            />
            {retentionSaved ? (
              <Text className="text-body-sm text-ink-soft">Preferencia guardada.</Text>
            ) : null}
            {retentionError ? (
              <Text className="text-body-sm text-error">{retentionError}</Text>
            ) : null}
          </View>

          {/* ──── Sección: Memoria ──── */}
          <View className="gap-4 rounded-xl border border-border bg-bg p-5">
            <Text className="text-caption text-ink-soft">MEMORIA</Text>

            {/* Links a las pantallas de memoria */}
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push("/memoria")}
              className="flex-row items-center justify-between rounded-lg border border-border bg-bg-soft px-4 py-3 active:opacity-70"
            >
              <Text className="text-body text-ink">Ver timeline de memoria</Text>
              <Text className="text-body text-ink-soft">›</Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              onPress={() => router.push("/buscar")}
              className="flex-row items-center justify-between rounded-lg border border-border bg-bg-soft px-4 py-3 active:opacity-70"
            >
              <Text className="text-body text-ink">Buscar en tu memoria</Text>
              <Text className="text-body text-ink-soft">›</Text>
            </Pressable>

            {/* Export */}
            <Button variant="secondary" onPress={handleExport} disabled={memoryExport.isPending}>
              {memoryExport.isPending ? "Exportando…" : "Exportar mi memoria"}
            </Button>
            {exportMsg ? <Text className="text-body-sm text-ink-soft">{exportMsg}</Text> : null}

            {/* Wipe */}
            <Button variant="ghost" onPress={() => setWipeOpen(true)}>
              Borrar toda mi memoria
            </Button>
          </View>

          {/* ──── Sección: Accesibilidad ──── */}
          <View className="gap-4 rounded-xl border border-border bg-bg p-5">
            <Text className="text-caption text-ink-soft">ACCESIBILIDAD</Text>
            <ChipGroup
              label="TAMAÑO DEL TEXTO"
              options={TEXT_SIZE_OPTIONS}
              value={textSize}
              onChange={setTextSize}
            />
            <Toggle
              label="Alto contraste"
              hint="Bordes y textos más definidos."
              checked={highContrast}
              onChange={setHighContrast}
            />
            <Toggle
              label="Reducir animaciones"
              hint="Menos movimiento en transiciones."
              checked={motion === "reduce"}
              onChange={(on) => setMotion(on ? "reduce" : "auto")}
            />
          </View>

          {/* ──── Sección: Cuenta ──── */}
          <View className="gap-4 rounded-xl border border-border bg-bg p-5">
            <Text className="text-caption text-ink-soft">CUENTA</Text>
            <Button variant="ghost" onPress={() => setLogoutOpen(true)}>
              Cerrar sesión
            </Button>
          </View>
        </ScrollView>

        {/* Sheet de confirmación de wipe */}
        <WipeMemorySheet open={wipeOpen} onClose={() => setWipeOpen(false)} />

        {/* Confirmación de cierre de sesión (auditoría H4) */}
        <LogoutSheet
          open={logoutOpen}
          isEphemeral={isEphemeral}
          onClose={() => setLogoutOpen(false)}
          onConfirm={handleLogout}
        />
      </SafeAreaView>
    </View>
  );
}
