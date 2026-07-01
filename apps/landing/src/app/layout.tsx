import type { Metadata, Viewport } from "next";
import { Field } from "@/components/field/Field";
import { Preloader } from "@/components/Preloader";
import SmoothScroll from "@/components/SmoothScroll";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteNav } from "@/components/site/SiteNav";
import { pricing, site } from "@/content/ynara";
import { fontBody, fontDisplay } from "./fonts";
import "./globals.css";

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "Ynara",
      url: `https://${site.domain}`,
      logo: `https://${site.domain}/logo.svg`,
      description: site.description,
      foundingDate: "2026-01-01",
      areaServed: "AR",
    },
    {
      "@type": "SoftwareApplication",
      name: "Ynara",
      url: `https://${site.domain}`,
      image: `https://${site.domain}/opengraph-image`,
      applicationCategory: "ProductivityApplication",
      operatingSystem: "iOS, Android",
      description: site.description,
      inLanguage: "es-AR",
      author: { "@type": "Organization", name: "Ynara" },
      offers: {
        "@type": "AggregateOffer",
        lowPrice: "0",
        highPrice: "6",
        priceCurrency: "USD",
        offerCount: pricing.plans.length,
        availability: "https://schema.org/PreOrder",
      },
    },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(`https://${site.domain}`),
  title: {
    default: "Ynara · Tu asistente personal con memoria",
    template: "%s · Ynara",
  },
  description: site.description,
  applicationName: "Ynara",
  alternates: { canonical: "/" },
  robots: { index: true, follow: true, googleBot: { index: true, follow: true } },
  keywords: [
    "Ynara",
    "asistente personal",
    "IA",
    "memoria",
    "productividad",
    "bienestar",
    "self-hosted",
  ],
  authors: [{ name: "Ynara" }],
  openGraph: {
    type: "website",
    locale: "es_AR",
    url: `https://${site.domain}`,
    siteName: "Ynara",
    title: "Ynara · Tu asistente personal con memoria",
    description: site.description,
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Ynara — Tu asistente personal con memoria",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Ynara · Tu asistente personal con memoria",
    description: site.description,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0c12",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es-AR" className={`${fontDisplay.variable} ${fontBody.variable}`}>
      <body>
        <script
          type="application/ld+json"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD estático y controlado
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <a
          href="#top"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[110] focus:rounded-[var(--r-md)] focus:bg-blue focus:px-4 focus:py-2 focus:text-white"
        >
          Saltar al contenido
        </a>
        <Field />
        <SmoothScroll />
        <Preloader />
        <SiteNav />
        <main id="top" tabIndex={-1} className="outline-none">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
