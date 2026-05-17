// @ts-check
// Configuración ESLint mínima para entornos que aún la necesitan
// (Expo, por ejemplo). Biome cubre la mayoría de los casos.

export default [
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
    },
    rules: {
      // TODO: agregar reglas específicas cuando aparezca una que
      // Biome no cubra. Mantener este archivo lo más chico posible.
    },
  },
];
