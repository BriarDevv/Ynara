import type { Metadata } from "next";
import type { ReactNode } from "react";
import { siteConfig } from "@/config/site";
import { a11yInitScript, themeInitScript } from "./a11y-init";
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
      // `data-theme="light"` es el DEFAULT server-rendered (tema claro,
      // DESIGN.md §3.1). Si el usuario eligió Noche, el pre-paint de abajo
      // lo pisa a "dark" + html.theme-dark ANTES del primer paint, y el
      // ThemeApplier (providers.tsx) lo mantiene en sync tras hidratar.
      // `color-scheme` por tema vive en globals.css, así el browser nunca
      // aplica `prefers-color-scheme` por su cuenta.
      data-theme="light"
      suppressHydrationWarning
      className={fontClasses}
    >
      <head>
        {/*
          Scripts inline pre-paint para aplicar preferencias persistidas
          (a11y + tema) antes del primer render. Evitan FOUC entre el
          default server-rendered (text-size-md, claro) y la preferencia
          del usuario. Sincronizados con stores/a11y.ts y stores/theme.ts.
        */}
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: snippet inline necesario para correr antes del primer paint y evitar FOUC; contenido es código propio en a11y-init.ts, no input del usuario. */}
        <script dangerouslySetInnerHTML={{ __html: a11yInitScript + themeInitScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
