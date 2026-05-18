"use client";

import { useEffect } from "react";
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

export function Toast({
  message,
  visible,
  onDismiss,
  variant = "info",
  duration = 3000,
  className,
}: Props) {
  useEffect(() => {
    if (!visible || duration <= 0) return;
    const id = window.setTimeout(onDismiss, duration);
    return () => window.clearTimeout(id);
  }, [visible, duration, onDismiss]);

  if (!visible) return null;

  /*
   * variant=error usa role=alert + aria-live=assertive para interrumpir
   * inmediato (importante para feedback de error post-submit).
   * Las otras variants usan role=status + aria-live=polite para no
   * cortar la lectura del screen reader.
   */
  const isError = variant === "error";

  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={cn(
        "anim-fade-up fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-[var(--radius-md)] px-5 py-3 shadow-lifted",
        VARIANTS[variant],
        className,
      )}
    >
      <p className="text-body">{message}</p>
    </div>
  );
}
