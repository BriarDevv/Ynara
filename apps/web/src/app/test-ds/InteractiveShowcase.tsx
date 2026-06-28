"use client";

import { useMemo, useReducer } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODES, type ModeId } from "@/components/ui/modes";
import { OptionCard } from "@/components/ui/OptionCard";
import { ProgressDots } from "@/components/ui/ProgressDots";
import { PromptChip } from "@/components/ui/PromptChip";
import { Sheet } from "@/components/ui/Sheet";
import { SuggestionCard } from "@/components/ui/SuggestionCard";
import { Textarea } from "@/components/ui/Textarea";
import { TextField } from "@/components/ui/TextField";
import { Toast } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";

type Size = "sm" | "md" | "lg";
type ToastVariant = "info" | "success" | "error";

const TOAST_MESSAGE: Record<ToastVariant, string> = {
  info: "Guardé eso en tu memoria.",
  success: "Listo. Bloqueé 10–12 para vos.",
  error: "No pude conectar. Probá de nuevo.",
};

/**
 * Estado agrupado del showcase. Antes eran 11 `useState` sueltos; al
 * consolidarlos en un reducer, un cambio lógico (ej. abrir un toast setea
 * `toastVariant` + `toastOpen`) no se reparte en renders separados.
 */
type ShowcaseState = {
  selectedOption: string | null;
  name: string;
  bio: string;
  toggle1: boolean;
  toggle2: boolean;
  size: Size;
  step: number;
  toastOpen: boolean;
  toastVariant: ToastVariant;
  picked: string | null;
  sheetOpen: boolean;
};

const INITIAL_STATE: ShowcaseState = {
  selectedOption: null,
  name: "",
  bio: "",
  toggle1: true,
  toggle2: false,
  size: "md",
  step: 0,
  toastOpen: false,
  toastVariant: "success",
  picked: null,
  sheetOpen: false,
};

type ShowcaseAction =
  | { type: "toggleOption"; option: string }
  | { type: "setName"; value: string }
  | { type: "setBio"; value: string }
  | { type: "setToggle1"; value: boolean }
  | { type: "setToggle2"; value: boolean }
  | { type: "setSize"; value: Size }
  | { type: "prevStep" }
  | { type: "nextStep" }
  | { type: "showToast"; variant: ToastVariant }
  | { type: "dismissToast" }
  | { type: "pick"; value: string }
  | { type: "openSheet" }
  | { type: "closeSheet" };

function reducer(state: ShowcaseState, action: ShowcaseAction): ShowcaseState {
  switch (action.type) {
    case "toggleOption":
      return {
        ...state,
        selectedOption: state.selectedOption === action.option ? null : action.option,
      };
    case "setName":
      return { ...state, name: action.value };
    case "setBio":
      return { ...state, bio: action.value };
    case "setToggle1":
      return { ...state, toggle1: action.value };
    case "setToggle2":
      return { ...state, toggle2: action.value };
    case "setSize":
      return { ...state, size: action.value };
    case "prevStep":
      return { ...state, step: Math.max(0, state.step - 1) };
    case "nextStep":
      return { ...state, step: Math.min(4, state.step + 1) };
    case "showToast":
      return { ...state, toastVariant: action.variant, toastOpen: true };
    case "dismissToast":
      return { ...state, toastOpen: false };
    case "pick":
      return { ...state, picked: action.value };
    case "openSheet":
      return { ...state, sheetOpen: true };
    case "closeSheet":
      return { ...state, sheetOpen: false };
    default:
      return state;
  }
}

/**
 * Slot `leading` del OptionCard extraído a su propio componente: así el JSX
 * del ModeChip se construye dentro del render de este hijo y no como prop
 * inline en el render del showcase (regla jsx-no-jsx-as-prop).
 */
function ModeLeading({ modeId }: { modeId: ModeId }) {
  return <ModeChip modeId={modeId} size="sm" label=" " />;
}

/**
 * OptionCard de un modo. El `leading` (JSX) se memoiza por `modeId` para no
 * pasar un nodo nuevo en cada render (regla jsx-no-jsx-as-prop); como es un
 * item de lista, el memo vive en este componente y no en el `.map` del padre.
 */
function ModeOptionCard({
  mode,
  selected,
  onClick,
}: {
  mode: (typeof MODES)[number];
  selected: boolean;
  onClick: () => void;
}) {
  const leading = useMemo(() => <ModeLeading modeId={mode.id} />, [mode.id]);
  return (
    <OptionCard
      title={mode.label}
      hint={mode.blurb}
      leading={leading}
      selected={selected}
      onClick={onClick}
    />
  );
}

