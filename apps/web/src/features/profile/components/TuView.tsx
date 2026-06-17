"use client";

import { DisplayNameSchema } from "@ynara/shared-schemas";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { TextField } from "@/components/ui/TextField";
import { Toast } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";
import { useMemoryExport } from "@/features/memory/api";
import { useUpdateMe } from "@/features/profile/api";
import { useActiveMode } from "@/hooks/useActiveMode";
import { applyA11yClasses, type TextSize, useA11yStore } from "@/stores/a11y";
import { useUserStore } from "@/stores/user";
import { WipeMemoryDialog } from "./WipeMemoryDialog";

// Opciones de tamaño de texto — espeja A11yStep.tsx.
const TEXT_SIZE_OPTIONS = [
  { value: "sm" as const, label: "Chico" },
  { value: "md" as const, label: "Normal" },
  { value: "lg" as const, label: "Grande" },
] as const;

// Opciones de retención de memoria sensible en días.
const RETENTION_OPTIONS = [
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
  { value: "180", label: "180 días" },
  { value: "365", label: "1 año" },
] as const;

type RetentionValue = "30" | "90" | "180" | "365";

/**
 * Card de ajustes reutilizable: título + contenido con borde y radio del sistema.
 */
function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      data-hero-reveal
      className="flex flex-col gap-4 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] p-6"
    >
      <h2 className="text-subtitle text-[var(--color-ink-deep)]">{title}</h2>
      {children}
    </section>
  );
}

/**
 * Vista **Tú** — perfil, ajustes y acciones de cuenta (build-plan Fase G).
 *
 * Consume los hooks de `@ynara/core` vía `@/features/profile/api` y
 * `@/features/memory/api`. El estado de a11y sigue el patrón EXACTO de
 * `A11yStep.tsx`: escribe directo a `useA11yStore` + `applyA11yClasses` para
 * preview vivo en cada cambio.
 *
 * TODO(post-MVP): cablear GET /me para inicializar los valores del perfil
 * (retention, display_name) desde el servidor en lugar del store local.
 */
export function TuView() {
  const router = useRouter();
  const activeMode = useActiveMode();

  // Store de usuario
  const displayName = useUserStore((s) => s.displayName);
  const setDisplayName = useUserStore((s) => s.setDisplayName);
  const resetUser = useUserStore((s) => s.reset);

  // Store de a11y — igual que A11yStep.tsx
  const textSize = useA11yStore((s) => s.textSize);
  const highContrast = useA11yStore((s) => s.highContrast);
  const motion = useA11yStore((s) => s.motion);
  const setTextSize = useA11yStore((s) => s.setTextSize);
  const setHighContrast = useA11yStore((s) => s.setHighContrast);
  const setMotion = useA11yStore((s) => s.setMotion);

  // Estado local para la sección de perfil
  const [nameValue, setNameValue] = useState(displayName ?? "");
  const [nameError, setNameError] = useState<string | null>(null);

  // Retención — default 365 (sin GET /me todavía).
  // Nota: el valor mostrado es la selección local pendiente; todavía no hay
  // GET /me cableado, así que se inicializa con el default y se sincroniza
  // al hacer el PATCH.
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

  // Mapeo motion ↔ toggle binario (espeja A11yStep.tsx).
  const osPrefersReduce = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
    [],
  );
  const motionToggleChecked =
    motion === "reduce" || (motion === "auto" && Boolean(osPrefersReduce));

  // ── Handlers de a11y ────────────────────────────────────────────────────────

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

  // ── Handlers de perfil ──────────────────────────────────────────────────────

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

  // ── Export de memoria ───────────────────────────────────────────────────────

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

  // ── Logout ──────────────────────────────────────────────────────────────────

  function handleLogout() {
    resetUser();
    router.push("/onboarding");
  }

  return (
    <div className="relative isolate flex min-h-full flex-col">
      {/* Fondo vivo — variante depth: profundidad pura (blooms, sin partículas),
          pensada para la pantalla de perfil (DESIGN.md §2.2). */}
      <LivingField variant="depth" modeId={activeMode} />

      <HeroReveal className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-6 px-6 pb-8 pt-10">
        {/* Header */}
        <div data-hero-reveal>
          <h1 className="text-title text-[var(--color-ink-deep)]">Tú</h1>
          <p className="text-body mt-1 text-[var(--color-ink-soft)]">
            Tu perfil, tu memoria y cómo Ynara se adapta a vos.
          </p>
        </div>

        {/* Sección: Perfil */}
        <SettingsSection title="Perfil">
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
          <Button
            variant="primary"
            onClick={handleSaveName}
            disabled={updateMe.isPending || nameValue.trim() === (displayName ?? "")}
          >
            {updateMe.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </SettingsSection>

        {/* Sección: Retención de memoria sensible */}
        <SettingsSection title="Retención de memoria sensible">
          {/* Nota: el valor mostrado es la selección local pendiente; todavía
              no hay GET /me cableado, así que se sincroniza al hacer el PATCH. */}
          <ChipGroup
            label="Guardar momentos sensibles durante"
            options={RETENTION_OPTIONS}
            value={retention}
            onChange={handleRetentionChange}
          />
          <p className="text-body-sm text-[var(--color-ink-soft)]">
            Los recuerdos marcados como sensibles se borran automáticamente después de este plazo.
          </p>
        </SettingsSection>

        {/* Sección: Memoria */}
        <SettingsSection title="Memoria">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-3">
              <Link
                href="/memoria"
                className="text-button rounded-[var(--radius-md)] border border-[var(--color-border-strong)] px-4 py-2.5 text-[var(--color-ink)] transition-colors hover:bg-[var(--color-bg-soft)]"
              >
                Ver mi memoria
              </Link>
              <Link
                href="/buscar"
                className="text-button rounded-[var(--radius-md)] border border-[var(--color-border-strong)] px-4 py-2.5 text-[var(--color-ink)] transition-colors hover:bg-[var(--color-bg-soft)]"
              >
                Buscar en mi memoria
              </Link>
            </div>
            <Button variant="secondary" onClick={handleExport} disabled={memoryExport.isPending}>
              {memoryExport.isPending ? "Exportando…" : "Exportar mi memoria"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setWipeOpen(true)}
              className="text-[var(--color-error)] hover:bg-[color-mix(in_srgb,var(--color-error)_8%,transparent)]"
            >
              Borrar toda mi memoria
            </Button>
          </div>
        </SettingsSection>

        {/* Sección: Accesibilidad — espeja A11yStep.tsx */}
        <SettingsSection title="Accesibilidad">
          <div className="flex flex-col gap-6">
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
          </div>
        </SettingsSection>

        {/* Sección: Cuenta */}
        <SettingsSection title="Cuenta">
          <Button variant="secondary" onClick={handleLogout}>
            Cerrar sesión
          </Button>
        </SettingsSection>
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
