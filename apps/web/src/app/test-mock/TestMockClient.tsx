"use client";

import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { type ApiError, api } from "@/lib/api";

type HealthResponse = { ok: boolean; ts: number };

export function TestMockClient() {
  const { data, error, isLoading, isFetching, refetch } = useQuery<HealthResponse, ApiError>({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>("/v1/health"),
  });

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-caption text-[var(--color-ink-soft)]">GET /v1/health</p>
          <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Pidiendo…" : "Refetch"}
          </Button>
        </div>
        {isLoading ? <p className="text-body text-[var(--color-ink-soft)]">Cargando…</p> : null}
        {error ? (
          <p className="text-body text-[var(--color-error)]">
            Error {error.status}: {error.message}
          </p>
        ) : null}
        {data ? (
          <pre className="text-body-sm overflow-x-auto rounded-[var(--radius-md)] bg-[var(--color-bg-soft)] p-4 text-[var(--color-ink)]">
            {JSON.stringify(data, null, 2)}
          </pre>
        ) : null}
      </div>
    </Card>
  );
}
