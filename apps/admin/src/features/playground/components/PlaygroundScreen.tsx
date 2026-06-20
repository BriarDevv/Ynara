"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ApiError } from "@/lib/api";
import { type ChatTurn, usePlaygroundSessions } from "@/stores/playgroundSessions";
import { usePlaygroundAgent } from "../hooks/usePlaygroundAgent";
import { type StreamFinal, usePlaygroundStream } from "../hooks/usePlaygroundStream";
import { useServing } from "../hooks/useServing";
import type { PlaygroundAgentOutT, PlaygroundInT, ServingOutT } from "../schemas";
import { ChatHeader } from "./ChatHeader";
import { ChatThread } from "./ChatThread";
import { ModelHealthPanel } from "./ModelHealthPanel";
import { PlaygroundComposer } from "./PlaygroundComposer";
import {
  type PlaygroundConfig,
  PlaygroundControls,
  type ThinkingChoice,
} from "./PlaygroundControls";
import { SessionSidebar } from "./SessionSidebar";
import { TurnInspector } from "./TurnInspector";

/**
 * Playground rediseñado (chat protagonista, ADR-018/019 + control plane F3).
 *
 * Tres columnas a `xl+` (app-like, alto fijo con scroll interno por panel):
 *  - **Sesiones** (izq) — historial client-side (`usePlaygroundSessions`).
 *  - **Chat** (centro, protagonista) — header con IA activa + tok/s en vivo,
 *    hilo completo con streaming token-por-token, composer anclado al pie.
 *  - **Riel** (der) — salud de modelos (qué IA activa), controles del turno e
 *    inspector (métricas + tool-calls).
 *
 * Debajo de `xl` apila en una columna con el chat primero (sigue siendo el
 * protagonista). Gatea el render con `mounted` + `useServing` para no chocar la
 * hidratación del store persistido ni pintar antes de tener el catálogo.
 */
export function PlaygroundScreen() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const { data, isPending, isError, refetch } = useServing();

  if (!mounted || isPending) return <PlaygroundSkeleton />;

  if (isError || !data) {
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

  return <PlaygroundBody serving={data} />;
}

