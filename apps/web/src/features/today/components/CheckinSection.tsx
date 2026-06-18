"use client";

import { useState } from "react";
import { Toast } from "@/components/ui/Toast";
import { CheckinCta } from "./CheckinCta";
import { CheckinSheet } from "./CheckinSheet";

/**
 * Sección de check-in matinal en Hoy. Muestra el CTA y controla la apertura
 * del sheet. Sin backend — el estado persiste solo en la sesión; al confirmar
 * ("Listo") damos feedback con un toast en vez de cerrar en silencio.
 */
export function CheckinSection() {
  const [open, setOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  return (
    <>
      <CheckinCta onOpen={() => setOpen(true)} />
      <CheckinSheet open={open} onClose={() => setOpen(false)} onDone={() => setConfirmed(true)} />
      <Toast
        message="Listo, lo anoté. Que tengas buen día."
        visible={confirmed}
        onDismiss={() => setConfirmed(false)}
        variant="success"
      />
    </>
  );
}
