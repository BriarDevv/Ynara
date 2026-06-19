"use client";

import type { CSSProperties } from "react";
import { Card } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/cn";
import type { ServingModelOutT } from "../schemas";

/** Modo de thinking elegido por el operador (Auto = default por role). */
export type ThinkingChoice = "auto" | "on" | "off";

/** Estado editable de los controles del playground (lo dueña `PlaygroundScreen`). */
export type PlaygroundConfig = {
  model: string;
  lowPerf: boolean;
  maxTokens: number;
  temperature: number;
  thinking: ThinkingChoice;
};

type Props = {
  models: readonly ServingModelOutT[];
  config: PlaygroundConfig;
  onChange: (next: PlaygroundConfig) => void;
  className?: string;
};

/** Hint del preset bajo rendimiento (la materialización del toggle, §2.2 paso 4). */
const LOW_PERF_HINT = "256 tokens · sin thinking · temp 0.2 · timeout 30s";

const THINKING_OPTIONS: readonly { value: ThinkingChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "on", label: "On" },
  { value: "off", label: "Off" },
];

/**
 * Banda 1 del Playground (ADR-018 §3): selector de modelo + bajo rendimiento +
 * params.
 *
 * - **ModelSelect**: `ChipGroup<served_name>` alimentado por `useServing` (NUNCA
 *   hardcode); deshabilita el modelo si `!healthy`.
 * - **LowPerfToggle**: `Switch` a11y con el hint del preset. En `on` deshabilita
 *   visualmente los sliders (el preset los pisa server-side).
 * - **MaxTokens / Temperature**: sliders nativos con valor `tabular-nums`.
 * - **ThinkingChip**: `ChipGroup ["Auto","On","Off"]`; muestra un warning si el
 *   modelo es Gemma (conversational) y se fuerza `On` (content vacío, ADR-012 D4).
 */
export function PlaygroundControls({ models, config, onChange, className }: Props) {
  const set = <K extends keyof PlaygroundConfig>(key: K, value: PlaygroundConfig[K]) =>
    onChange({ ...config, [key]: value });

  const modelOptions = models.map((m) => ({ value: m.served_name, label: m.served_name }));
  const selectedModel = models.find((m) => m.served_name === config.model);
  const isGemma = selectedModel?.role === "conversational";
  const gemmaThinkingWarning = isGemma && config.thinking === "on";

  return (
    <Card className={cn("flex flex-col gap-6", className)}>
      <header className="flex flex-col gap-1">
        <p className="text-caption text-[var(--color-ink-soft)]">Controles</p>
        <h3 className="text-subtitle text-[var(--color-ink-deep)]">Parámetros del turno</h3>
      </header>

      <ChipGroup
        label="Modelo"
        options={modelOptions}
        value={config.model}
        onChange={(v) => set("model", v)}
      />

      <Switch
        label="Bajo rendimiento"
        hint={LOW_PERF_HINT}
        checked={config.lowPerf}
        onChange={(v) => set("lowPerf", v)}
      />

      <div className={cn("flex flex-col gap-5", config.lowPerf && "opacity-50")}>
        <Slider
          label="Máx. tokens"
          min={1}
          max={4096}
          step={1}
          value={config.maxTokens}
          disabled={config.lowPerf}
          onChange={(v) => set("maxTokens", v)}
        />
        <Slider
          label="Temperatura"
          min={0}
          max={2}
          step={0.1}
          value={config.temperature}
          disabled={config.lowPerf}
          onChange={(v) => set("temperature", v)}
          format={(v) => v.toFixed(1)}
        />
      </div>

      <div className="flex flex-col gap-2">
        <ChipGroup
          label="Thinking"
          options={THINKING_OPTIONS}
          value={config.thinking}
          onChange={(v) => set("thinking", v)}
        />
        {gemmaThinkingWarning ? (
          <p className="text-caption" style={{ color: "var(--color-error)" }}>
            Gemma es conversacional: forzar thinking puede devolver contenido vacío.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

/**
 * Slider nativo (range) con label + valor `tabular-nums`. Usa el azul plano de
 * marca para el acento (`accent-color`); el valor a la derecha no "baila" al
 * arrastrar gracias a las cifras tabulares.
 */
function Slider({
  label,
  min,
  max,
  step,
  value,
  disabled,
  onChange,
  format,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
  format?: (value: number) => string;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="flex items-center justify-between gap-4">
        <span className="text-caption text-[var(--color-ink-soft)]">{label}</span>
        <span className="text-body-sm tabular-nums text-[var(--color-ink)]">
          {format ? format(value) : value}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--color-blue-flat)] disabled:cursor-not-allowed"
        style={{ accentColor: "var(--color-blue-flat)" } as CSSProperties}
      />
    </label>
  );
}
