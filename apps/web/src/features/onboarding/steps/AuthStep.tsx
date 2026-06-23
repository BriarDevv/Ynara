"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { type AuthSession, logIn, signUp } from "@ynara/core/features/auth";
import { useMemo, useState } from "react";
import { type SubmitHandler, useForm } from "react-hook-form";
import type { z } from "zod";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
// Importar desde `@/lib/api` corre el side-effect que configura el cliente HTTP
// de core (base URL + token provider) antes de la primera llamada signUp/logIn.
import { ApiError } from "@/lib/api";
import { qk } from "@/lib/queryKeys";
import { StepFooter } from "../components/StepFooter";
import { StepShell } from "../components/StepShell";
import { AUTH_STEP_COPY } from "../constants";
import { useOnboardingNav } from "../hooks/useOnboardingNav";
import { type ApiErrorBody, LoginRequestSchema, SignupRequestSchema } from "../schemas";
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
  const queryClient = useQueryClient();
  const setAuth = useOnboardingStore((s) => s.setAuth);
  const startEphemeral = useOnboardingStore((s) => s.startEphemeral);

  const form = useForm<SignupValues>({
    resolver: zodResolver(SignupRequestSchema),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
  });

  // 2-step real contra el backend: signUp = register THEN token (core).
  // register devuelve el UserOut (sin token); token() devuelve access_token.
  // El refresh_token que devuelve token() se ignora por ahora (ver issue de
  // refresh wiring): AuthSession solo expone { userId, token }.
  // La invalidación de cache vive en onSuccess vía `invalidateUserScopedQueries`
  // (helper); react-doctor no la ve a través del wrapper → falso positivo.
  // react-doctor-disable-next-line react-doctor/query-mutation-missing-invalidation
  const mutation = useMutation({
    mutationFn: (values: SignupValues): Promise<AuthSession> => signUp(values),
    onSuccess: (session) => {
      setAuth({ userId: session.userId, token: session.token, mode: "signup" });
      // No hay query "me" en core (el perfil vive en el store), pero esto cruza
      // el borde de identidad: limpiamos los caches por usuario para que las
      // vistas posteriores no muestren datos de un estado previo.
      invalidateUserScopedQueries(queryClient);
      next();
    },
    onError: (error) => bindServerError(error, form.setError),
  });

  const onSubmit: SubmitHandler<SignupValues> = (values) => {
    mutation.mutate(values);
  };

  const handleEphemeral = () => {
    const id = `ephemeral-${Date.now()}`;
    startEphemeral({ userId: id, token: `ephemeral-${id}` });
    next();
  };

  // Memoizado: StepFooter es un hijo que recibe JSX por prop; sin memo recibiría
  // un nodo nuevo en cada render y se redibujaría aunque nada relevante cambie.
  const customNext = useMemo(
    () => (
      <Button
        type="submit"
        fullWidth
        disabled={mutation.isPending}
        form="signup-form"
        className="sm:w-auto sm:min-w-[220px]"
      >
        {mutation.isPending ? "Creando…" : "Crear cuenta"}
      </Button>
    ),
    [mutation.isPending],
  );

  return (
    <StepShell
      hero
      eyebrow="Paso 1 — Cuenta"
      title={AUTH_STEP_COPY.signup.title}
      subtitle={AUTH_STEP_COPY.signup.subtitle}
      footer={<StepFooter customNext={customNext} />}
    >
      <form
        id="signup-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-5"
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

      {/*
        Bloque secundario, alineado a la izquierda — mismo eje que el form
        y el título. Antes "Probar sin cuenta" y la nota quedaban centrados,
        rompiendo la grilla del step.

        La nota va en una línea aparte (text-caption) en lugar de inline
        con punto separador: mobile no la cortaba bien y la jerarquía
        queda más clara (acción primero, explicación abajo).
      */}
      <div className="flex flex-col gap-3 pt-2">
        <AuthModeSwitchLink mode="signup" onChange={onSwitch} />
        <div className="flex flex-col gap-1">
          <Button variant="subtle" onClick={handleEphemeral} className="text-body-sm self-start">
            Probar sin cuenta
          </Button>
          <p className="text-caption text-[var(--color-ink-soft)]">
            Cuenta efímera — no se guarda entre sesiones.
          </p>
        </div>
      </div>
    </StepShell>
  );
}

// ============================================================
// Login
// ============================================================

/**
 * LoginForm intencionalmente no muestra "Probar sin cuenta": la cuenta
 * efímera es para users nuevos sin credenciales (flujo signup). Si
 * el user llegó al tab login, asumimos que tiene cuenta real.
 */
