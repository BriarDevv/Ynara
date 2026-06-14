/** @type {import('tailwindcss').Config} */
// Design tokens de Ynara espejados de la web (apps/web/src/app/globals.css).
// Fuente de marca: manual de identidad 2026 (paleta sólida, no gradientes).
// NativeWind corre sobre Tailwind 3, así que los tokens van en theme.extend
// (la web usa Tailwind 4 CSS-first; los VALORES son los mismos).
// Las fuentes (Space Grotesk / DM Sans) se cargan aparte con expo-font.
const ink = "#242c3f";
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Texto (ink)
        ink: {
          DEFAULT: ink,
          deep: "#1b2233",
          soft: "rgba(36,44,63,0.70)",
          muted: "rgba(36,44,63,0.45)",
          faint: "rgba(36,44,63,0.18)",
        },
        "on-dark": "#ffffff",
        // Fondos
        bg: {
          DEFAULT: "#ffffff",
          canvas: "#faf9f5",
          soft: "#f3f0ea",
        },
        // Bordes
        border: {
          DEFAULT: "rgba(36,44,63,0.12)",
          strong: "rgba(36,44,63,0.22)",
        },
        // CTA primario (azul plano de marca)
        "blue-flat": {
          DEFAULT: "#2f5aa6",
          hover: "#26498a",
          active: "#1f3c75",
        },
        // Paleta oficial del manual
        azul: "#2f5aa6",
        indigo: "#434a82",
        violaceo: "#5c6fb3",
        violeta: "#8165a3",
        celeste: "#6e92cc",
        lavanda: { DEFAULT: "#8b9ad0", deep: "#565f81" },
        noche: ink,
        marfil: "#f3f0ea",
        // Errores
        error: { DEFAULT: "#c0392b", soft: "rgba(192,57,43,0.12)" },
        // Tints por modo (DESIGN.md §3.5)
        mode: {
          productividad: "#2f5aa6",
          estudio: "#434a82",
          bienestar: "#8165a3",
          vida: "#5c6fb3",
          memoria: "#8b9ad0",
        },
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        pill: "9999px",
      },
      fontSize: {
        // Escala tipográfica aproximada a la de la web ([size, lineHeight]).
        caption: ["13px", "18px"],
        "body-sm": ["14px", "20px"],
        body: ["16px", "24px"],
        button: ["15px", "20px"],
        title: ["28px", "34px"],
        hero: ["34px", "40px"],
      },
    },
  },
  plugins: [],
};
