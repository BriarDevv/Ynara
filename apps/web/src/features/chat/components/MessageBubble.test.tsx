import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useShowReasoningStore } from "@/stores/showReasoning";
import type { ChatUiMessage } from "../store";
import { MessageBubble } from "./MessageBubble";

function userMsg(over: Partial<ChatUiMessage> = {}): ChatUiMessage {
  return { id: "m1", role: "user", text: "hola", status: "done", ...over };
}

describe("MessageBubble", () => {
  // El toggle display-only es un store persistido: reseteamos entre casos para
  // que el default (OFF) sea determinista, sin depender de residuo en localStorage.
  beforeEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

  afterEach(() => {
    useShowReasoningStore.getState().reset();
    localStorage.clear();
  });

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

  it("muestra el colapsable de razonamiento con reasoning + toggle ON", () => {
    useShowReasoningStore.getState().setEnabled(true);
    render(
      <MessageBubble
        message={userMsg({ role: "assistant", text: "respuesta", reasoning: "pensé esto" })}
        mode="estudio"
      />,
    );
    expect(screen.getByTestId("thinking-disclosure")).toBeInTheDocument();
    expect(screen.getByText("pensé esto")).toBeInTheDocument();
  });

  it("oculta el colapsable con el toggle OFF aunque haya reasoning", () => {
    // store default OFF (reseteado en beforeEach)
    render(
      <MessageBubble
        message={userMsg({ role: "assistant", text: "respuesta", reasoning: "pensé esto" })}
        mode="estudio"
      />,
    );
    expect(screen.queryByTestId("thinking-disclosure")).toBeNull();
  });

  it("no muestra el colapsable sin reasoning aunque el toggle esté ON", () => {
    useShowReasoningStore.getState().setEnabled(true);
    render(
      <MessageBubble message={userMsg({ role: "assistant", text: "respuesta" })} mode="estudio" />,
    );
    expect(screen.queryByTestId("thinking-disclosure")).toBeNull();
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
