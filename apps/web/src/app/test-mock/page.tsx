import { ChatMockSmoke } from "./ChatMockSmoke";
import { TestMockClient } from "./TestMockClient";

export default function TestMockPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-[640px] flex-col gap-6 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-title">Mock sandbox</h1>
        <p className="text-body text-[var(--color-ink-soft)]">
          Verificación de que MSW intercepta y el fetcher tipado parsea.
        </p>
      </header>
      <TestMockClient />
      <ChatMockSmoke />
    </main>
  );
}
