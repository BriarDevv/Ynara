"use client";

import { useState } from "react";
import { CheckinCta } from "./CheckinCta";
import { CheckinSheet } from "./CheckinSheet";

/**
 * Sección de check-in matinal en Hoy. Muestra el CTA y controla la apertura
 * del sheet. Sin backend — el estado persiste solo en la sesión.
 */
export function CheckinSection() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <CheckinCta onOpen={() => setOpen(true)} />
      <CheckinSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
