import type { MetadataRoute } from "next";
import { site } from "@/content/ynara";

export default function robots(): MetadataRoute.Robots {
  const base = `https://${site.domain}`;
  return {
    rules: [
      { userAgent: "*", allow: "/" },
      { userAgent: "*", disallow: "/lab/" },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
