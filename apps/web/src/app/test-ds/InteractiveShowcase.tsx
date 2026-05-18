"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ChipGroup } from "@/components/ui/ChipGroup";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { ModeChip } from "@/components/ui/ModeChip";
import { MODES } from "@/components/ui/modes";
import { OptionCard } from "@/components/ui/OptionCard";
import { ProgressDots } from "@/components/ui/ProgressDots";
import { SuggestionCard } from "@/components/ui/SuggestionCard";
import { Textarea } from "@/components/ui/Textarea";
import { TextField } from "@/components/ui/TextField";
import { Toast } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";

type Size = "sm" | "md" | "lg";

export function InteractiveShowcase() {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [toggle1, setToggle1] = useState(true);
  const [toggle2, setToggle2] = useState(false);
  const [size, setSize] = useState<Size>("md");
  const [step, setStep] = useState(0);
  const [toastOpen, setToastOpen] = useState(false);

  return (
    <div className="flex flex-col gap-16">
      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">
          OptionCard (multi-select)
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {["Tranquilo", "Ocupado", "Estresado", "Creativo"].map((opt) => (
            <OptionCard
              key={opt}
              title={opt}
              hint={`Hint para ${opt.toLowerCase()}`}
              selected={selectedOption === opt}
              onClick={() => setSelectedOption(selectedOption === opt ? null : opt)}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">
          OptionCard con leading (ModeChip)
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {MODES.slice(0, 4).map((mode) => (
            <OptionCard
              key={mode.id}
              title={mode.label}
              hint={mode.blurb}
              leading={<ModeChip modeId={mode.id} size="sm" label=" " />}
              selected={selectedOption === mode.id}
              onClick={() => setSelectedOption(selectedOption === mode.id ? null : mode.id)}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">TextField + Textarea</h2>
        <div className="flex max-w-[480px] flex-col gap-6">
          <TextField
            label="TU NOMBRE"
            placeholder="Ej. Mateo"
            value={name}
            onChange={(e) => setName(e.target.value)}
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
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={160}
            hint={`${bio.length}/160`}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">Toggle + ChipGroup</h2>
        <div className="flex max-w-[480px] flex-col gap-6">
          <Toggle
            label="Contraste alto"
            hint="Bordes más marcados, texto más oscuro."
            checked={toggle1}
            onChange={setToggle1}
          />
          <Toggle
            label="Reducir animaciones"
            hint="Sigue la preferencia del sistema por default."
            checked={toggle2}
            onChange={setToggle2}
          />
          <ChipGroup
            label="TAMAÑO DE TEXTO"
            options={[
              { value: "sm", label: "Chico" },
              { value: "md", label: "Normal" },
              { value: "lg", label: "Grande" },
            ]}
            value={size}
            onChange={(v) => setSize(v as Size)}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">ProgressDots</h2>
        <div className="flex flex-col gap-4">
          <ProgressDots total={5} current={step} />
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => setStep((s) => Math.max(0, s - 1))}>
              Atrás
            </Button>
            <Button variant="primary" onClick={() => setStep((s) => Math.min(4, s + 1))}>
              Siguiente
            </Button>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">
          ModeChip (todos los modos)
        </h2>
        <div className="flex flex-wrap gap-2">
          {MODES.map((mode) => (
            <ModeChip key={mode.id} modeId={mode.id} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">
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
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">EmptyStateCard</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <EmptyStateCard
            title="Vacío. Empezá una abajo ↓"
            hint="Tus conversaciones van a aparecer acá."
          />
          <EmptyStateCard
            title="Sin recordatorios todavía"
            hint="Probá pedirle al modo productividad."
            action={<Button variant="secondary">Crear uno</Button>}
          />
        </div>
      </section>

      <section>
        <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">Toast</h2>
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => setToastOpen(true)}>Mostrar toast</Button>
            <p className="text-body-sm text-[var(--color-ink-soft)]">Auto-dismiss en 3s.</p>
          </div>
        </Card>
        <Toast
          message="Listo. Bloqueé 10–12 para vos."
          variant="success"
          visible={toastOpen}
          onDismiss={() => setToastOpen(false)}
        />
      </section>
    </div>
  );
}
