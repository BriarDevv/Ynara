"use client";

import CascadeField from "@/components/field/CascadeField";

/**
 * Banco de pruebas AISLADO del campo cascada (técnica infinitefield completa,
 * identidad Ynara). El canvas es opaco/carbón y z-alto → tapa el campo global
 * y el chrome. 500vh para recorrer la coreografía: olas edge-on → giro a
 * cenital + buceo → plano → puntos → tablero → cuadros. /lab/field
 * Driver manual: window.__setFieldProgress(p).
 */
export default function FieldLab() {
  return (
    <>
      <CascadeField />
      <div style={{ height: "500vh" }} aria-hidden />
    </>
  );
}
