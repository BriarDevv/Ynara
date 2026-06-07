import { DM_Sans, Space_Grotesk } from "next/font/google";

export const fontDisplay = Space_Grotesk({
  subsets: ["latin"],
  // 600 (semibold) lo usa el wordmark del lockup (YnaraWordmark); sin él
  // el navegador sintetiza faux-bold sobre el 500 y el grosor queda
  // distinto al diseñado e inconsistente entre motores.
  weight: ["500", "600", "700"],
  display: "swap",
  variable: "--font-display",
});

export const fontBody = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-body",
});
