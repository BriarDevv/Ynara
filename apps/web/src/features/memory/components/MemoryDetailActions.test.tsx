import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { EpisodicMemoryOut, SemanticMemoryOut } from "@ynara/shared-schemas";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { MemoryDetailActions } from "./MemoryDetailActions";

// El componente navega tras borrar; basta con un router stub.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const ISO = "2026-05-08T09:42:00.000Z";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const semantic: SemanticMemoryOut = {
  id: UUID,
  user_id: UUID,
  content: "Un hecho editable.",
  importance: 50,
  source_session_id: null,
  created_at: ISO,
  updated_at: ISO,
};

const episodic: EpisodicMemoryOut = {
  id: UUID,
  user_id: UUID,
  session_id: UUID,
  summary: "Un momento, no editable.",
  is_sensitive: false,
  retention_days: 365,
  occurred_at: ISO,
  topics: {},
  created_at: ISO,
  updated_at: ISO,
};

function renderWithClient(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("MemoryDetailActions", () => {
  it("la capa semántica ofrece editar y borrar", () => {
    renderWithClient(<MemoryDetailActions layer="semantic" item={semantic} />);
    expect(screen.getByRole("button", { name: "Editar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Borrar" })).toBeInTheDocument();
  });

  it("la capa episódica no ofrece editar (el backend responde 405)", () => {
    renderWithClient(<MemoryDetailActions layer="episodic" item={episodic} />);
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Borrar" })).toBeInTheDocument();
  });
});
