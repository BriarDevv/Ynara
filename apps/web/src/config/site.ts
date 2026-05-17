export const siteConfig = {
  name: "Ynara",
  description: "Asistente personal adaptativo con memoria propia.",
  url: "https://ynara.app",
  // TODO: confirmar dominio definitivo y completar canales/social.
  links: {
    docs: "/docs",
  },
} as const;

export type SiteConfig = typeof siteConfig;
