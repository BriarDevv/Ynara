import { useRecap } from "@ynara/core/features/today";
import { useState } from "react";
import { RecapCta } from "./RecapCta";
import { RecapSheet } from "./RecapSheet";

/**
 * Sección **Recap pendiente** (wireframe 06). Mientras el día no se cerró
 * (`recap.pending`), muestra el CTA que abre el sheet del recap. Si no hay recap,
 * está cargando, falló, o el día ya se cerró, no muestra nada (contenido
 * opcional, no bloquea el dashboard). Espejo de web.
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
