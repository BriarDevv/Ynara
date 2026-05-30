import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChatUiMessage } from "../store";
import { MessageBubble } from "./MessageBubble";

function userMsg(over: Partial<ChatUiMessage> = {}): ChatUiMessage {
  return { id: "m1", role: "user", text: "hola", status: "done", ...over };
}

describe("MessageBubble", () => {
  it("renderiza el mensaje del usuario como texto plano", () => {
    render(<MessageBubble message={userMsg({ text: "qué onda **negrita**" })} mode="vida" />);
    // Texto plano: los asteriscos quedan literales (no markdown en user).
    expect(screen.getByText("qué onda **negrita**")).toBeInTheDocument();
  });

  it("renderiza la respuesta del assistant con markdown sanitizado", () => {
    render(
      <MessageBubble
        message={userMsg({ role: "assistant", text: "esto es **fuerte**" })}
        mode="estudio"
      />,
    );
    // react-markdown convierte **fuerte** en <strong>.
    const strong = screen.getByText("fuerte");
    expect(strong.tagName).toBe("STRONG");
  });

  it("un mensaje de error muestra copy humano + botón reintentar", () => {
    const onRetry = vi.fn();
    render(
      <MessageBubble
        message={userMsg({ status: "error", errorCode: "LlmTimeoutError" })}
        mode="vida"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("Me colgué un segundo, ¿lo reintentás?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("error sin código conocido cae al copy genérico", () => {
    render(<MessageBubble message={userMsg({ status: "error" })} mode="vida" />);
    expect(screen.getByText("Algo falló de mi lado. Probá de nuevo.")).toBeInTheDocument();
  });

  it("los links del markdown abren en pestaña nueva con rel seguro", () => {
    render(
      <MessageBubble
        message={userMsg({ role: "assistant", text: "[Ynara](https://ynara.app)" })}
        mode="vida"
      />,
    );
    const link = screen.getByRole("link", { name: "Ynara" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
