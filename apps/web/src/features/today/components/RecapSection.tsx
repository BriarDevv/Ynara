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

  // data es undefined cuando el endpoint no existe todavía (404 degradado) o
  // cuando react-query no terminó de cargar. `data.pending` decide si mostrar
  // el CTA; si no hay recap no mostramos nada (contenido opcional, no bloquea).
  // La forma explícita `!data || !data.pending` (no `!data?.pending`) es
  // intencional: narrowea `data` a `Recap` para que `recap={data}` abajo
  // satisfaga el tipo sin aserción.
  // biome-ignore lint/complexity/useOptionalChain: necesario para narrowing de `data`
  if (!data || !data.pending) return null;

  return (
    <>
      <RecapCta onOpen={() => setOpen(true)} />
      <RecapSheet open={open} onClose={() => setOpen(false)} recap={data} />
    </>
  );
}
