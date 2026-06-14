import { useMutation } from "@tanstack/react-query";
import { type AuthSession, logIn, signUp } from "@ynara/core/features/auth";
import { LoginRequestSchema, SignupRequestSchema } from "@ynara/shared-schemas";
import { useState } from "react";
import { Text, View } from "react-native";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
// Import con side-effect: configura el cliente API (baseUrl + token) y reexpone
// ApiError. Garantiza que `configureApi` corrió antes de la primera llamada.
import { ApiError } from "@/lib/api";
import { useOnboardingStore } from "@/stores/onboarding";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { AUTH_STEP_COPY } from "../constants";
import { useOnboardingNav } from "../useOnboardingNav";

type AuthMode = "signup" | "login";

/**
 * Step 1 del onboarding (mobile): crear cuenta o iniciar sesión contra el
 * backend real. Espejo del `AuthStep` de la web, portado al patrón mobile
 * (useState + safeParse + `useMutation`, sin react-hook-form). El token
 * resultante va al draft store; `useCompleteOnboarding` lo traslada al user
 * store al cerrar el flujo.
 *
 * Sin "cuenta efímera" (la web la tiene mockeada; el backend real no expone
 * ese flujo todavía) y sin `display_name` en el register: el nombre se pide en
 * el step siguiente y vive client-side (no hay endpoint para sincronizarlo).
 */
export function AuthStep() {
  const { next } = useOnboardingNav();
  const setAuth = useOnboardingStore((s) => s.setAuth);

  const [mode, setMode] = useState<AuthMode>("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string>();
  const [passwordError, setPasswordError] = useState<string>();
  const [submitError, setSubmitError] = useState<string>();

  const copy = mode === "signup" ? AUTH_STEP_COPY.signup : AUTH_STEP_COPY.login;

  const mutation = useMutation({
    mutationFn: (creds: { email: string; password: string }): Promise<AuthSession> =>
      mode === "signup" ? signUp(creds) : logIn(creds),
    onSuccess: (session) => {
      setAuth({ userId: session.userId, token: session.token, mode });
      next();
    },
    onError: (error) => setSubmitError(authErrorMessage(error, mode)),
  });

  const clearErrors = () => {
    setEmailError(undefined);
    setPasswordError(undefined);
    setSubmitError(undefined);
  };

  const onSubmit = () => {
    clearErrors();
    const schema = mode === "signup" ? SignupRequestSchema : LoginRequestSchema;
    const parsed = schema.safeParse({ email: email.trim(), password });
    if (!parsed.success) {
      const fields = parsed.error.flatten().fieldErrors;
      setEmailError(fields.email?.[0]);
      setPasswordError(fields.password?.[0]);
      return;
    }
    mutation.mutate(parsed.data);
  };

  const toggleMode = () => {
    setMode((m) => (m === "signup" ? "login" : "signup"));
    clearErrors();
  };

  const pending = mutation.isPending;
  const cta =
    mode === "signup" ? (pending ? "Creando…" : "Crear cuenta") : pending ? "Entrando…" : "Entrar";

  return (
    <StepShell
      eyebrow="Paso 1 — Cuenta"
      title={copy.title}
      subtitle={copy.subtitle}
      footer={<StepFooter onNext={onSubmit} nextLabel={cta} nextDisabled={pending} />}
    >
      <View className="gap-5">
        <TextField
          label="EMAIL"
          placeholder="vos@ejemplo.com"
          value={email}
          onChangeText={(t) => {
            setEmail(t);
            if (emailError || submitError) {
              setEmailError(undefined);
              setSubmitError(undefined);
            }
          }}
          autoFocus
          autoCapitalize="none"
          keyboardType="email-address"
          autoComplete="email"
          error={emailError}
        />
        <TextField
          label="CONTRASEÑA"
          placeholder={mode === "signup" ? "Mínimo 8 caracteres" : "Tu contraseña"}
          value={password}
          onChangeText={(t) => {
            setPassword(t);
            if (passwordError || submitError) {
              setPasswordError(undefined);
              setSubmitError(undefined);
            }
          }}
          secureTextEntry
          autoCapitalize="none"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          returnKeyType="go"
          onSubmitEditing={onSubmit}
          error={passwordError}
        />
        {submitError ? <Text className="text-body-sm text-error">{submitError}</Text> : null}
      </View>

      <View className="flex-row items-baseline gap-2">
        <Text className="text-body-sm text-ink-soft">
          {mode === "signup" ? "¿Ya tenés cuenta?" : "¿Sos nuevo?"}
        </Text>
        <Button variant="subtle" onPress={toggleMode}>
          {mode === "signup" ? "Iniciar sesión" : "Crear cuenta"}
        </Button>
      </View>
    </StepShell>
  );
}

/** Mapea el error de la mutation a un mensaje accionable para el usuario. */
function authErrorMessage(error: unknown, mode: AuthMode): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Email o contraseña incorrectos.";
    if (error.status === 409 || error.status === 400) {
      return mode === "signup"
        ? "Ese email ya tiene una cuenta. Iniciá sesión."
        : "No pudimos validar tus datos.";
    }
    if (error.status === 422) return "Revisá el email y la contraseña.";
  }
  return "Algo no anduvo. Probá de nuevo en un momento.";
}
