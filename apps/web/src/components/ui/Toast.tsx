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
  error: "bg-[#c0392b] text-[var(--color-on-dark)]",
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

  return (
    <div
      role="status"
      aria-live="polite"
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
