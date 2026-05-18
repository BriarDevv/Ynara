import type { Metadata } from "next";
import { TestMockClient } from "./TestMockClient";

export const metadata: Metadata = {
  title: "Mock smoke test",
  description: "Smoke test del fetcher + MSW.",
  robots: { index: false, follow: false },
};

export default function TestMockPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-[640px] flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-title">Mock smoke test</h1>
        <p className="text-body-sm text-[var(--color-ink-soft)]">
          Llama <code>GET /v1/health</code> via el fetcher tipado. En dev, MSW intercepta y responde{" "}
          <code>{`{ ok: true, ts }`}</code>.
        </p>
      </header>
      <TestMockClient />
    </main>
  );
}
