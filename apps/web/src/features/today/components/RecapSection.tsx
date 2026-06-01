"use client";

import { useState } from "react";
import { useRecap } from "../api";
import { RecapCta } from "./RecapCta";
import { RecapSheet } from "./RecapSheet";

/**
 * Sección **Recap pendiente** (wireframe 06 / build-plan E4). Mientras el día no
 * se cerró (`recap.pending`), muestra el CTA oscuro que abre el sheet del recap.
 * Si no hay recap, está cargando, falló, o el día ya se cerró, no se muestra
 * nada (es contenido opcional, no bloquea el dashboard).
 */
export function RecapSection() {
  const { data } = useRecap();
  const [open, setOpen] = useState(false);

  if (!data?.pending) return null;

  return (
    <>
      <RecapCta onOpen={() => setOpen(true)} />
      <RecapSheet open={open} onClose={() => setOpen(false)} recap={data} />
    </>
  );
}
