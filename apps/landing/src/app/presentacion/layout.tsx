import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Presentación",
  description: "Presentación institucional de lanzamiento de Ynara.",
  // Pitch interno: no indexar.
  robots: { index: false, follow: false },
  alternates: { canonical: "/presentacion" },
};

export default function PresentacionLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
