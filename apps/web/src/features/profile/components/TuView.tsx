"use client";

import { DisplayNameSchema } from "@ynara/shared-schemas";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { MODE_BY_ID } from "@/components/ui/modes";
import { TextField } from "@/components/ui/TextField";
import { Toast } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";
import { useMemoryExport } from "@/features/memory/api";
import { useUpdateMe } from "@/features/profile/api";
import { useActiveMode } from "@/hooks/useActiveMode";
import { applyA11yClasses, type TextSize, useA11yStore } from "@/stores/a11y";
import { applyThemeClass, type ThemePreference, useThemeStore } from "@/stores/theme";
import { useUserStore } from "@/stores/user";
import { WipeMemoryDialog } from "./WipeMemoryDialog";

// ---------------------------------------------------------------------------
// Componentes de filas calmas (sin caja, separadas por hairline)
// ---------------------------------------------------------------------------

/**
 * Fila aireada del perfil: ícono opcional + título + subtítulo + acción/chevron.
 * Separada de la fila anterior por un borde hairline (`border-t`) salvo la primera.
 */
function SettingsRow({
  icon,
  title,
  sub,
  action,
  first = false,
  as: Tag = "div",
  onClick,
  href,
}: {
  icon?: React.ReactNode;
  title: string;
  sub?: string;
  action?: React.ReactNode;
  first?: boolean;
  as?: "div" | "button";
  onClick?: () => void;
  href?: string;
}) {
  const rowClass = [
    "flex items-center gap-3 py-4",
    !first ? "border-t border-[var(--color-border)]" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const inner = (
    <>
      {icon && (
        <div
          className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[10px] bg-[var(--color-bg-soft)]"
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-body font-medium text-[var(--color-ink)]">{title}</p>
        {sub && <p className="text-caption mt-0.5 text-[var(--color-ink-soft)]">{sub}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={`${rowClass} w-full`}>
        {inner}
      </Link>
    );
  }

  if (Tag === "button" || onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${rowClass} w-full bg-transparent text-left`}
      >
        {inner}
      </button>
    );
  }

  return <div className={rowClass}>{inner}</div>;
}

/**
 * Grupo de filas calmas con label de sección en caption uppercase.
 */
function SettingsGroup({
  label,
  children,
  dataHeroReveal = true,
}: {
  label: string;
  children: React.ReactNode;
  dataHeroReveal?: boolean;
}) {
  return (
    <section {...(dataHeroReveal ? { "data-hero-reveal": true } : {})}>
      <p className="text-caption mb-1 font-semibold uppercase tracking-widest text-[var(--color-ink-soft)]">
        {label}
      </p>
      <div>{children}</div>
    </section>
  );
}

/**
 * Bloque de a11y con sus 3 controles — mantiene card sutil para agrupar.
 */
function A11yCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-hero-reveal
      className="flex flex-col gap-6 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] p-6"
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Opciones
// ---------------------------------------------------------------------------

const TEXT_SIZE_OPTIONS = [
  { value: "sm" as const, label: "Chico" },
  { value: "md" as const, label: "Normal" },
  { value: "lg" as const, label: "Grande" },
] as const;

const RETENTION_OPTIONS = [
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
  { value: "180", label: "180 días" },
  { value: "365", label: "1 año" },
] as const;

const THEME_OPTIONS = [
  { value: "light" as const, label: "Claro" },
  { value: "dark" as const, label: "Oscuro" },
] as const;

type RetentionValue = "30" | "90" | "180" | "365";

// ---------------------------------------------------------------------------
// Ícono SVG de chevron derecho
// ---------------------------------------------------------------------------

function ChevronRight() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      className="text-[var(--color-ink-faint)]"
    >
      <path
        d="M6 4l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Vista principal
// ---------------------------------------------------------------------------

/**
 * Vista **Tú** — perfil fiel al mockup: presencia (avatar + nombre + plan),
 * filas aireadas calmas, selector de tema Claro/Oscuro, sección de memoria
 * completa, accesibilidad en card sutil, y footer con versión + tagline.
 *
 * Mantiene TODA la funcionalidad existente: editar nombre (`useUpdateMe` +
 * `setDisplayName`), retención, exportar memoria, borrar memoria
 * (`WipeMemoryDialog`), links a /memoria y /buscar, a11y vía `useA11yStore`
 * + `applyA11yClasses`, logout (`useUserStore.reset()` + router).
 */
export function TuView() {
  const router = useRouter();
  const activeMode = useActiveMode();
  const modeDescriptor = MODE_BY_ID[activeMode];

  // Store de usuario
  const displayName = useUserStore((s) => s.displayName);
  const setDisplayName = useUserStore((s) => s.setDisplayName);
  const resetUser = useUserStore((s) => s.reset);

  // Store de tema
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  // Store de a11y
  const textSize = useA11yStore((s) => s.textSize);
  const highContrast = useA11yStore((s) => s.highContrast);
  const motion = useA11yStore((s) => s.motion);
  const setTextSize = useA11yStore((s) => s.setTextSize);
  const setHighContrast = useA11yStore((s) => s.setHighContrast);
  const setMotion = useA11yStore((s) => s.setMotion);

  // Estado local del perfil
  const [nameValue, setNameValue] = useState(displayName ?? "");
  const [nameError, setNameError] = useState<string | null>(null);

  // Retención
  const [retention, setRetention] = useState<RetentionValue>("365");

  // Dialog de wipe
  const [wipeOpen, setWipeOpen] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ message: string; variant: "success" | "error" } | null>(
    null,
  );

  // Mutations
  const updateMe = useUpdateMe();
  const memoryExport = useMemoryExport();

  // Inicial del nombre para el avatar
  const nameInitial = (displayName ?? "U").charAt(0).toUpperCase();

  // Mapeo motion ↔ toggle binario (espeja A11yStep.tsx)
  const osPrefersReduce = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
    [],
  );
  const motionToggleChecked =
    motion === "reduce" || (motion === "auto" && Boolean(osPrefersReduce));

  // ── Handlers de a11y ──────────────────────────────────────────────────────

  function handleTextSize(value: TextSize) {
    setTextSize(value);
    applyA11yClasses({ textSize: value, highContrast, motion });
  }

  function handleHighContrast(on: boolean) {
    setHighContrast(on);
    applyA11yClasses({ textSize, highContrast: on, motion });
  }

  function handleMotion(reduceOn: boolean) {
    const nextMotion = reduceOn ? "reduce" : "auto";
    setMotion(nextMotion);
    applyA11yClasses({ textSize, highContrast, motion: nextMotion });
  }

  // ── Handler de tema ───────────────────────────────────────────────────────

  function handleThemeChange(value: ThemePreference) {
    setTheme(value);
    applyThemeClass({ theme: value });
  }

  // ── Handlers de perfil ────────────────────────────────────────────────────

  async function handleSaveName() {
    const result = DisplayNameSchema.safeParse(nameValue.trim());
    if (!result.success) {
      setNameError(result.error.issues[0]?.message ?? "Nombre inválido");
      return;
    }
    setNameError(null);
    try {
      const updated = await updateMe.mutateAsync({ display_name: result.data });
      setDisplayName(updated.display_name);
      setToast({ message: "Nombre guardado.", variant: "success" });
    } catch {
      setToast({ message: "No se pudo guardar el nombre. Intentá de nuevo.", variant: "error" });
    }
  }

  async function handleRetentionChange(value: RetentionValue) {
    setRetention(value);
    try {
      await updateMe.mutateAsync({ retention_sensitive_days: Number(value) });
      setToast({ message: "Retención actualizada.", variant: "success" });
    } catch {
      setToast({ message: "No se pudo actualizar la retención.", variant: "error" });
    }
  }

  // ── Export de memoria ─────────────────────────────────────────────────────

  async function handleExport() {
    try {
      const data = await memoryExport.mutateAsync();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ynara-memory-export.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setToast({ message: "Export descargado.", variant: "success" });
    } catch {
      setToast({ message: "No se pudo exportar la memoria.", variant: "error" });
    }
  }

  // ── Logout ────────────────────────────────────────────────────────────────

  function handleLogout() {
    resetUser();
    router.push("/onboarding");
  }

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo — variante depth: profundidad pura (blooms, sin partículas) */}
      <LivingField variant="depth" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-8 px-6 pb-10 pt-10">
        {/* ── Presencia: avatar + nombre + plan ── */}
        <div data-hero-reveal className="flex items-center gap-4">
          {/* Avatar circular con fill sólido del modo activo (sin gradiente — guard §3.4) */}
          <div
            className="flex h-[60px] w-[60px] flex-shrink-0 items-center justify-center rounded-full text-[25px] font-semibold text-white"
            style={{ backgroundColor: modeDescriptor.fillVar }}
            role="img"
            aria-label={`Avatar de ${displayName ?? "usuario"}`}
          >
            {nameInitial}
          </div>
          <div className="min-w-0">
            <h1 className="text-title text-[var(--color-ink-deep)] leading-tight">
              {displayName ?? "Vos"}
            </h1>
            <span className="text-caption mt-1 inline-block rounded-full bg-[var(--color-bg-soft)] px-2.5 py-0.5 text-[var(--color-ink-soft)]">
              Plan gratis
            </span>
          </div>
        </div>

        {/* ── Sección: Perfil ── */}
        <SettingsGroup label="Perfil">
          <SettingsRow first title="Tu nombre" sub="Cómo te llama Ynara" />
          <div className="pb-2 pt-1">
            <TextField
              label="Tu nombre"
              value={nameValue}
              onChange={(e) => {
                setNameValue(e.target.value);
                setNameError(null);
              }}
              error={nameError ?? undefined}
              placeholder="Como querés que te llame Ynara"
              maxLength={40}
              disabled={updateMe.isPending}
            />
            <div className="mt-3">
              <Button
                variant="primary"
                onClick={handleSaveName}
                disabled={updateMe.isPending || nameValue.trim() === (displayName ?? "")}
              >
                {updateMe.isPending ? "Guardando…" : "Guardar"}
              </Button>
            </div>
          </div>
        </SettingsGroup>

        {/* ── Sección: Memoria ── */}
        <SettingsGroup label="Memoria">
          <SettingsRow
            first
            title="Tu memoria"
            sub="Ver la red de recuerdos"
            href="/memoria"
            action={<ChevronRight />}
          />
          <SettingsRow
            title="Buscar"
            sub="Buscá en tus recuerdos"
            href="/buscar"
            action={<ChevronRight />}
          />
          <SettingsRow
            title="Exportar mi memoria"
            sub="Descargá un JSON con todo"
            as="button"
            onClick={handleExport}
            action={
              memoryExport.isPending ? (
                <span className="text-caption text-[var(--color-ink-faint)]">Exportando…</span>
              ) : (
                <ChevronRight />
              )
            }
          />
          <SettingsRow
            title="Borrar toda mi memoria"
            sub="Acción permanente e irreversible"
            as="button"
            onClick={() => setWipeOpen(true)}
            action={<ChevronRight />}
          />
        </SettingsGroup>

        {/* ── Sección: Retención de memoria sensible ── */}
        <SettingsGroup label="Retención de memoria sensible">
          <div data-hero-reveal className="pt-2">
            <ChipGroup
              label="Guardar momentos sensibles durante"
              options={RETENTION_OPTIONS}
              value={retention}
              onChange={handleRetentionChange}
            />
            <p className="text-caption mt-2 text-[var(--color-ink-soft)]">
              Los recuerdos marcados como sensibles se borran automáticamente después de este plazo.
            </p>
          </div>
        </SettingsGroup>

        {/* ── Sección: Apariencia ── */}
        <SettingsGroup label="Apariencia">
          <div data-hero-reveal className="pt-2">
            <ChipGroup
              label="Tema"
              options={THEME_OPTIONS}
              value={theme}
              onChange={handleThemeChange}
            />
          </div>
        </SettingsGroup>

        {/* ── Sección: Accesibilidad — card sutil para agrupar los 3 controles ── */}
        <SettingsGroup label="Accesibilidad" dataHeroReveal={false}>
          <A11yCard>
            <ChipGroup
              label="TAMAÑO DEL TEXTO"
              options={TEXT_SIZE_OPTIONS}
              value={textSize}
              onChange={handleTextSize}
            />
            <Toggle
              label="Alto contraste"
              hint="Bordes y textos más definidos."
              checked={highContrast}
              onChange={handleHighContrast}
            />
            <Toggle
              label="Reducir animaciones"
              hint="Menos movimiento en transiciones."
              checked={motionToggleChecked}
              onChange={handleMotion}
            />
          </A11yCard>
        </SettingsGroup>

        {/* ── Sección: Privacidad (calibración de confianza — NN/g) ── */}
        <SettingsGroup label="Privacidad">
          <SettingsRow
            first
            title="On-prem · tus datos no salen del perímetro"
            sub="Tus charlas y tu memoria viven en servidores propios. Nada se manda a terceros."
          />
        </SettingsGroup>

        {/* ── Sección: Cuenta ── */}
        <SettingsGroup label="Cuenta">
          <div data-hero-reveal className="pt-2">
            <Button variant="secondary" onClick={handleLogout}>
              Cerrar sesión
            </Button>
          </div>
        </SettingsGroup>

        {/* ── Footer ── */}
        <footer data-hero-reveal className="mt-2 text-center">
          <p className="text-caption text-[var(--color-ink-faint)]">
            Ynara · MVP 2026
            <br />
            Pensar mejor, recordar siempre.
          </p>
        </footer>
      </HeroReveal>

      {/* Toast global de la vista */}
      <Toast
        message={toast?.message ?? ""}
        visible={toast !== null}
        onDismiss={() => setToast(null)}
        variant={toast?.variant ?? "success"}
      />

      {/* Dialog de confirmación de wipe */}
      <WipeMemoryDialog
        open={wipeOpen}
        onClose={() => setWipeOpen(false)}
        onSuccess={() => setToast({ message: "Memoria borrada.", variant: "success" })}
      />
    </div>
  );
}
