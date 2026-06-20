import { useMutation } from "@tanstack/react-query";
import { type AuthSession, signUp } from "@ynara/core/features/auth";
import { SignupRequestSchema } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { Button } from "@/components/ui/Button";
import { Text } from "@/components/ui/Text";
import { TextField } from "@/components/ui/TextField";
// Side-effect: configura el cliente API antes de la primera llamada.
import "@/lib/api";
import { useOnboardingStore } from "@/stores/onboarding";
import { authErrorMessage } from "../../auth/errors";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { AUTH_STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

/**
 * Step 1 del onboarding: **crear cuenta** (signup). El login vive en `/welcome`;
 * acá sólo se crea cuenta. El token resultante va al draft store; al cerrar el
 * wizard `useCompleteOnboarding` lo pasa al user store.
 */
export function AuthStep() {
  const router = useRouter();
  const { next } = useOnboardingNav();
  const setAuth = useOnboardingStore((s) => s.setAuth);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string>();
  const [passwordError, setPasswordError] = useState<string>();
  const [submitError, setSubmitError] = useState<string>();

  const copy = AUTH_STEP_COPY.signup;

  const mutation = useMutation({
    mutationFn: (creds: { email: string; password: string }): Promise<AuthSession> => signUp(creds),
    onSuccess: (session) => {
      setAuth({ userId: session.userId, token: session.token, mode: "signup" });
      next();
    },
    onError: (error) => setSubmitError(authErrorMessage(error, "signup")),
  });

  const onSubmit = () => {
    setEmailError(undefined);
    setPasswordError(undefined);
    setSubmitError(undefined);
    const parsed = SignupRequestSchema.safeParse({ email: email.trim(), password });
    if (!parsed.success) {
      const fields = parsed.error.flatten().fieldErrors;
      setEmailError(fields.email?.[0]);
      setPasswordError(fields.password?.[0]);
      return;
    }
    mutation.mutate(parsed.data);
  };

  const pending = mutation.isPending;

  return (
    <StepShell
      eyebrow="Paso 1 — Cuenta"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={
        <StepFooter
          onNext={onSubmit}
          nextLabel={pending ? "Creando…" : "Crear cuenta"}
          nextDisabled={pending}
        />
      }
    >
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
          autoFocus
          autoCapitalize="none"
          keyboardType="email-address"
          autoComplete="email"
          error={emailError}
        />
        <TextField
          label="CONTRASEÑA"
          placeholder="Mínimo 8 caracteres"
          value={password}
          onChangeText={(t) => {
            setPassword(t);
            setPasswordError(undefined);
            setSubmitError(undefined);
          }}
          secureTextEntry
          autoCapitalize="none"
          autoComplete="new-password"
          returnKeyType="go"
          onSubmitEditing={onSubmit}
          error={passwordError}
        />
        {submitError ? <Text className="text-body-sm text-error">{submitError}</Text> : null}
      </View>

      <View className="flex-row items-baseline gap-2">
        <Text className="text-body-sm text-ink-soft">¿Ya tenés cuenta?</Text>
        <Button variant="subtle" onPress={() => router.replace("/welcome")}>
          Iniciar sesión
        </Button>
      </View>
    </StepShell>
  );
}
