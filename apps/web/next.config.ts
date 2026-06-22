import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Orígenes de dev permitidos para los assets de `/_next` (Next 16 bloquea con 403
  // los requests cross-origin al dev server desde un host no listado). Se setea por
  // env `NEXT_DEV_ALLOWED_ORIGINS` (CSV) SOLO al compartir el dev server por LAN/
  // Tailscale (ej. `100.66.59.108,lonchos.tail093f0b.ts.net`); vacío en local normal.
  // No afecta producción (allowedDevOrigins es solo del dev server).
  allowedDevOrigins: process.env.NEXT_DEV_ALLOWED_ORIGINS?.split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
  // TODO: configurar imágenes externas cuando sepamos qué dominios
  // (R2, avatars, etc.) van a aparecer.
  images: {
    remotePatterns: [],
  },
  // TODO: configurar headers de seguridad (CSP, HSTS, etc.) en una
  // pasada de hardening previa al launch.
  experimental: {
    // TODO: revisar flags experimentales de Next 16 que nos sirvan.
  },
};

export default nextConfig;
