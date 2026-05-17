import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
