// React Doctor — config de apps/web.
//
// Estas 3 reglas se apagan A PROPÓSITO porque chocan con supresiones inline de
// biome (el linter de CI) sobre los MISMOS elementos intencionales. Ni biome ni
// react-doctor toleran otro comentario entre su directiva de supresión y el
// elemento, y ambas reglas anclan en la misma línea → no se pueden suprimir las
// dos inline. Como biome es el linter de CI, dejamos su `biome-ignore` inline
// (con su razón) y movemos la supresión de react-doctor acá.
//
// - nextjs-no-native-script → el <script> inline anti-FOUC de src/app/layout.tsx
//   DEBE correr síncrono antes del primer paint; next/script corre tras hidratar
//   y reintroduce el flash de tema. Único uso en el repo. (biome lo cubre con
//   noDangerouslySetInnerHtml inline.)
// - click-events-have-key-events / no-noninteractive-element-interactions → el
//   <dialog> de src/components/ui/Sheet.tsx ya cierra por teclado (Escape vía
//   onCancel nativo + botón "Cerrar"); el onClick sólo agrega cierre por click en
//   el backdrop (mouse). Único uso en el repo. (biome lo cubre con
//   useKeyWithClickEvents inline.)
export default {
  rules: {
    "react-doctor/nextjs-no-native-script": "off",
    "react-doctor/click-events-have-key-events": "off",
    "react-doctor/no-noninteractive-element-interactions": "off",
  },
};
