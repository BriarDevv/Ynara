import { DM_Sans, Space_Grotesk } from "next/font/google";

// Display — titulares, mark, eyebrows. Tight, editorial.
export const fontDisplay = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  display: "swap",
  variable: "--font-display",
});

// Body — copy, leads, captions.
export const fontBody = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-body",
});
