import type { Metadata } from "next";
import type { ReactNode } from "react";
import { siteConfig } from "@/config/site";
import { a11yInitScript } from "./a11y-init";
import { fontBody, fontDisplay } from "./fonts";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: {
    default: siteConfig.name,
    template: `%s — ${siteConfig.name}`,
  },
  description: siteConfig.description,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const fontClasses = `${fontDisplay.variable} ${fontBody.variable} text-size-md`;
  return (
    <html
      lang="es-AR"
      // `data-theme="light"` fija el tema en light: el sistema de tokens en
      // globals.css es light-only por decisión de marca (ver DESIGN.md). Sin
      // esto, el browser podría aplicar `prefers-color-scheme: dark` del OS
      // antes de la primera ronda de CSS. El atributo es estable (no cambia
      // por client), así que es seguro renderizarlo en el server.
      data-theme="light"
      suppressHydrationWarning
      className={fontClasses}
    >
      <head>
        {/*
          Script inline pre-paint para aplicar preferencias de a11y antes
          del primer render. Evita FOUC entre el default server-rendered
          (text-size-md) y la preferencia persistida del usuario.
          Sincronizado con stores/a11y.ts.
        */}
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: snippet inline necesario para correr antes del primer paint y evitar FOUC; contenido es código propio en a11y-init.ts, no input del usuario. */}
        <script dangerouslySetInnerHTML={{ __html: a11yInitScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
