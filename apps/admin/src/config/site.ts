export const siteConfig = {
  name: "Ynara · Panel",
  description: "Panel interno de soberanía: métricas de producto, salud del moat y auditoría.",
  url: "https://ynara.app",
  links: {
    docs: "/docs",
  },
} as const;

export type SiteConfig = typeof siteConfig;
