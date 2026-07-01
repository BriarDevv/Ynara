"use client";

import { useQueryClient } from "@tanstack/react-query";
import { logOut } from "@ynara/core/features/auth";
import { DisplayNameSchema } from "@ynara/shared-schemas";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { HeroReveal } from "@/components/ui/HeroReveal";
import { LivingField } from "@/components/ui/LivingField";
import { MODE_BY_ID } from "@/components/ui/modes";
import { TextField } from "@/components/ui/TextField";
import { Toast } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";
import { useChatStore } from "@/features/chat/store";
import { useMemoryExport } from "@/features/memory/api";
import { useOnboardingStore } from "@/features/onboarding/store";
import { useMe, useUpdateMe } from "@/features/profile/api";
import { useAvisosStore } from "@/features/today/avisosStore";
import { useActiveMode } from "@/hooks/useActiveMode";
import { qk } from "@/lib/queryKeys";
import { applyA11yClasses, type TextSize, useA11yStore } from "@/stores/a11y";
import { useActiveModeStore } from "@/stores/mode";
import { useShowReasoningStore } from "@/stores/showReasoning";
import { applyThemeClass, type ThemePreference, useThemeStore } from "@/stores/theme";
import { useUserStore } from "@/stores/user";
import { LogoutDialog } from "./LogoutDialog";
import { PaywallSheet } from "./PaywallSheet";
import { A11yCard, ChevronRight, SettingsGroup, SettingsRow } from "./settings-rows";
import { WipeMemoryDialog } from "./WipeMemoryDialog";

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
  { value: "system" as const, label: "Sistema" },
] as const;

type RetentionValue = "30" | "90" | "180" | "365";

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
 * + `applyA11yClasses`, logout (`useUserStore.reset()` + router). Las filas
 * calmas (`SettingsRow`/`SettingsGroup`/`A11yCard`/`ChevronRight`) viven en
 * `./settings-rows` para mantener este archivo bajo 500 líneas.
 */
