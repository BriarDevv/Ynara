"use client";

import { type CSSProperties, type ReactNode, useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { Toast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import { usePlayground } from "../hooks/usePlayground";
import { useServing } from "../hooks/useServing";
import type { PlaygroundInT, PlaygroundOutT, ServingOutT } from "../schemas";
import { PlaygroundComposer } from "./PlaygroundComposer";
import {
  type PlaygroundConfig,
  PlaygroundControls,
  type ThinkingChoice,
} from "./PlaygroundControls";
import { PlaygroundTranscript } from "./PlaygroundTranscript";
import { ServingInventory } from "./ServingInventory";

/**
 * Composición client del Playground (ADR-018 §3) — patrón `SystemView`.
 *
 * Vive separada de `page.tsx` (server, conserva `metadata`) y es la única capa
 * client: consume `useServing` (catálogo) + `usePlayground` (mutation sync). NO
 * lleva `range` (runtime/config, foto única). Grilla por bandas con reveal
 * `anim-stagger-up`:
 *  0. `ServingInventory` — estado read-only del serving.
 *  1. `PlaygroundControls` — modelo + bajo rendimiento + params.
 *  2. `PlaygroundTranscript` — turno (user + respuesta/pending/error).
 *  3. `PlaygroundComposer` — textarea + enviar/limpiar.
 *
 * El estado del turno es LOCAL (`useState`): un playground efímero no persiste
 * conversaciones de prueba (sin store, sin semántica de `Mode`).
 */
export function PlaygroundScreen() {
  const { data, isPending: servingPending, isError, refetch } = useServing();

  if (servingPending) return <PlaygroundSkeleton />;

  if (isError) {
    return (
      <EmptyStateCard
        title="No pudimos leer el estado del serving."
        hint="El endpoint /v1/admin/serving no respondió. Reintentá en unos segundos."
        action={
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-[var(--radius-pill)] border border-[var(--color-border-strong)] px-4 py-2 text-button text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)] hover:bg-[var(--color-bg-soft)]"
          >
            Reintentar
          </button>
        }
      />
    );
  }

  if (!data) {
    return (
      <EmptyStateCard
        title="Sin datos de serving."
        hint="El endpoint /v1/admin/serving devolvió vacío."
      />
    );
  }

  return <PlaygroundBody serving={data} />;
}

/**
 * Cuerpo con datos ya cargados: dueña el estado del turno + el de los controles,
 * mapea la config a `PlaygroundIn` y dispara la mutation sync.
 */
function PlaygroundBody({ serving }: { serving: ServingOutT }) {
  const mutation = usePlayground();

  // Config inicial: primer modelo sano (o el primero), params por default.
  const firstHealthy = serving.models.find((m) => m.healthy) ?? serving.models[0];
  const [config, setConfig] = useState<PlaygroundConfig>({
    model: firstHealthy?.served_name ?? "",
    lowPerf: false,
    maxTokens: 1024,
    temperature: 0.7,
    thinking: "auto",
  });

  // Estado local del turno (efímero, sin persistencia).
  const [draft, setDraft] = useState("");
  const [sentMessage, setSentMessage] = useState<string | null>(null);
  const [result, setResult] = useState<PlaygroundOutT | null>(null);
  const [toastVisible, setToastVisible] = useState(false);

  const send = (message: string) => {
    const text = message.trim();
    if (!text || !serving.is_real || !config.model) return;
    setSentMessage(text);
    setResult(null);
    mutation.mutate(toPlaygroundIn(config, text), {
      onSuccess: (out) => setResult(out),
      onError: () => setToastVisible(true),
    });
  };

  const handleSend = () => {
    send(draft);
    setDraft("");
  };

  const handleClear = () => {
    setDraft("");
    setSentMessage(null);
    setResult(null);
    mutation.reset();
  };

  const handleRetry = () => {
    if (sentMessage) send(sentMessage);
  };

  const canSend = serving.is_real && config.model !== "" && draft.trim().length > 0;

  return (
    <>
      <div className="grid grid-cols-12 gap-8">
        <Band span={12} index={0}>
          <ServingInventory serving={serving} />
        </Band>

        <Band span={12} index={1}>
          <PlaygroundControls models={serving.models} config={config} onChange={setConfig} />
        </Band>

        <Band span={12} index={2}>
          <PlaygroundTranscript
            isReal={serving.is_real}
            userMessage={sentMessage}
            result={result}
            isPending={mutation.isPending}
            error={mutation.error}
            onRetry={handleRetry}
          />
        </Band>

        <Band span={12} index={3}>
          <PlaygroundComposer
            value={draft}
            onChange={setDraft}
            onSend={handleSend}
            onClear={handleClear}
            canSend={canSend}
            isPending={mutation.isPending}
          />
        </Band>
      </div>

      <Toast
        message="No pudimos contactar el serving. Reintentá."
        variant="error"
        visible={toastVisible}
        onDismiss={() => setToastVisible(false)}
      />
    </>
  );
}

/**
 * Mapea la config de UI al body `PlaygroundIn` del contrato. `thinking` "auto"
 * viaja como `null` (el server resuelve el default por role); "on"/"off" como
 * booleano explícito.
 */
function toPlaygroundIn(config: PlaygroundConfig, message: string): PlaygroundInT {
  return {
    model: config.model,
    message,
    params: {
      max_tokens: config.maxTokens,
      temperature: config.temperature,
      low_perf: config.lowPerf,
    },
    thinking: thinkingToWire(config.thinking),
  };
}

/** "auto" → null (default por role); "on"/"off" → booleano explícito. */
function thinkingToWire(choice: ThinkingChoice): boolean | null {
  if (choice === "auto") return null;
  return choice === "on";
}

/** Mapeo de `span` a clase de columna (Tailwind necesita clases estáticas). */
const SPAN_CLASS: Record<12, string> = {
  12: "col-span-12",
};

/**
 * Banda de la grilla con reveal escalonado de page-load (mismo patrón que
 * `SystemView`): cada banda entra con `.anim-stagger-up` y su `--stagger-index`.
 */
function Band({ span, index, children }: { span: 12; index: number; children: ReactNode }) {
  return (
    <div
      className={cn(SPAN_CLASS[span], "anim-stagger-up")}
      style={{ "--stagger-index": index } as CSSProperties}
    >
      {children}
    </div>
  );
}

/** Skeleton con la topología de la pantalla, para que no salte al cargar. */
function PlaygroundSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-8" aria-hidden>
      <div className="anim-fade-in col-span-12 h-48 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="anim-fade-in col-span-12 h-64 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="anim-fade-in col-span-12 h-72 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
    </div>
  );
}
