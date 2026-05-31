"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

type Variant = "info" | "success" | "error";

type Props = {
  message: string;
  visible: boolean;
  onDismiss: () => void;
  variant?: Variant;
  /** ms — 0 desactiva el auto-dismiss. */
  duration?: number;
  className?: string;
};

const VARIANTS: Record<Variant, string> = {
  info: "bg-[var(--color-ink)] text-[var(--color-on-dark)]",
  success: "bg-gradient-blue-base text-[var(--color-on-dark)]",
  error: "bg-[var(--color-error)] text-[var(--color-on-dark)]",
};

/** Duración de la animación de salida (§8.2: 200ms out). Espeja --duration-base. */
const EXIT_MS = 200;

export function Toast({
  message,
  visible,
  onDismiss,
  variant = "info",
  duration = 3000,
  className,
}: Props) {
  // Mantiene el toast montado durante la salida para poder animarla; el padre
  // controla `visible`, nosotros sólo demoramos el desmontaje 200ms.
  const [rendered, setRendered] = useState(visible);
  const [leaving, setLeaving] = useState(false);

  // Ref para que el auto-dismiss no dependa de la identidad de `onDismiss`: los
  // callers pasan arrows inline, y tenerlo en deps reiniciaría el timer en cada
  // render del padre (el toast viviría más de `duration`).
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  useEffect(() => {
    if (!visible || duration <= 0) return;
    const id = window.setTimeout(() => onDismissRef.current(), duration);
    return () => window.clearTimeout(id);
  }, [visible, duration]);

  useEffect(() => {
    if (visible) {
      setRendered(true);
      setLeaving(false);
      return;
    }
    if (!rendered) return;
    setLeaving(true);
    const id = window.setTimeout(() => {
      setRendered(false);
      setLeaving(false);
    }, EXIT_MS);
    return () => window.clearTimeout(id);
  }, [visible, rendered]);

  if (!rendered) return null;

  /*
   * variant=error usa role=alert + aria-live=assertive para interrumpir
   * inmediato (importante para feedback de error post-submit). Las otras
   * usan role=status + aria-live=polite para no cortar la lectura del SR.
   */
  const isError = variant === "error";

  return (
    // Wrapper de posición: el centrado (translateX -50%) vive acá para no
    // chocar con el transform (translateY) de las animaciones de la caja.
    <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
      <div
        role={isError ? "alert" : "status"}
        aria-live={isError ? "assertive" : "polite"}
        className={cn(
          "rounded-[var(--radius-md)] px-5 py-3 shadow-lifted",
          leaving ? "anim-toast-out" : "anim-toast-in",
          VARIANTS[variant],
          className,
        )}
      >
        <p className="text-body">{message}</p>
      </div>
    </div>
  );
}
