"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Diamond } from "@/components/ui/Diamond";
import { MODE_BY_ID } from "@/components/ui/modes";
import { Sheet } from "@/components/ui/Sheet";
import { Toast } from "@/components/ui/Toast";
import { YnaraOrb } from "@/components/ui/YnaraOrb";

// ---------------------------------------------------------------------------
// Beneficios de Premium
// ---------------------------------------------------------------------------

const BENEFITS = [
  "Memoria sin límite",
  "Avisos proactivos",
  "Modos avanzados",
  "Soporte prioritario",
] as const;

// ---------------------------------------------------------------------------
// PaywallSheet
// ---------------------------------------------------------------------------

type Props = {
  open: boolean;
  onClose: () => void;
};

/**
 * Bottom-sheet de paywall (mockup PaywallScreen): muestra orbe bienestar,
 * headline con acento violeta, 4 beneficios con Diamond como bullet, precio
 * y CTAs primario/ghost. Completamente maquetado — sin integración de pago.
 */
export function PaywallSheet({ open, onClose }: Props) {
  const [toast, setToast] = useState<string | null>(null);

  const violetaFill = MODE_BY_ID.bienestar.fillVar;

  function handleActivar() {
    onClose();
    setToast("Premium es demo por ahora 🔒");
  }

  return (
    <>
      <Sheet open={open} onClose={onClose} title="Activar Premium" titleHidden>
        <div className="flex flex-col items-center gap-6 pb-2">
          {/* Orbe modo bienestar (violeta) */}
          <YnaraOrb size={72} modeId="bienestar" />

          {/* Headline */}
          <div className="text-center">
            <h2 className="text-display leading-tight text-[var(--color-ink)]">
              Pagás para que <span style={{ color: violetaFill }}>no se olvide</span> de vos
            </h2>
            <p className="text-body mt-2 text-[var(--color-ink-soft)]">
              Desbloqueá todo lo que Ynara puede darte.
            </p>
          </div>

          {/* Beneficios */}
          <ul className="w-full space-y-3" aria-label="Beneficios de Premium">
            {BENEFITS.map((benefit) => (
              <li key={benefit} className="flex items-center gap-3">
                <Diamond size={10} color={violetaFill} />
                <span className="text-body text-[var(--color-ink)]">{benefit}</span>
              </li>
            ))}
          </ul>

          {/* Precio */}
          <div className="text-center">
            <p className="text-title font-semibold text-[var(--color-ink-deep)]">$6.900/mes</p>
            <p className="text-caption mt-0.5 text-[var(--color-ink-soft)]">
              Cancelás cuando querés.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex w-full flex-col gap-3">
            <button
              type="button"
              onClick={handleActivar}
              className="text-button inline-flex w-full items-center justify-center rounded-[var(--radius-md)] px-6 py-3 font-semibold text-[var(--color-on-dark)] transition-[opacity,transform] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] active:scale-[0.98] disabled:opacity-50"
              style={{ backgroundColor: violetaFill }}
            >
              Activar Premium
            </button>
            <Button variant="ghost" fullWidth onClick={onClose}>
              Quizás después
            </Button>
          </div>
        </div>
      </Sheet>

      {/* Toast de demo — posicionado fuera del Sheet para no quedar atrapado en el stacking context */}
      <Toast
        message={toast ?? ""}
        visible={toast !== null}
        onDismiss={() => setToast(null)}
        variant="info"
      />
    </>
  );
}
