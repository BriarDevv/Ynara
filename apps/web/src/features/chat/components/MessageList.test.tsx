import { render, screen, waitFor } from "@testing-library/react";
import { chatPausedCopy } from "@ynara/shared-schemas";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatUiMessage } from "../store";
import { MessageList } from "./MessageList";

/**
 * Contrato de a11y de la lista (PR #9). Las dinámicas reales de scroll
 * (pin-while-streaming, pausa al subir, mostrar/ocultar el botón) dependen del
 * layout, que jsdom no tiene, así que se cubren en e2e; acá verificamos el
 * contrato de la región viva dedicada, `aria-busy`, y que no se roba el foco.
 */

function msg(
  over: Partial<ChatUiMessage> & Pick<ChatUiMessage, "id" | "role" | "status">,
): ChatUiMessage {
  return { text: "", ...over };
}

const user = msg({ id: "u", role: "user", status: "done", text: "hola" });
const noop = (_id: string) => {};

beforeEach(() => {
  // jsdom no implementa scrollTo; el auto-scroll lo invoca al montar/crecer.
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MessageList — a11y del streaming (PR #9)", () => {
  it("el scroller NO tiene aria-live; la región dedicada sí, con aria-atomic", () => {
    const messages = [
      user,
      msg({ id: "a", role: "assistant", status: "streaming", text: "parci" }),
    ];
    const { container } = render(<MessageList messages={messages} mode="vida" onRetry={noop} />);

    const scroller = container.querySelector("[data-lenis-prevent]");
    expect(scroller).not.toBeNull();
    expect(scroller?.getAttribute("aria-live")).toBeNull();
    expect(scroller).toHaveAttribute("aria-busy", "true");

    const live = screen.getByRole("status");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveAttribute("aria-atomic", "true");
    expect(live).toHaveClass("sr-only");
  });

  it("aria-busy es false cuando ningún mensaje está en streaming", () => {
    const messages = [user, msg({ id: "a", role: "assistant", status: "done", text: "lista" })];
    const { container } = render(<MessageList messages={messages} mode="vida" onRetry={noop} />);
    expect(container.querySelector("[data-lenis-prevent]")).toHaveAttribute("aria-busy", "false");
  });

  it("no anuncia el parcial mientras streamea; anuncia el final UNA vez al cerrar en done", async () => {
    const streaming = [
      user,
      msg({ id: "a", role: "assistant", status: "streaming", text: "respuesta parcial" }),
    ];
    const { rerender } = render(<MessageList messages={streaming} mode="vida" onRetry={noop} />);

    // Mientras streamea, la región viva está vacía (no spamea el parcial).
    expect(screen.getByRole("status").textContent).toBe("");

    // Cierra en done -> ahora sí anuncia el texto final (clear-then-set en rAF).
    const done = [
      user,
      msg({ id: "a", role: "assistant", status: "done", text: "respuesta final" }),
    ];
    rerender(<MessageList messages={done} mode="vida" onRetry={noop} />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("respuesta final"));
  });

  it("dos respuestas seguidas (texto distinto) se anuncian cada una", async () => {
    const a1done = [user, msg({ id: "a1", role: "assistant", status: "done", text: "primera" })];
    const { rerender } = render(<MessageList messages={a1done} mode="vida" onRetry={noop} />);
    // a1 ya estaba "done" al montar -> adoptado sin anunciar.
    expect(screen.getByRole("status").textContent).toBe("");

    // Llega y cierra un segundo turno -> se anuncia su texto.
    const u2 = msg({ id: "u2", role: "user", status: "done", text: "otra" });
    const a2done = [
      ...a1done,
      u2,
      msg({ id: "a2", role: "assistant", status: "done", text: "segunda" }),
    ];
    rerender(<MessageList messages={a2done} mode="vida" onRetry={noop} />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("segunda"));
  });

  it("dos respuestas IDÉNTICAS seguidas re-anuncian (remonta el live-region)", async () => {
    // Turno 1 cierra con "igual".
    const s1 = [user, msg({ id: "a1", role: "assistant", status: "streaming", text: "" })];
    const { rerender } = render(<MessageList messages={s1} mode="vida" onRetry={noop} />);
    const d1 = [user, msg({ id: "a1", role: "assistant", status: "done", text: "igual" })];
    rerender(<MessageList messages={d1} mode="vida" onRetry={noop} />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("igual"));
    const firstNode = screen.getByRole("status");

    // Turno 2 con texto IDÉNTICO. El live-region se REMONTA (key nueva por cada
    // "done") para que el lector re-anuncie aunque el string no cambió: un nodo
    // aria-live nuevo ⇒ nuevo anuncio, sin el viejo truco "" → rAF → text.
    const u2 = msg({ id: "u2", role: "user", status: "done", text: "x" });
    const s2 = [...d1, u2, msg({ id: "a2", role: "assistant", status: "streaming", text: "" })];
    rerender(<MessageList messages={s2} mode="vida" onRetry={noop} />);
    const d2 = [...d1, u2, msg({ id: "a2", role: "assistant", status: "done", text: "igual" })];
    rerender(<MessageList messages={d2} mode="vida" onRetry={noop} />);

    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("igual"));
    // Re-anuncio = nodo remontado (no el mismo nodo con texto repetido, que el
    // lector ignoraría por aria-atomic sin cambio de string).
    expect(screen.getByRole("status")).not.toBe(firstNode);
  });

  it("un turno degradado (IA no disponible) se anuncia en la región viva con el copy honesto", async () => {
    const streaming = [
      user,
      msg({ id: "a", role: "assistant", status: "streaming", text: "Estoy con un problema" }),
    ];
    const { rerender } = render(<MessageList messages={streaming} mode="vida" onRetry={noop} />);
    expect(screen.getByRole("status").textContent).toBe("");

    // El turno cierra "degraded": el store ya vació el texto enlatado, así que la
    // región persistente anuncia el copy honesto (no el enlatado, no vacío).
    const degraded = [user, msg({ id: "a", role: "assistant", status: "degraded", text: "" })];
    rerender(<MessageList messages={degraded} mode="vida" onRetry={noop} />);
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(chatPausedCopy()));
  });

  it("un mensaje cancelado o con error NO se anuncia en la región viva", async () => {
    const streaming = [
      user,
      msg({ id: "a", role: "assistant", status: "streaming", text: "parci" }),
    ];
    const { rerender } = render(<MessageList messages={streaming} mode="vida" onRetry={noop} />);

    const canceled = [user, msg({ id: "a", role: "assistant", status: "canceled", text: "parci" })];
    rerender(<MessageList messages={canceled} mode="vida" onRetry={noop} />);
    // Un frame por si hubiera un re-anuncio pendiente; no debe haberlo.
    await new Promise((r) => requestAnimationFrame(r));
    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("no anuncia el historial ya presente al montar (no relee al abrir la conversación)", () => {
    const history = [
      user,
      msg({ id: "a", role: "assistant", status: "done", text: "vieja respuesta" }),
    ];
    render(<MessageList messages={history} mode="vida" onRetry={noop} />);
    // El assistant ya estaba "done" al montar -> se adopta sin anunciarlo.
    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("no roba el foco al cerrar el stream", () => {
    const streaming = [
      user,
      msg({ id: "a", role: "assistant", status: "streaming", text: "parci" }),
    ];
    const { rerender } = render(<MessageList messages={streaming} mode="vida" onRetry={noop} />);
    const before = document.activeElement;

    const done = [user, msg({ id: "a", role: "assistant", status: "done", text: "lista" })];
    rerender(<MessageList messages={done} mode="vida" onRetry={noop} />);
    expect(document.activeElement).toBe(before);
  });

  it("conversación vacía: muestra el empty state, sin scroller ni región viva", () => {
    const { container } = render(<MessageList messages={[]} mode="vida" onRetry={noop} />);
    expect(container.querySelector("[data-lenis-prevent]")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });
});
