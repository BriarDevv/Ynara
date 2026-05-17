import type { Metadata } from "next";
import type { ReactNode } from "react";
import { siteConfig } from "@/config/site";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: siteConfig.name,
    template: `%s — ${siteConfig.name}`,
  },
  description: siteConfig.description,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-AR" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        {/* TODO: providers (TanStack Query, Theme, Auth) cuando estén montados */}
        {children}
      </body>
    </html>
  );
}
