import { logIn } from "@ynara/core/features/auth";
import { LoginRequestSchema } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Image, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button } from "@/components/ui/Button";
import { LivingField } from "@/components/ui/LivingField";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
// Side-effect: asegura configureApi (baseUrl + token) antes del primer request.
import "@/lib/api";
import { env } from "@/lib/env";
import { useOnboardingStore } from "@/stores/onboarding";
import { useOnboardingStepStore } from "@/stores/onboardingStep";
import { useUserStore } from "@/stores/user";
import logo from "../../../assets/splash-icon.png";
import { authErrorMessage } from "./errors";
import { recoverProfileFromLogin } from "./recoverProfileFromLogin";

/** Usuario fake para el OAuth de maqueta (dev, ENABLE_MOCKS). */
const MOCK_OAUTH_USER_ID = "0193f000-0000-7000-8000-0000000000bb";

/**
 * Bienvenida (entrada sin sesión): logo + nombre arriba, y abajo login email/clave
 * + OAuth (maqueta) + olvidé contraseña + crear cuenta. Layout sin scroll: dos
 * bloques flex reparten el alto (nunca desborda). Fondo vivo constellation.
 *
 * El login usa `logIn` de core (mock-first vía el seam de fetch). El OAuth se
 * simula sólo con ENABLE_MOCKS (dev); con el flag off muestra "próximamente"
 * (queda listo para cablear el OAuth real). Login/OAuth = usuario que vuelve →
 * Hoy directo.
 */
export function WelcomeScreen() {
  const router = useRouter();
  const setAuth = useUserStore((s) => s.setAuth);
  const completeOnboarding = useUserStore((s) => s.completeOnboarding);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string>();
  const [passwordError, setPasswordError] = useState<string>();
  const [submitError, setSubmitError] = useState<string>();
  const [pending, setPending] = useState(false);

  // Entrada del OAuth de maqueta (sin LoginResult del backend): trata al usuario
  // como ya onboardeado y entra. El login real usa la rama de `onLogin`.
  const enterApp = (session: { userId: string; token: string }) => {
    setAuth({ userId: session.userId, token: session.token });
    completeOnboarding();
    router.replace("/");
  };

  const onLogin = async () => {
    setEmailError(undefined);
    setPasswordError(undefined);
    setSubmitError(undefined);
    const parsed = LoginRequestSchema.safeParse({ email: email.trim(), password });
    if (!parsed.success) {
      const fields = parsed.error.flatten().fieldErrors;
      setEmailError(fields.email?.[0]);
      setPasswordError(fields.password?.[0]);
      return;
    }
    setPending(true);
    try {
      const result = await logIn(parsed.data);
      if (result.user.onboarding_completed) {
        // Usuario que YA onboardeó (otro dispositivo): hidratar perfil + a11y
        // desde el `me` (gap-fill, sin pisar lo local) y entrar sin rehacerlo.
        recoverProfileFromLogin(result);
        router.replace("/");
        return;
      }
      // Cuenta sin onboarding terminado: NO marcar completo (el guard de
      // `(tabs)/_layout` rebota a /welcome). Se pasa el token al draft y se manda a
      // completar el wizard, saltando el paso de signup (ya tiene cuenta) → arranca
      // en "nombre".
      useOnboardingStore.getState().setAuth({
        userId: result.userId,
        token: result.token,
        mode: "login",
      });
      useOnboardingStepStore.getState().setStep("nombre");
      router.replace("/onboarding");
    } catch (error) {
      setSubmitError(authErrorMessage(error, "login"));
      setPending(false);
    }
  };

  const onOAuth = (provider: "google" | "apple") => {
    setSubmitError(undefined);
    if (!env.EXPO_PUBLIC_ENABLE_MOCKS) {
      // OAuth real (SDK nativo Google/Apple + backend) pendiente.
      setSubmitError(
        `Vinculación con ${provider === "google" ? "Google" : "Apple"}: próximamente.`,
      );
      return;
    }
    // Maqueta (dev): simula una cuenta vinculada y entra.
    enterApp({ userId: MOCK_OAUTH_USER_ID, token: "mock-oauth-token" });
  };

  return (
    <View className="flex-1 bg-bg-canvas">
      <LivingField variant="aurora" />
      <SafeAreaView className="flex-1" edges={["top", "bottom"]}>
        <View className="flex-1 px-6 py-4">
          {/* Logo + nombre: centrado, un poco hacia arriba. El logo usa el icono
              con tile blanco por ahora; falta un PNG con fondo transparente. */}
          <View className="flex-[2] items-center justify-center gap-4">
            <Image source={logo} style={{ width: 88, height: 88, borderRadius: 20 }} />
            <View className="items-center gap-1">
              <Text className="text-hero font-display text-ink-deep">Ynara</Text>
              <Text className="text-body text-ink-soft">Tu asistente que recuerda con vos.</Text>
            </View>
          </View>

          {/* Login + OAuth + crear cuenta */}
          <View className="flex-[3] justify-center gap-6">
            <View className="gap-5">
              <TextField
                label="EMAIL"
                placeholder="vos@ejemplo.com"
                value={email}
                onChangeText={(t) => {
                  setEmail(t);
                  setEmailError(undefined);
                  setSubmitError(undefined);
                }}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
                error={emailError}
              />
              <TextField
                label="CONTRASEÑA"
                placeholder="Tu contraseña"
                value={password}
                onChangeText={(t) => {
                  setPassword(t);
                  setPasswordError(undefined);
                  setSubmitError(undefined);
                }}
                secureTextEntry
                autoCapitalize="none"
                autoComplete="current-password"
                returnKeyType="go"
                onSubmitEditing={onLogin}
                error={passwordError}
              />
              <Button
                variant="subtle"
                onPress={() => router.push("/forgot-password")}
                className="self-end"
              >
                Olvidé mi contraseña
              </Button>
              {submitError ? <Text className="text-body-sm text-error">{submitError}</Text> : null}
              <Button variant="primary" onPress={onLogin} disabled={pending}>
                {pending ? "Entrando…" : "Entrar"}
              </Button>
            </View>

            <View className="flex-row items-center gap-3">
              <View className="h-px flex-1 bg-border" />
              <Text className="text-caption text-ink-soft">o</Text>
              <View className="h-px flex-1 bg-border" />
            </View>

            <View className="gap-3">
              <Button variant="secondary" onPress={() => onOAuth("google")}>
                Continuar con Google
              </Button>
              <Button variant="secondary" onPress={() => onOAuth("apple")}>
                Continuar con Apple
              </Button>
            </View>

            <View className="flex-row items-baseline justify-center gap-2">
              <Text className="text-body-sm text-ink-soft">¿No tenés cuenta?</Text>
              <Button variant="subtle" onPress={() => router.push("/onboarding")}>
                Crear cuenta
              </Button>
            </View>
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}
