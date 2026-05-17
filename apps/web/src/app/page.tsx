import { siteConfig } from "@/config/site";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-4xl font-semibold">{siteConfig.name}</h1>
      <p className="max-w-prose text-center text-base">
        {siteConfig.description}
      </p>
      <p className="text-sm opacity-60">
        Scaffold inicial — pendiente de UI definitiva. Ver{" "}
        <code>DESIGN.md</code> y <code>docs/product/MODES.md</code>.
      </p>
    </main>
  );
}