export function InteractiveShowcase() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);

  return (
    <div className="flex flex-col gap-16">
      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          OptionCard (multi-select)
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {["Tranquilo", "Ocupado", "Estresado", "Creativo"].map((opt) => (
            <OptionCard
              key={opt}
              title={opt}
              hint={`Hint para ${opt.toLowerCase()}`}
              selected={state.selectedOption === opt}
              onClick={() => dispatch({ type: "toggleOption", option: opt })}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          OptionCard con leading (ModeChip)
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {MODES.slice(0, 4).map((mode) => (
            <ModeOptionCard
              key={mode.id}
              mode={mode}
              selected={state.selectedOption === mode.id}
              onClick={() => dispatch({ type: "toggleOption", option: mode.id })}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">TextField + Textarea</h2>
        <div className="flex max-w-[480px] flex-col gap-6">
          <TextField
            label="TU NOMBRE"
            placeholder="Ej. Mateo"
            value={state.name}
            onChange={(e) => dispatch({ type: "setName", value: e.target.value })}
            hint="Lo uso solo cuando hablo con vos."
          />
          <TextField
            label="EMAIL"
            type="email"
            placeholder="vos@ejemplo.com"
            value=""
            onChange={() => {}}
            error="Esa dirección no parece válida"
          />
          <Textarea
            label="¿ALGO MÁS?"
            placeholder="Contame en una línea"
            value={state.bio}
            onChange={(e) => dispatch({ type: "setBio", value: e.target.value })}
            maxLength={160}
            hint={`${state.bio.length}/160`}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">Toggle + ChipGroup</h2>
        <div className="flex max-w-[480px] flex-col gap-6">
          <Toggle
            label="Contraste alto"
            hint="Bordes más marcados, texto más oscuro."
            checked={state.toggle1}
            onChange={(value) => dispatch({ type: "setToggle1", value })}
          />
          <Toggle
            label="Reducir animaciones"
            hint="Sigue la preferencia del sistema por default."
            checked={state.toggle2}
            onChange={(value) => dispatch({ type: "setToggle2", value })}
          />
          <ChipGroup
            label="TAMAÑO DE TEXTO"
            options={[
              { value: "sm", label: "Chico" },
              { value: "md", label: "Normal" },
              { value: "lg", label: "Grande" },
            ]}
            value={state.size}
            onChange={(v) => dispatch({ type: "setSize", value: v as Size })}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">ProgressDots</h2>
        <div className="flex flex-col gap-4">
          <ProgressDots total={5} current={state.step} />
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => dispatch({ type: "prevStep" })}>
              Atrás
            </Button>
            <Button variant="primary" onClick={() => dispatch({ type: "nextStep" })}>
              Siguiente
            </Button>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          ModeChip (todos los modos)
        </h2>
        <div className="flex flex-wrap gap-2">
          {MODES.map((mode) => (
            <ModeChip key={mode.id} modeId={mode.id} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          SuggestionCard (por modo)
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <SuggestionCard
            modeId="productividad"
            title="Agendame algo"
            subtitle="Probá pedirle al modo productividad"
            onClick={() => console.info("click productividad")}
          />
          <SuggestionCard
            modeId="estudio"
            title="Explicame un tema"
            subtitle="El modo estudio te tutorea"
            onClick={() => console.info("click estudio")}
          />
          <SuggestionCard
            modeId="bienestar"
            title="¿Cómo estás?"
            subtitle="Charla casual, sin presión"
            onClick={() => console.info("click bienestar")}
          />
          <SuggestionCard
            modeId="memoria"
            title="Recordá esto sobre mí"
            subtitle="Memoria semántica explícita"
            onClick={() => console.info("click memoria")}
          />
          <SuggestionCard
            modeId="vida"
            title="Recomendame algo"
            subtitle="Sugerencias del día a día"
            disabled
            onClick={() => console.info("click vida (disabled)")}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          PromptChip (empty state de chat)
        </h2>
        <div className="flex flex-wrap gap-2">
          {["¿Qué hago hoy?", "Resumime el día", "Explicame un tema", "Conectá estas ideas"].map(
            (prompt) => (
              <PromptChip
                key={prompt}
                label={prompt}
                onClick={() => dispatch({ type: "pick", value: prompt })}
              />
            ),
          )}
        </div>
        {state.picked ? (
          <p className="text-body-sm mt-3 text-[var(--color-ink-soft)]">
            Elegiste: “{state.picked}”
          </p>
        ) : null}
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">EmptyStateCard</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <EmptyStateCard
            title="Todavía no hay conversaciones"
            hint="Las que empieces van a aparecer acá."
          />
          <EmptyStateCard
            title="Sin recordatorios todavía"
            hint="Probá pedirle al modo productividad."
            action={<Button variant="secondary">Crear uno</Button>}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">Toast</h2>
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              onClick={() => dispatch({ type: "showToast", variant: "info" })}
            >
              Info
            </Button>
            <Button
              variant="primary"
              onClick={() => dispatch({ type: "showToast", variant: "success" })}
            >
              Success
            </Button>
            <Button
              variant="secondary"
              onClick={() => dispatch({ type: "showToast", variant: "error" })}
            >
              Error
            </Button>
            <p className="text-body-sm text-[var(--color-ink-soft)]">
              Entrada 300ms / salida 200ms · auto-dismiss en 3s.
            </p>
          </div>
        </Card>
        <Toast
          message={TOAST_MESSAGE[state.toastVariant]}
          variant={state.toastVariant}
          visible={state.toastOpen}
          onDismiss={() => dispatch({ type: "dismissToast" })}
        />
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-soft)]">
          Sheet (bottom-sheet mobile / modal desktop)
        </h2>
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={() => dispatch({ type: "openSheet" })}>
              Abrir sheet
            </Button>
            <p className="text-body-sm text-[var(--color-ink-soft)]">
              Esc o click en el backdrop cierran. En mobile entra desde abajo con handle.
            </p>
          </div>
        </Card>
        <Sheet
          open={state.sheetOpen}
          onClose={() => dispatch({ type: "closeSheet" })}
          title="Cambiar modo"
          description="Elegí cómo te acompaña hoy."
        >
          <div className="flex flex-col gap-2">
            {MODES.map((mode) => (
              <ModeOptionCard
                key={mode.id}
                mode={mode}
                selected={state.picked === mode.id}
                onClick={() => dispatch({ type: "pick", value: mode.id })}
              />
            ))}
            <Button
              variant="ghost"
              fullWidth
              onClick={() => dispatch({ type: "closeSheet" })}
              className="mt-2"
            >
              Cerrar
            </Button>
          </div>
        </Sheet>
      </section>
    </div>
  );
}