// no-giant-component: el largo es JSX declarativo de secciones de settings, no
// lógica; las filas calmas ya se extrajeron a ./settings-rows. Partir más
// cablearía muchos handlers de store por props y arriesga la vista de perfil ya
// verificada. prefer-useReducer: los 7 useState son estados de UI independientes
// (campo de nombre, retención, y flags open de 3 dialogs + toast); se setean en
// handlers distintos y no forman una actualización lógica única, así que un
// reducer no aplica.
// react-doctor-disable-next-line react-doctor/no-giant-component
// react-doctor-disable-next-line react-doctor/prefer-useReducer
export function TuView() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const activeMode = useActiveMode();
  const modeDescriptor = MODE_BY_ID[activeMode];

  // Store de usuario
  const displayName = useUserStore((s) => s.displayName);
  const setDisplayName = useUserStore((s) => s.setDisplayName);
  const resetUser = useUserStore((s) => s.reset);
  const token = useUserStore((s) => s.token);

  // Perfil real del backend (G3): trae la retención persistida. Solo con sesión
  // (sin token el endpoint da 401). Hidrata el chip de retención más abajo.
  const meQuery = useMe({ enabled: Boolean(token) });

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

  // Retención. Arranca en el default y se hidrata con el valor real del backend
  // cuando llega `me` (G3: antes quedaba clavado en 365). Solo se adopta si el
  // valor cae en las opciones del chip (el backend lo acota a 30..365 y el FE
  // solo escribe esas 4; un valor fuera de set mantiene el default visible).
  const [retention, setRetention] = useState<RetentionValue>("365");
  const serverRetention = meQuery.data?.retention_sensitive_days;
  useEffect(() => {
    if (serverRetention == null) return;
    const value = String(serverRetention);
    if (RETENTION_OPTIONS.some((o) => o.value === value)) {
      setRetention(value as RetentionValue);
    }
  }, [serverRetention]);

  // Dialog de wipe
  const [wipeOpen, setWipeOpen] = useState(false);

  // Paywall sheet
  const [paywallOpen, setPaywallOpen] = useState(false);

  // Dialog de confirmación de logout
  const [logoutOpen, setLogoutOpen] = useState(false);

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
      // display_name puede ser null si el backend aún no lo guardó; el
      // fallback vacío evita propagar null al store (setDisplayName: string).
      setDisplayName(updated.display_name ?? "");
      // El perfil cambió server-side: refrescamos la query `me` para que la
      // próxima lectura (o re-montaje) traiga el valor persistido, no el cacheado.
      queryClient.invalidateQueries({ queryKey: qk.profile.me() });
      setToast({ message: "Nombre guardado.", variant: "success" });
    } catch {
      setToast({ message: "No se pudo guardar el nombre. Intentá de nuevo.", variant: "error" });
    }
  }

  async function handleRetentionChange(value: RetentionValue) {
    // Guard de pending: con un PATCH en vuelo, ignoramos un segundo cambio — si
    // no, dos cambios rápidos generan rollbacks que se pisan (uno con un
    // `previous` ya stale) y el revert dejaría de ser confiable.
    if (updateMe.isPending) return;
    // Optimista con revert: mostramos el valor elegido ya, pero si el server lo
    // rechaza volvemos al previo — si no, el chip quedaba mostrando una
    // retención que el backend no aceptó (UI mentirosa sobre un control de
    // privacidad). El valor real se hidrata de `me` (G3); tras el PATCH OK
    // invalidamos esa query para que quede consistente con el backend.
    const previous = retention;
    setRetention(value);
    try {
      await updateMe.mutateAsync({ retention_sensitive_days: Number(value) });
      queryClient.invalidateQueries({ queryKey: qk.profile.me() });
      setToast({ message: "Retención actualizada.", variant: "success" });
    } catch {
      setRetention(previous);
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
    // Revocación server-side best-effort: con el Bearer actual el backend revoca la
    // FAMILIA entera de la sesión (claim `sid`) → el access y sus hermanos dejan de
    // servir aunque no hayan expirado (sin esto, un token robado seguía válido hasta
    // su expiración natural). Se captura el token ANTES del reset; fire-and-forget
    // porque el logout local no debe bloquearse en la red: si falla, el token expira
    // solo. No se manda el refresh (la family-revocation por `sid` ya lo cubre).
    const { token } = useUserStore.getState();
    if (token) void logOut(token).catch(() => {});
    // Logout total: además de la sesión del usuario, limpiar TODO el estado con
    // datos personales. `router.push` es navegación client-side (no recarga), así
    // que el chat store (sessions+messages en localStorage), la preferencia
    // show-reasoning y la cache de memoria de TanStack Query sobreviven al logout y
    // los vería el próximo usuario del dispositivo. Por eso los limpiamos acá. Tema y
    // a11y NO se tocan: son prefs del dispositivo, no datos del usuario (limpiar a11y
    // degradaría la accesibilidad del próximo que use el equipo).
    resetUser();
    useChatStore.getState().reset();
    useActiveModeStore.getState().reset();
    useAvisosStore.getState().reset();
    useOnboardingStore.getState().reset();
    useShowReasoningStore.getState().reset();
    queryClient.clear();
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
            className="flex h-[60px] w-[60px] flex-shrink-0 items-center justify-center rounded-full text-[25px] font-semibold text-[var(--color-on-dark)]"
            style={{ backgroundColor: modeDescriptor.fillVar }}
            // No es una imagen real: es el inicial del nombre sobre un círculo
            // teñido. <img> exige src y no admite hijos; role="img" es el patrón
            // ARIA correcto para un avatar generado por texto.
            // react-doctor-disable-next-line react-doctor/prefer-tag-over-role
            role="img"
            aria-label={`Avatar de ${displayName ?? "usuario"}`}
          >
            {nameInitial}
          </div>
          <div className="min-w-0">
            <h1 className="text-title text-[var(--color-ink-deep)] leading-tight">
              {displayName ?? "Vos"}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="text-caption inline-block rounded-full bg-[var(--color-bg-soft)] px-2.5 py-0.5 text-[var(--color-ink-soft)]">
                Plan gratis
              </span>
              <button
                type="button"
                onClick={() => setPaywallOpen(true)}
                className="text-caption inline-block rounded-full px-2.5 py-0.5 font-semibold text-[var(--color-on-dark)] transition-opacity hover:opacity-90 active:opacity-75"
                style={{ backgroundColor: MODE_BY_ID.bienestar.fillVar }}
                aria-label="Subir a Premium"
              >
                Subir a Premium
              </button>
            </div>
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
                <span className="text-caption text-[var(--color-ink-soft)]">Exportando…</span>
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
            title="Privacidad · tu memoria es tuya"
            sub="Tu memoria está cifrada y la podés exportar cuando quieras. Nada se manda a IA de terceros."
          />
        </SettingsGroup>

        {/* ── Sección: Cuenta ── */}
        <SettingsGroup label="Cuenta">
          <div data-hero-reveal className="pt-2">
            <Button variant="secondary" onClick={() => setLogoutOpen(true)}>
              Cerrar sesión
            </Button>
          </div>
        </SettingsGroup>

        {/* ── Footer ── */}
        <footer data-hero-reveal className="mt-2 text-center">
          <p className="text-caption text-[var(--color-ink-soft)]">
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

      {/* Confirmación de cierre de sesión */}
      <LogoutDialog
        open={logoutOpen}
        onClose={() => setLogoutOpen(false)}
        onConfirm={handleLogout}
      />

      {/* Sheet de paywall — maquetado, sin pago real */}
      <PaywallSheet open={paywallOpen} onClose={() => setPaywallOpen(false)} />
    </div>
  );
}
