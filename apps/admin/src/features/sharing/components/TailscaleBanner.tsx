"use client";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

type Props = {
  up: boolean;
  hostname: string | null;
  tailnetIp: string | null;
  detail: string;
};

/**
 * Estado del tailnet de Tailscale (banner superior de Conexión / Compartir).
 *
 * Estado binario, sin verde (decisión de marca, igual que System Health): conectado
 * = azul plano de marca con dot que late; desconectado = neutro. El `detail` da el
 * porqué cuando está abajo (`not_installed`/`needslogin`/`timeout`…). El `tailnet_ip`
 * va en `tabular-nums` para que los dígitos no bailen.
 */
export function TailscaleBanner({ up, hostname, tailnetIp, detail }: Props) {
  return (
    <Card className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Tailscale</p>
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">
          {up ? "Conectado al tailnet" : "Desconectado"}
        </h3>
        {up && tailnetIp ? (
          <p className="text-body-sm text-[var(--color-ink-soft)]">
            {hostname ? `${hostname} · ` : ""}
            <span className="tabular-nums text-[var(--color-ink)]">{tailnetIp}</span>
          </p>
        ) : (
          <p className="text-caption text-[var(--color-ink-soft)]">{detail}</p>
        )}
      </div>
      <StatusDot up={up} />
    </Card>
  );
}

/** Dot de estado: azul plano que late si conectado, neutro si no (sin verde/ámbar). */
function StatusDot({ up }: { up: boolean }) {
  return (
    <span
      aria-hidden
      className={cn("mt-1 size-2.5 shrink-0 rounded-[var(--radius-pill)]", up && "anim-pulse-soft")}
      style={{ backgroundColor: up ? "var(--color-blue-flat)" : "var(--color-ink-faint)" }}
    />
  );
}
