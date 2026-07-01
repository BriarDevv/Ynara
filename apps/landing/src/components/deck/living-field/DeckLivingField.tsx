"use client";

import type { Mode } from "./field";
import { LivingField } from "./LivingField";
import "./DeckLivingField.css";

/**
 * Campo vivo de la app Ynara montado como BACKDROP a sangre completa de una lámina
 * del deck (sección de marca). Una base tapa el campo WebGL del deck para que el
 * campo vivo de la app sea el fondo limpio de la lámina. Encima va el `LivingField`
 * variante `aurora` —el fondo del **HOY** de la app: ondas de marca que fluyen
 * (las "vetas" en movimiento) + atmósfera + nodos— teñido por el clima de marca.
 *
 * `dark=false` (default): mundo CLARO/calmo, acorde a la sección de marca.
 */
export function DeckLivingField({
  modeId = "productividad",
  dark = false,
  active = true,
}: {
  modeId?: Mode;
  dark?: boolean;
  /** Lámina activa: pausa el campo cuando no lo está (perf). */
  active?: boolean;
}) {
  return (
    <div className={`deck-livingfield${dark ? " is-dark" : " is-light"}`} aria-hidden>
      <div className="deck-livingfield__base" />
      <LivingField variant="aurora" modeId={modeId} dark={dark} active={active} />
    </div>
  );
}