function LoginForm({ onSwitch }: { onSwitch: () => void }) {
  const { next } = useOnboardingNav("auth");
  const queryClient = useQueryClient();
  const setAuth = useOnboardingStore((s) => s.setAuth);

  const form = useForm<LoginValues>({
    resolver: zodResolver(LoginRequestSchema),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
  });

  // logIn de core = token() + me() (para resolver el userId). Devuelve la
  // AuthSession lista para el draft store; el refresh_token se ignora por ahora.
  // La invalidación de cache vive en onSuccess vía `invalidateUserScopedQueries`
  // (helper); react-doctor no la ve a través del wrapper → falso positivo.
  // react-doctor-disable-next-line react-doctor/query-mutation-missing-invalidation
  const mutation = useMutation({
    mutationFn: (values: LoginValues): Promise<AuthSession> => logIn(values),
    onSuccess: (session) => {
      setAuth({ userId: session.userId, token: session.token, mode: "login" });
      // Login cruza el borde de identidad: limpiamos los caches por usuario
      // para que las vistas posteriores no muestren datos de otra sesión.
      invalidateUserScopedQueries(queryClient);
      next();
    },
    onError: (error) => bindServerError(error, form.setError),
  });

  const onSubmit: SubmitHandler<LoginValues> = (values) => mutation.mutate(values);

  // Memoizado: ver nota en SignupForm (StepFooter recibe JSX por prop).
  const customNext = useMemo(
    () => (
      <Button
        type="submit"
        fullWidth
        disabled={mutation.isPending}
        form="login-form"
        className="sm:w-auto sm:min-w-[220px]"
      >
        {mutation.isPending ? "Entrando…" : "Entrar"}
      </Button>
    ),
    [mutation.isPending],
  );

  return (
    <StepShell
      hero
      eyebrow="Paso 1 — Cuenta"
      title={AUTH_STEP_COPY.login.title}
      subtitle={AUTH_STEP_COPY.login.subtitle}
      footer={<StepFooter customNext={customNext} />}
    >
      <form
        id="login-form"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="flex flex-col gap-5"
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

      <div className="pt-2">
        <AuthModeSwitchLink mode="login" onChange={onSwitch} />
      </div>
    </StepShell>
  );
}

// ============================================================
// Sub-componentes
// ============================================================

/**
 * Invalida los caches de TanStack scoped por usuario tras un cambio de
 * identidad (signup/login). No hay query "me" en core (el perfil vive en el
 * user store), pero hoy/agenda/memoria/sesiones sí cachean datos por usuario:
 * limpiarlos evita que la siguiente vista muestre datos de otra sesión.
 * Invalidación por prefijo (TanStack matchea por inicio del array).
 */
function invalidateUserScopedQueries(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: qk.today.tasks() });
  queryClient.invalidateQueries({ queryKey: qk.today.suggestions() });
  queryClient.invalidateQueries({ queryKey: qk.today.recap() });
  queryClient.invalidateQueries({ queryKey: qk.agenda.all() });
  queryClient.invalidateQueries({ queryKey: qk.memory.all() });
  queryClient.invalidateQueries({ queryKey: qk.sessions.all() });
}

/**
 * Switch textual entre signup ↔ login. Intencionalmente NO es un
 * `role="tablist"`: no hay paneles separados, solo dos modos del mismo
 * form. Si en algún momento se rediseña como tabs reales (con role=tab
 * + aria-controls + arrow-key nav), renombrar a `AuthModeTabs`.
 *
 * Alineado a la izquierda — antes quedaba "centrado" mezclado con un
 * título a la izquierda, rompiendo la grilla.
 */
function AuthModeSwitchLink({ mode, onChange }: { mode: AuthMode; onChange: () => void }) {
  return (
    <div className="flex items-baseline gap-2 text-body-sm text-[var(--color-ink-soft)]">
      <span>{mode === "signup" ? "¿Ya tenés cuenta?" : "¿Sos nuevo?"}</span>
      <Button variant="subtle" onClick={onChange} className="text-body-sm">
        {mode === "signup" ? "Iniciar sesión" : "Crear cuenta"}
      </Button>
    </div>
  );
}

/**
 * Toma un error de la mutation y lo pega a los campos del form si
 * coincide con un `field` del ApiErrorBody. Si es un error sin field,
 * va al campo `password` como fallback (la decisión de UX es no exponer
 * "este email no existe" para no enumerar).
 *
 * El backend real responde FastAPI-style: el 409 de `/register` (email ya
 * registrado) y el 401 uniforme de `/token` traen `{ detail: string }` sin
 * `field`, así que caen al fallback a `password` — que es justamente lo que
 * queremos para no enumerar cuentas.
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
