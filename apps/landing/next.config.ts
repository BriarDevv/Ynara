import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // El indicador de dev de Next cae por defecto en bottom-left, justo sobre la
  // firma de marca del deck (logo + "Ynara"). Lo movemos a top-right para no
  // pisarla (abajo-derecha ya lo ocupa el contador). Solo afecta a `next dev`.
  devIndicators: {
    position: "top-right",
  },
  experimental: {
    optimizePackageImports: ["three", "gsap", "lenis"],
  },
};

export default nextConfig;
