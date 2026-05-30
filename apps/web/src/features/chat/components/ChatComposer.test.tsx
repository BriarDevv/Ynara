import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CHAT_TEXT_MAX_LENGTH } from "@ynara/shared-schemas";
import { describe, expect, it, vi } from "vitest";
import { ChatComposer } from "./ChatComposer";

describe("ChatComposer", () => {
  it("Enter envía el texto trimmeado y limpia el textarea", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatComposer onSend={onSend} busy={false} />);

    const textarea = screen.getByLabelText("Escribí tu mensaje");
    await user.type(textarea, "  hola mundo  ");
    await user.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledWith("hola mundo");
    expect(textarea).toHaveValue("");
  });

  it("Shift+Enter inserta newline y NO envía", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatComposer onSend={onSend} busy={false} />);

    const textarea = screen.getByLabelText("Escribí tu mensaje");
    await user.type(textarea, "linea1");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(textarea, "linea2");

    expect(onSend).not.toHaveBeenCalled();
    expect((textarea as HTMLTextAreaElement).value).toContain("linea1");
    expect((textarea as HTMLTextAreaElement).value).toContain("linea2");
  });

  it("el botón enviar está deshabilitado si está vacío o solo espacios", async () => {
    const user = userEvent.setup();
    render(<ChatComposer onSend={vi.fn()} busy={false} />);

    const send = screen.getByLabelText("Enviar");
    expect(send).toBeDisabled();

    await user.type(screen.getByLabelText("Escribí tu mensaje"), "   ");
    expect(send).toBeDisabled();
  });

  it("no envía cuando busy", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatComposer onSend={onSend} busy={true} />);

    const textarea = screen.getByLabelText("Escribí tu mensaje");
    expect(textarea).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("no muestra contador con texto corto", () => {
    render(<ChatComposer onSend={vi.fn()} busy={false} />);
    fireEvent.change(screen.getByLabelText("Escribí tu mensaje"), { target: { value: "hola" } });
    expect(screen.queryByText(`/ ${CHAT_TEXT_MAX_LENGTH}`)).toBeNull();
  });

  it("muestra el contador y bloquea el envío cuando se pasa del límite", () => {
    render(<ChatComposer onSend={vi.fn()} busy={false} />);
    const tooLong = "a".repeat(CHAT_TEXT_MAX_LENGTH + 5);
    fireEvent.change(screen.getByLabelText("Escribí tu mensaje"), { target: { value: tooLong } });

    expect(screen.getByText(`${tooLong.length} / ${CHAT_TEXT_MAX_LENGTH}`)).toBeInTheDocument();
    expect(screen.getByLabelText("Enviar")).toBeDisabled();
  });
});
