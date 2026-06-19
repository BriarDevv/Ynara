"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { forwardRef, type InputHTMLAttributes, Suspense, useEffect, useId, useState } from "react";
import { type SubmitHandler, useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LivingField } from "@/components/ui/LivingField";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
import { loginErrorMessage, useLogin } from "@/features/auth/hooks/useLogin";
import { LoginRequest, type LoginRequestT } from "@/features/auth/schemas";
import { useThemeStore } from "@/stores/theme";

/**
 * Login del panel admin — pantalla PÚBLICA, fuera del route group `(panel)`
 * (no monta el `AdminShell`, no tiene guard de token: es la puerta de entrada).
 *
 * Editorial y consistente con la marca: lockup oficial arriba, `LivingField`
 * sutil de atmósfera, una `Card` central con el form (email + password) sobre
 * react-hook-form + Zod (`LoginRequest`). Tema Noche por default (igual que el
 * resto del panel). En éxito redirige a "/".
 *
 * Client component: usa stores, form, router y efectos. El form se aísla en
 * `LoginForm` para envolverlo en `<Suspense>` (lo exige `useSearchParams`).
 */
export default function LoginPage() {
  // Lockup por fondo: mono-light sobre Noche, color sobre claro. `mounted` evita
  // el mismatch de hidratación (el server siempre renderiza el default Noche).
  const dark = useThemeStore((s) => s.theme === "dark");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const wordmarkVariant = mounted && dark ? "mono-light" : "color";

  return (
    <main className="relative isolate flex min-h-screen flex-col items-center justify-center px-6 py-16">
      {/* Atmósfera de marca: campo vivo sutil, detrás de todo. */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-[var(--z-field)]">
        <LivingField variant="depth" density="sutil" />
      </div>

      <div className="flex w-full max-w-[400px] flex-col items-center gap-8">
        <YnaraWordmark height={28} variant={wordmarkVariant} />

        <Card className="w-full">
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </Card>

        <p className="text-caption text-[var(--color-ink-muted)]">
          Panel interno · Acceso restringido
        </p>
      </div>
    </main>
  );
}

/**
 * Form de login. Vive separado del page por el `<Suspense>` que exige
 * `useSearchParams` (Next 16): el `?reason=forbidden` con el que el guard de
 * `/v1/admin/*` rebota a un user logueado-pero-no-admin pinta el aviso de
 * permisos.
 */
function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");
  const mutation = useLogin();

  const form = useForm<LoginRequestT>({
    resolver: zodResolver(LoginRequest),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
  });

  const onSubmit: SubmitHandler<LoginRequestT> = (values) => {
    mutation.mutate(values, { onSuccess: () => router.replace("/") });
  };

  // El mensaje de "permisos de admin" (rebote del guard) se muestra hasta que
  // el operador vuelve a intentar; el error de credenciales gana si existe.
  const serverError = mutation.isError ? loginErrorMessage(mutation.error) : null;
  const forbiddenNotice =
    reason === "forbidden" && !serverError ? "Necesitás permisos de admin" : null;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-subtitle text-[var(--color-ink-deep)]">Iniciá sesión</h1>
        <p className="text-body-sm text-[var(--color-ink-soft)]">
          Acceso al panel de soberanía de Ynara.
        </p>
      </header>

      <div className="flex flex-col gap-5">
        <Field
          label="EMAIL"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="vos@ynara.app"
          error={form.formState.errors.email?.message}
          {...form.register("email")}
        />
        <Field
          label="CONTRASEÑA"
          type="password"
          autoComplete="current-password"
          placeholder="Tu contraseña"
          error={form.formState.errors.password?.message}
          {...form.register("password")}
        />
      </div>

      {forbiddenNotice ? (
        <p role="status" className="text-body-sm text-[var(--color-ink-soft)]">
          {forbiddenNotice}
        </p>
      ) : null}
      {serverError ? (
        <p role="alert" className="text-body-sm text-[var(--color-error)]">
          {serverError}
        </p>
      ) : null}

      <Button type="submit" fullWidth disabled={mutation.isPending}>
        {mutation.isPending ? "Entrando…" : "Entrar"}
      </Button>
    </form>
  );
}

/**
 * Campo de texto inline del login. El panel no tiene un primitivo `TextField`
 * propio todavía (las 6 pantallas son read-only); este es el único form del
 * app, así que el input vive acá con su label + error accesibles — mismos
 * tokens que el `TextField` de web (border default → strong en hover; error en
 * `--color-error`; el focus-ring global aplica el accent encima).
 */
type FieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & {
  label: string;
  /** Mensaje de error inline. Presente ⇒ marca el campo inválido. */
  error?: string;
};

const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, id, ...rest },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const errorId = error ? `${fieldId}-error` : undefined;
  const invalid = Boolean(error);

  return (
    <div className="flex w-full flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-caption text-[var(--color-ink-soft)]">
        {label}
      </label>
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={invalid || undefined}
        aria-describedby={errorId}
        className={`text-body w-full rounded-[var(--radius-md)] border bg-[var(--color-bg)] px-4 py-3.5 text-[var(--color-ink)] placeholder:text-[var(--color-ink-soft)] transition-[border-color,background-color] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] ${
          invalid
            ? "border-[var(--color-error)]"
            : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]"
        }`}
        {...rest}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-body-sm text-[var(--color-error)]">
          {error}
        </p>
      ) : null}
    </div>
  );
});
