import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiError } from "@ynara/core/api";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// Mocks de las mutations de wipe (la lógica real vive en @ynara/core; acá
// aislamos el comportamiento del dialog SAGRADO — regla #3).
const previewMock = {
  mutateAsync: vi.fn(),
  isPending: false,
  reset: vi.fn(),
};
const executeMock = {
  mutateAsync: vi.fn(),
  isPending: false,
  reset: vi.fn(),
  error: null as unknown,
};

vi.mock("@/features/memory/api", () => ({
  useMemoryWipePreview: () => previewMock,
  useMemoryWipeExecute: () => executeMock,
}));

const { WipeMemoryDialog } = await import("./WipeMemoryDialog");

const PREVIEW = { semantic: 3, episodic: 2, procedural: 2, total: 7 };

// jsdom no implementa showModal/close del <dialog> (Sheet).
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

beforeEach(() => {
  previewMock.mutateAsync = vi.fn().mockResolvedValue(PREVIEW);
  previewMock.reset = vi.fn();
  executeMock.mutateAsync = vi.fn().mockResolvedValue({ deleted: 7 });
  executeMock.reset = vi.fn();
  executeMock.isPending = false;
  executeMock.error = null;
});

function getConfirmInput() {
  return screen.getByRole("textbox", { name: /escribí .* para confirmar/i });
}
function getConfirmButton() {
  return screen.getByRole("button", { name: /confirmar borrado permanente/i });
}

describe("WipeMemoryDialog", () => {
  it("trae el preview al abrir y muestra los conteos por capa", async () => {
    render(<WipeMemoryDialog open onClose={vi.fn()} />);
    expect(previewMock.mutateAsync).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/7 recuerdos/i)).toBeInTheDocument();
    expect(screen.getByText(/3 hechos/i)).toBeInTheDocument();
  });

  it("el botón queda deshabilitado hasta escribir BORRAR exacto", async () => {
    render(<WipeMemoryDialog open onClose={vi.fn()} />);
    await screen.findByText(/7 recuerdos/i);
    expect(getConfirmButton()).toBeDisabled();

    fireEvent.change(getConfirmInput(), { target: { value: "borrar" } });
    expect(getConfirmButton()).toBeDisabled(); // case-sensitive

    fireEvent.change(getConfirmInput(), { target: { value: "BORRAR" } });
    expect(getConfirmButton()).toBeEnabled();
  });

  it("al confirmar ejecuta con los expected_* del preview y llama onClose+onSuccess", async () => {
    const onClose = vi.fn();
    const onSuccess = vi.fn();
    render(<WipeMemoryDialog open onClose={onClose} onSuccess={onSuccess} />);
    await screen.findByText(/7 recuerdos/i);
    fireEvent.change(getConfirmInput(), { target: { value: "BORRAR" } });
    fireEvent.click(getConfirmButton());

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(executeMock.mutateAsync).toHaveBeenCalledWith({
      expected_semantic: 3,
      expected_episodic: 2,
      expected_procedural: 2,
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ante 409 muestra el aviso, re-trae el preview, limpia el input y NO llama onSuccess", async () => {
    const onSuccess = vi.fn();
    executeMock.mutateAsync = vi
      .fn()
      .mockRejectedValue(new ApiError(409, { message: "Los conteos cambiaron." }));
    render(<WipeMemoryDialog open onClose={vi.fn()} onSuccess={onSuccess} />);
    await screen.findByText(/7 recuerdos/i);
    fireEvent.change(getConfirmInput(), { target: { value: "BORRAR" } });
    fireEvent.click(getConfirmButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(/conteos cambiaron/i);
    expect(onSuccess).not.toHaveBeenCalled();
    // Re-trajo el preview (1 al abrir + 1 tras el 409) y limpió el input.
    expect(previewMock.mutateAsync).toHaveBeenCalledTimes(2);
    expect((getConfirmInput() as HTMLInputElement).value).toBe("");
  });

  it("muestra un error genérico ante un fallo no-409 del execute", async () => {
    executeMock.error = new Error("boom");
    render(<WipeMemoryDialog open onClose={vi.fn()} />);
    await screen.findByText(/7 recuerdos/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/ocurrió un error al borrar/i);
  });
});
