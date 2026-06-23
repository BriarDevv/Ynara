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
  const fontClasses = `${fontDisplay.variable} ${fontBody.variable} text-size-md theme-dark`;
  return (
    <html
      lang="es-AR"
      // Noche es el DEFAULT server-rendered (paridad con el mockup dark-first):
      // `data-theme="dark"` + `.theme-dark`. Si el usuario eligió claro, el
      // pre-paint de abajo le saca la clase + pone data-theme="light" ANTES del
      // primer paint (sin flash), y el ThemeApplier (providers.tsx) lo mantiene
      // en sync tras hidratar. `color-scheme` por tema vive en globals.css, así
      // el browser nunca aplica `prefers-color-scheme` por su cuenta.
      data-theme="dark"
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
        {/* Script crítico inline anti-FOUC: DEBE correr síncrono antes del primer paint. next/script (afterInteractive/lazyOnload) corre tras hidratar → reintroduce el flash de tema. */}
        {/* react-doctor/nextjs-no-native-script se apaga en doctor.config.js (no inline: chocaría con el biome-ignore de abajo, que debe quedar pegado al <script>). */}
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: snippet inline necesario para correr antes del primer paint y evitar FOUC; contenido es código propio en a11y-init.ts, no input del usuario. */}
        <script dangerouslySetInnerHTML={{ __html: a11yInitScript + themeInitScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