function PlaygroundBody({ serving }: { serving: ServingOutT }) {
  const sessions = usePlaygroundSessions((s) => s.sessions);
  const activeId = usePlaygroundSessions((s) => s.activeId);

  const firstHealthy = serving.models.find((m) => m.healthy) ?? serving.models[0];
  const [config, setConfig] = useState<PlaygroundConfig>({
    model: firstHealthy?.served_name ?? "",
    lowPerf: false,
    maxTokens: 1024,
    temperature: 0.7,
    thinking: "auto",
    agentMode: false,
  });

  const [draft, setDraft] = useState("");
  const stream = usePlaygroundStream();
  const agent = usePlaygroundAgent();

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) ?? null,
    [sessions, activeId],
  );
  const messages = activeSession?.messages ?? [];
  const lastAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant") ?? null,
    [messages],
  );

  const activeModel = serving.models.find((m) => m.served_name === config.model);
  const isBusy = stream.isStreaming || agent.isPending;
  const canSend = serving.is_real && config.model !== "" && draft.trim().length > 0 && !isBusy;

  const runGeneration = (sessionId: string, text: string) => {
    const body = toPlaygroundIn(config, text);
    if (config.agentMode) {
      agent.mutate(body, {
        onSuccess: (out) =>
          usePlaygroundSessions.getState().appendMessage(sessionId, agentTurn(out)),
        onError: (err) =>
          usePlaygroundSessions.getState().appendMessage(sessionId, errorTurn(statusOf(err))),
      });
    } else {
      stream.start(body, {
        onComplete: (final) =>
          usePlaygroundSessions.getState().appendMessage(sessionId, streamTurn(final)),
        onError: (status) =>
          usePlaygroundSessions.getState().appendMessage(sessionId, errorTurn(status)),
      });
    }
  };

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !canSend) return;
    const store = usePlaygroundSessions.getState();
    const sessionId = activeId ?? store.newSession();
    store.appendMessage(sessionId, userTurn(text));
    setDraft("");
    runGeneration(sessionId, text);
  };

  const handleStop = () => stream.abort();

  const handleRetry = () => {
    if (!activeSession) return;
    const lastUser = [...activeSession.messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    const last = activeSession.messages.at(-1);
    if (last && last.role === "assistant" && last.status === "error") {
      usePlaygroundSessions.getState().dropLast(activeSession.id);
    }
    runGeneration(activeSession.id, lastUser.content);
  };

  const handleNew = () => {
    stream.abort();
    usePlaygroundSessions.getState().newSession();
    setDraft("");
  };

  const handleClear = () => {
    stream.reset();
    usePlaygroundSessions.getState().clearActive();
  };

  const handleSelect = (id: string) => {
    stream.abort();
    usePlaygroundSessions.getState().selectSession(id);
  };

  return (
    <div className="anim-screen-in flex flex-col gap-6 xl:h-[calc(100dvh-9rem)] xl:min-h-[34rem] xl:flex-row">
      <SessionSidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={(id) => usePlaygroundSessions.getState().deleteSession(id)}
        onRename={(id, title) => usePlaygroundSessions.getState().renameSession(id, title)}
        className="order-2 shrink-0 xl:order-1 xl:w-[clamp(180px,15vw,240px)] xl:overflow-y-auto xl:scrollbar-none"
      />

      <section className="order-1 flex min-h-[28rem] min-w-0 flex-1 flex-col gap-4 xl:order-2 xl:min-h-0">
        <ChatHeader
          sessionTitle={activeSession?.title ?? null}
          activeModel={activeModel}
          isStreaming={stream.isStreaming}
          liveTokensPerSecond={stream.live.tokensPerSecond}
          liveTokens={stream.live.completionTokens}
          thinkingOn={config.thinking === "on"}
          agentMode={config.agentMode}
          onClear={handleClear}
          canClear={messages.length > 0 && !isBusy}
        />
        <ChatThread
          messages={messages}
          live={stream.live}
          agentPending={agent.isPending}
          isReal={serving.is_real}
          onRetry={handleRetry}
          className="min-h-[18rem] xl:min-h-0"
        />
        <PlaygroundComposer
          value={draft}
          onChange={setDraft}
          onSend={handleSend}
          onStop={handleStop}
          canSend={canSend}
          isStreaming={isBusy}
        />
      </section>

      <aside className="order-3 flex shrink-0 flex-col gap-6 xl:w-[clamp(300px,24vw,360px)] xl:overflow-y-auto xl:scrollbar-none">
        <ModelHealthPanel serving={serving} activeModel={config.model} />
        <PlaygroundControls models={serving.models} config={config} onChange={setConfig} />
        <TurnInspector turn={lastAssistant} live={stream.live} />
      </aside>
    </div>
  );
}

/** Mapea la config de UI al body `PlaygroundIn` del contrato. */
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

function userTurn(text: string): ChatTurn {
  return {
    id: crypto.randomUUID(),
    role: "user",
    content: text,
    status: "ok",
    createdAt: Date.now(),
  };
}

function streamTurn(final: StreamFinal): ChatTurn {
  const d = final.done;
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content: final.text,
    status: "ok",
    model: d.model_name,
    finishReason: d.finish_reason,
    completionTokens: d.completion_tokens,
    latencyMs: d.latency_ms,
    tokensPerSecond: d.tokens_per_second,
    thinkingUsed: d.thinking_used,
    thinking: final.thinking,
    agent: false,
    createdAt: Date.now(),
  };
}

function agentTurn(out: PlaygroundAgentOutT): ChatTurn {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content: out.text,
    status: "ok",
    model: out.model_name,
    finishReason: out.finish_reason,
    thinking: out.thinking ?? null,
    thinkingUsed: out.thinking != null,
    agent: true,
    actions: out.actions,
    createdAt: Date.now(),
  };
}

function errorTurn(status: number | null): ChatTurn {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    status: "error",
    errorStatus: status,
    createdAt: Date.now(),
  };
}

function statusOf(err: unknown): number | null {
  return err instanceof ApiError ? err.status : null;
}

/** Skeleton con la topología de 3 columnas (no salta al cargar). */
function PlaygroundSkeleton() {
  return (
    <div
      className="flex flex-col gap-6 xl:h-[calc(100dvh-9rem)] xl:min-h-[34rem] xl:flex-row"
      aria-hidden
    >
      <div className="anim-fade-in hidden h-full rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] xl:block xl:w-[clamp(180px,15vw,240px)]" />
      <div className="anim-fade-in min-h-[28rem] flex-1 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)]" />
      <div className="anim-fade-in hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] xl:block xl:w-[clamp(300px,24vw,360px)]" />
    </div>
  );
}
