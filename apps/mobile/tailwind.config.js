/** @type {import('tailwindcss').Config} */
// Design tokens de Ynara espejados de la web (apps/web/src/app/globals.css).
// Fuente de marca: manual de identidad 2026 (paleta sólida, no gradientes).
// NativeWind corre sobre Tailwind 3, así que los tokens van en theme.extend
// (la web usa Tailwind 4 CSS-first; los VALORES son los mismos).
// Los colores semánticos salen de variables CSS (src/global.css): tema oscuro
// por default, con un set claro inactivo listo para un toggle futuro.
// Las fuentes (Space Grotesk / DM Sans) se cargan aparte con expo-font.
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Texto (ink) — variables de tema
        ink: {
          DEFAULT: "var(--ink)",
          deep: "var(--ink-deep)",
          soft: "var(--ink-soft)",
          muted: "var(--ink-muted)",
          faint: "var(--ink-faint)",
        },
        "on-dark": "#ffffff",
        // Fondos / superficies — variables de tema
        bg: {
          DEFAULT: "var(--bg)",
          canvas: "var(--bg-canvas)",
          soft: "var(--bg-soft)",
          hi: "var(--bg-hi)",
        },
        // Bordes — variables de tema
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        // Superficies translúcidas (glass / chips) — variables de tema
        glass: "var(--glass)",
        chip: { DEFAULT: "var(--chip)", border: "var(--chip-border)" },
        // CTA primario (azul plano de marca) — fijo en ambos temas
        "blue-flat": {
          DEFAULT: "#2f5aa6",
          hover: "#26498a",
          active: "#1f3c75",
        },
        // Paleta oficial del manual — fija
        azul: "#2f5aa6",
        indigo: "#434a82",
        violaceo: "#5c6fb3",
        violeta: "#8165a3",
        celeste: "#6e92cc",
        lavanda: { DEFAULT: "#8b9ad0", deep: "#565f81" },
        noche: "#242c3f",
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
      fontFamily: {
        // Cuerpo (DM Sans) y titulares (Space Grotesk). Cargadas en el root con
        // expo-font (ver src/lib/fonts.ts). Los pesos van como familias aparte.
        body: ["DMSans-Regular", "system-ui", "sans-serif"],
        "body-medium": ["DMSans-Medium", "system-ui", "sans-serif"],
        "body-semibold": ["DMSans-SemiBold", "system-ui", "sans-serif"],
        display: ["SpaceGrotesk-SemiBold", "system-ui", "sans-serif"],
        "display-medium": ["SpaceGrotesk-Medium", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
