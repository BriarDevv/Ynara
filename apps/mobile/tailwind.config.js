/** @type {import('tailwindcss').Config} */
// Config mínima de NativeWind para que la app bootee (Fase 0 / spike).
// Los design tokens compartidos con la web (globals.css) se agregan en la
// Fase 2 (Task 2.1) dentro de `theme.extend`.
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {},
  },
  plugins: [],
};
