import type { Metadata } from "next";
import type { ReactNode } from "react";
import { siteConfig } from "@/config/site";
import { fontBody, fontDisplay } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: siteConfig.name,
    template: `%s — ${siteConfig.name}`,
  },
  description: siteConfig.description,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const fontClasses = `${fontDisplay.variable} ${fontBody.variable}`;
  return (
    <html lang="es-AR" suppressHydrationWarning className={fontClasses}>
      <body className="min-h-screen antialiased">
        {/* TODO: providers (TanStack Query, Theme, Auth) cuando estén montados */}
        {children}
      </body>
    </html>
  );
}
