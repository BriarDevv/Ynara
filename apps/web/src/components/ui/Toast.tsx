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
  // Azul plano de marca: el gradiente como fill de superficie es anti-patrón (§3.4).
  success: "bg-[var(--color-blue-flat)] text-[var(--color-on-dark)]",
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
  // `leaving` es el único estado pintado: marca que corre la animación de salida.
  // `rendered` NO se copia a estado; se deriva en render como `visible || leaving`
  // así el toast sigue montado mientras anima la salida (200ms) y se desmonta
  // solo cuando `leaving` vuelve a false. Derivar evita la copia stale del prop.
  const [leaving, setLeaving] = useState(false);
  const rendered = visible || leaving;
  // El "previo de visible" sólo sirve para detectar el cambio del prop EN RENDER
  // (patrón recomendado de React para "ajustar estado al cambiar un prop");
  // nunca se pinta, así que va en un ref para no forzar un render extra.
  const prevVisibleRef = useRef(visible);
  if (visible !== prevVisibleRef.current) {
    const wasRendered = prevVisibleRef.current || leaving;
    prevVisibleRef.current = visible;
    if (visible) {
      // Entrada: cancelar cualquier salida en curso (rendered ya es true por `visible`).
      setLeaving(false);
    } else if (wasRendered) {
      // Salida: arranca la animación out; el desmontaje lo demora el timer.
      setLeaving(true);
    }
  }

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

  // Único efecto real: el timer que termina la salida tras EXIT_MS. Al apagar
  // `leaving`, `rendered` (= visible || leaving) cae a false y el toast se
  // desmonta. Si `visible` vuelve a true durante la salida, el ajuste-en-render
  // pone leaving=false y el cleanup limpia este timeout.
  useEffect(() => {
    if (!leaving) return;
    const id = window.setTimeout(() => setLeaving(false), EXIT_MS);
    return () => window.clearTimeout(id);
  }, [leaving]);

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
