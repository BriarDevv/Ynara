import { useRouter } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button } from "@/components/ui/Button";
import { LivingField } from "@/components/ui/LivingField";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";

/**
 * Reset de contraseña (maqueta). No envía nada: muestra un mensaje neutro (no
 * revela si el email existe). El envío real (mail con link) llega con el backend.
 */
export function ForgotPasswordScreen() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="aurora" />
      <SafeAreaView className="flex-1" edges={["top", "bottom"]}>
        <ScrollView
          contentContainerClassName="flex-1 justify-center gap-6 px-6"
          keyboardShouldPersistTaps="handled"
        >
          <View className="gap-2">
            <Text className="text-title font-display text-ink-deep">¿Olvidaste tu contraseña?</Text>
            <Text className="text-body text-ink-soft">
              Poné tu email y te mandamos un enlace para resetearla.
            </Text>
          </View>

          {sent ? (
            <View className="gap-4">
              <View className="rounded-lg border border-border bg-bg p-4">
                <Text className="text-body text-ink-soft">
                  Si existe una cuenta con ese email, te mandamos un enlace para resetear la
                  contraseña. Revisá tu correo.
                </Text>
              </View>
              <Button variant="secondary" onPress={() => router.back()}>
                Volver
              </Button>
            </View>
          ) : (
            <View className="gap-5">
              <TextField
                label="EMAIL"
                placeholder="vos@ejemplo.com"
                value={email}
                onChangeText={setEmail}
                autoFocus
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
                returnKeyType="go"
                onSubmitEditing={() => setSent(true)}
              />
              <Button
                variant="primary"
                onPress={() => setSent(true)}
                disabled={email.trim().length === 0}
              >
                Enviar enlace
              </Button>
              <Button variant="subtle" onPress={() => router.back()} className="self-center">
                Volver
              </Button>
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
