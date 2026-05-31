"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { type SubmitHandler, useForm } from "react-hook-form";
import type { z } from "zod";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { ApiError, api } from "@/lib/api";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { AUTH_STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import {
  type ApiErrorBody,
  AuthResponseSchema,
  LoginRequestSchema,
  SignupRequestSchema,
} from "../schemas";
import { useOnboardingStore } from "../store";

type AuthMode = "signup" | "login";

type SignupValues = z.infer<typeof SignupRequestSchema>;
type LoginValues = z.infer<typeof LoginRequestSchema>;

export function AuthStep() {
  const [mode, setMode] = useState<AuthMode>("signup");
  return mode === "signup" ? (
    <SignupForm onSwitch={() => setMode("login")} />
  ) : (
    <LoginForm onSwitch={() => setMode("signup")} />
  );
}

// ============================================================
// Signup
// ============================================================

function SignupForm({ onSwitch }: { onSwitch: () => void }) {
  const { next } = useOnboardingNav("auth");
  const setAuth = useOnboardingStore((s) => s.setAuth);
  const startEphemeral = useOnboardingStore((s) => s.startEphemeral);

  const form = useForm<SignupValues>({
    resolver: zodResolver(SignupRequestSchema),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
  });

  const mutation = useMutation({
    mutationFn: async (values: SignupValues) => {
      const raw = await api.post<unknown>("/v1/auth/signup", values);
      return AuthResponseSchema.parse(raw);
    },
    onSuccess: (response) => {
      setAuth({ userId: response.userId, token: response.token, mode: "signup" });
      next();
    },
    onError: (error) => bindServerError(error, form.setError),
  });

  const onSubmit: SubmitHandler<SignupValues> = (values) => {
    mutation.mutate(values);
  };

  return (
    <StepShell
      variant="editorial"
      title={AUTH_STEP_COPY.signup.title}
      subtitle={AUTH_STEP_COPY.signup.subtitle}
      footer={
        <StepFooter
          customNext={
            <Button
              type="submit"
              fullWidth
              disabled={mutation.isPending}
              form="signup-form"
              className="sm:w-auto sm:min-w-[200px]"
            >
              {mutation.isPending ? "Creando…" : "Crear cuenta"}
            </Button>
          }
        />
      }
    >
      <AuthModeSwitchLink mode="signup" onChange={onSwitch} />
      <form
        id="signup-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-4"
      >
        <TextField
          label="EMAIL"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="vos@ejemplo.com"
          error={form.formState.errors.email?.message}
          {...form.register("email")}
        />
        <TextField
          label="CONTRASEÑA"
          type="password"
          autoComplete="new-password"
          placeholder="Mínimo 8 caracteres"
          error={form.formState.errors.password?.message}
          {...form.register("password")}
        />
      </form>
      <EphemeralButton
        onContinue={() => {
          const id = `ephemeral-${Date.now()}`;
          startEphemeral({ userId: id, token: `ephemeral-${id}` });
          next();
        }}
      />
    </StepShell>
  );
}

// ============================================================
// Login
// ============================================================

/**
 * LoginForm intencionalmente no muestra `EphemeralButton`: la cuenta
 * efímera es para users nuevos sin credenciales (flujo signup). Si
 * el user llegó al tab login, asumimos que tiene cuenta real.
 */
function LoginForm({ onSwitch }: { onSwitch: () => void }) {
  const { next } = useOnboardingNav("auth");
  const setAuth = useOnboardingStore((s) => s.setAuth);

  const form = useForm<LoginValues>({
    resolver: zodResolver(LoginRequestSchema),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
  });

  const mutation = useMutation({
    mutationFn: async (values: LoginValues) => {
      const raw = await api.post<unknown>("/v1/auth/login", values);
      return AuthResponseSchema.parse(raw);
    },
    onSuccess: (response) => {
      setAuth({ userId: response.userId, token: response.token, mode: "login" });
      next();
    },
    onError: (error) => bindServerError(error, form.setError),
  });

  const onSubmit: SubmitHandler<LoginValues> = (values) => mutation.mutate(values);

  return (
    <StepShell
      variant="editorial"
      title={AUTH_STEP_COPY.login.title}
      subtitle={AUTH_STEP_COPY.login.subtitle}
      footer={
        <StepFooter
          customNext={
            <Button
              type="submit"
              fullWidth
              disabled={mutation.isPending}
              form="login-form"
              className="sm:w-auto sm:min-w-[200px]"
            >
              {mutation.isPending ? "Entrando…" : "Entrar"}
            </Button>
          }
        />
      }
    >
      <AuthModeSwitchLink mode="login" onChange={onSwitch} />
      <form
        id="login-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-4"
      >
        <TextField
          label="EMAIL"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="vos@ejemplo.com"
          error={form.formState.errors.email?.message}
          {...form.register("email")}
        />
        <TextField
          label="CONTRASEÑA"
          type="password"
          autoComplete="current-password"
          placeholder="Tu contraseña"
          error={form.formState.errors.password?.message}
          {...form.register("password")}
        />
      </form>
    </StepShell>
  );
}

// ============================================================
// Sub-componentes
// ============================================================

/**
 * Switch textual entre signup ↔ login. Intencionalmente NO es un
 * `role="tablist"`: no hay paneles separados, solo dos modos del mismo
 * form. Si en algún momento se rediseña como tabs reales (con role=tab
 * + aria-controls + arrow-key nav), renombrar a `AuthModeTabs`.
 */
function AuthModeSwitchLink({ mode, onChange }: { mode: AuthMode; onChange: () => void }) {
  return (
    <div className="flex items-center gap-2 text-body-sm text-[var(--color-ink-soft)]">
      <span>{mode === "signup" ? "¿Ya tenés cuenta?" : "¿Sos nuevo?"}</span>
      <button
        type="button"
        onClick={onChange}
        className="text-button rounded-[var(--radius-sm)] px-1 text-[var(--color-accent)] underline-offset-2 hover:underline"
      >
        {mode === "signup" ? "Iniciar sesión" : "Crear cuenta"}
      </button>
    </div>
  );
}

function EphemeralButton({ onContinue }: { onContinue: () => void }) {
  return (
    <div className="mt-2 flex flex-col gap-2">
      <button
        type="button"
        onClick={onContinue}
        className="text-body-sm text-[var(--color-ink-soft)] underline-offset-4 hover:text-[var(--color-ink)] hover:underline"
      >
        Probar sin cuenta
      </button>
      <p className="text-caption text-[var(--color-ink-muted)]">
        Cuenta efímera: tu perfil no se va a guardar entre sesiones.
      </p>
    </div>
  );
}

/**
 * Toma un error de la mutation y lo pega a los campos del form si
 * coincide con un `field` del ApiErrorBody. Si es un error sin field,
 * va al campo `password` como fallback (la decisión de UX es no exponer
 * "este email no existe" para no enumerar).
 */
type SetErrorFn = (name: "email" | "password", value: { message: string }) => void;

function bindServerError(error: unknown, setError: SetErrorFn): void {
  if (!(error instanceof ApiError)) {
    setError("password", {
      message: "Algo no anduvo. Probá de nuevo en un momento.",
    });
    return;
  }
  const body = error.body as Partial<ApiErrorBody> | null;
  if (body && typeof body === "object" && "field" in body && body.field) {
    const field = body.field === "email" ? "email" : "password";
    setError(field, { message: body.detail ?? "Revisá este campo." });
    return;
  }
  setError("password", {
    message: body?.detail ?? "No pudimos validar tus datos. Reintentá.",
  });
}
