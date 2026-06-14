import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Task } from "@ynara/shared-schemas";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { qk } from "@/lib/queryKeys";
import { useToggleTask } from "./api";

// Mockeamos el fetcher: el test verifica la mecánica optimista del hook, no la
// red. `patch` devuelve la tarea ya flipeada (lo que haría el backend).
// El hook vive en @ynara/core (ADR-012) e importa `api` desde @ynara/core/api,
// así que el mock apunta ahí (no a @/lib/api).
const patch = vi.fn();
vi.mock("@ynara/core/api", () => ({
  api: { patch: (...args: unknown[]) => patch(...args) },
}));

const task: Task = {
  id: "0193c001-0000-4000-8000-000000000002",
  title: "Llamada con equipo de diseño",
  status: "pending",
  scheduled_at: new Date(2026, 4, 7, 14, 0).toISOString(),
  duration_min: 45,
};

function setup() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  client.setQueryData(qk.today.tasks(), [task]);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useToggleTask(), { wrapper });
  return { client, result };
}

const read = (client: QueryClient) => client.getQueryData<Task[]>(qk.today.tasks());

afterEach(() => patch.mockReset());

describe("useToggleTask", () => {
  it("actualiza el cache de forma optimista al togglear", async () => {
    // Nunca resuelve: aislamos el frame optimista (onMutate) del settle.
    patch.mockReturnValue(new Promise(() => {}));
    const { client, result } = setup();

    act(() => {
      result.current.mutate(task);
    });

    await waitFor(() => expect(read(client)?.[0]?.status).toBe("done"));
  });

  it("revierte el cache si el PATCH falla", async () => {
    patch.mockRejectedValue(new Error("boom"));
    const { client, result } = setup();

    act(() => {
      result.current.mutate(task);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(read(client)?.[0]?.status).toBe("pending");
  });

  it("confirma el estado que devuelve el server al tener éxito", async () => {
    patch.mockResolvedValue({ ...task, status: "done" });
    const { client, result } = setup();

    act(() => {
      result.current.mutate(task);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(read(client)?.[0]?.status).toBe("done");
    expect(patch).toHaveBeenCalledWith(`/v1/tasks/${task.id}`, { status: "done" });
  });
});
