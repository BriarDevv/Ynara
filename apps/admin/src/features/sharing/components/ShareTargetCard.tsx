"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Toast } from "@/components/ui/Toast";

type Props = {
  label: string;
  url: string;
  port: number;
};

/**
 * Tarjeta de una superficie para compartir (API OpenAI-compatible / chat). Muestra
 * la URL alcanzable por el tailnet (mono, seleccionable) + un botón de copiar con
 * feedback por Toast. El puerto va en `tabular-nums` (guard de diseño). Sin
 * gradiente: color plano por token.
 */
export function ShareTargetCard({ label, url, port }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard
      .writeText(url)
      .then(() => setCopied(true))
      .catch(() => {
        // Clipboard puede fallar sin gesto/permiso o fuera de contexto seguro; el
        // usuario igual puede seleccionar la URL a mano. No bloqueamos el flujo.
      });
  };

  return (
    <Card className="flex flex-col gap-4">
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">{label}</h3>
        <span className="text-caption text-[var(--color-ink-soft)]">
          puerto <span className="tabular-nums text-[var(--color-ink)]">{port}</span>
        </span>
      </header>

      <p className="break-all rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-3 py-2 font-mono text-body-sm text-[var(--color-ink)]">
        {url}
      </p>

      <Button variant="secondary" fullWidth onClick={handleCopy}>
        {copied ? "¡Copiada!" : "Copiar URL"}
      </Button>

      <Toast
        message="URL copiada al portapapeles"
        visible={copied}
        onDismiss={() => setCopied(false)}
        variant="success"
        duration={2000}
      />
    </Card>
  );
}
