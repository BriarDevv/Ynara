import type { Metadata } from "next";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LivingField } from "@/components/ui/LivingField";
import { MODES } from "@/components/ui/modes";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { InteractiveShowcase } from "./InteractiveShowcase";
import { ThemeToggle } from "./ThemeToggle";

export const metadata: Metadata = {
  title: "Design System · Test",
  description: "Sandbox del sistema visual de Ynara.",
  robots: { index: false, follow: false },
};

const COLOR_TOKENS = [
  { name: "ink", value: "var(--color-ink)" },
  { name: "ink-soft", value: "var(--color-ink-soft)" },
  { name: "ink-muted", value: "var(--color-ink-muted)" },
  { name: "ink-faint", value: "var(--color-ink-faint)" },
  { name: "bg", value: "var(--color-bg)" },
  { name: "bg-soft", value: "var(--color-bg-soft)" },
  { name: "border", value: "var(--color-border)" },
  { name: "border-strong", value: "var(--color-border-strong)" },
] as const;

/* Gradientes que sobreviven en v4: solo los del logo/acento azul (§3.4).
   Jade, ámbar y violeta se retiraron al realinear los modos a la paleta. */
const GRADIENT_TOKENS = [
  { name: "blue-base", className: "bg-gradient-blue-base" },
  { name: "blue-relief", className: "bg-gradient-blue-relief" },
] as const;

/* Vitrina del fondo vivo (DESIGN.md §2.2): una caja por variante, cada una
   teñida por un modo distinto para ver el clima de dos tonos. `paper` y
   `depth` esperan a Agenda y Tu — acá ya se pueden revisar igual. */
const FIELD_VARIANTS = [
  { variant: "aurora", modeId: "productividad", note: "Hoy — ondas + atmósfera" },
  { variant: "constellation", modeId: "bienestar", note: "Hablar y onboarding — estrellas" },
  { variant: "network", modeId: "memoria", note: "Memoria — red enlazada" },
  { variant: "paper", modeId: "vida", note: "Agenda (pendiente) — grano" },
  { variant: "depth", modeId: "estudio", note: "Tu (pendiente) — profundidad" },
] as const;

const TYPE_TOKENS = [
  { className: "text-display", label: "Display — 42→56 fluido" },
  { className: "text-hero", label: "Hero — 48/52" },
  { className: "text-title", label: "Title — 34/38" },
  { className: "text-subtitle", label: "Subtitle — 22/28" },
  { className: "text-body", label: "Body — 16/24" },
  { className: "text-body-sm", label: "Body small — 14/20" },
  { className: "text-caption", label: "Caption — 12/16 caps" },
] as const;

export default function TestDsPage() {
  return (
    <main className="mx-auto max-w-[1120px] px-6 py-16">
      {/* Switch claro/Noche (§3.1) — el sandbox se revisa en ambos temas. */}
      <div className="mb-10 flex justify-end">
        <ThemeToggle />
      </div>

      <Section title="Marca">
        <div className="flex items-end gap-8">
          <YnaraMark size={120} />
          <div className="flex flex-col gap-2">
            <h1 className="text-hero">Ynara.</h1>
            <p className="text-body text-[var(--color-ink-soft)]">
              Sandbox visual del sistema. Cada cambio en <code>globals.css</code> o{" "}
              <code>DESIGN.md</code> tiene que verse acá.
            </p>
          </div>
        </div>
      </Section>

      <Section title="Tipografía">
        <div className="flex flex-col gap-4">
          {TYPE_TOKENS.map((t) => (
            <div key={t.className} className="flex items-baseline gap-6">
              <span className="text-caption w-32 shrink-0 text-[var(--color-ink-muted)]">
                {t.label}
              </span>
              <span className={t.className}>Ynara aprende de vos.</span>
            </div>
          ))}
        </div>
        {/* Display en contexto editorial (DESIGN.md §4): big type para piezas
            poster — auth, outro del onboarding, welcome del chat. */}
        <div className="mt-10 max-w-[18ch] border-t border-[var(--color-border)] pt-8">
          <p className="text-display text-[var(--color-ink)]">Antes que nada, hola.</p>
        </div>
      </Section>

      <Section title="Paleta · ink &amp; surfaces">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {COLOR_TOKENS.map((c) => (
            <Card key={c.name}>
              <div
                className="mb-3 h-14 rounded-[var(--radius-md)] border border-[var(--color-border)]"
                style={{ backgroundColor: c.value }}
              />
              <p className="text-body-sm">{c.name}</p>
              <p className="text-caption text-[var(--color-ink-muted)]">{c.value}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title="Gradientes">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {GRADIENT_TOKENS.map((g) => (
            <Card key={g.name}>
              <div className={`mb-3 h-14 rounded-[var(--radius-md)] ${g.className}`} />
              <p className="text-body-sm">{g.name}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title="Modos">
        {/* Tint plano por modo (§3.5): dot ambiental + fill con texto blanco
            (el fill de Memoria es lavanda-deep, único modo con dos tonos). */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {MODES.map((mode) => (
            <Card key={mode.id}>
              <div className="mb-4 flex items-center gap-3">
                <div
                  className="h-12 w-12 rounded-[var(--radius-pill)]"
                  style={{ backgroundColor: mode.tintVar }}
                />
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-pill)] text-caption text-[var(--color-on-dark)]"
                  style={{ backgroundColor: mode.fillVar }}
                >
                  Aa
                </div>
              </div>
              <p className="text-subtitle">{mode.label}</p>
              <p className="text-body-sm text-[var(--color-ink-soft)]">{mode.blurb}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title="Fondo vivo">
        {/* Cada caja es un contenedor relative+isolate, el mismo contrato de
            montaje que las vistas reales (§16 #5: absolute, nunca fixed). */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FIELD_VARIANTS.map((f) => (
            <div
              key={f.variant}
              className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)]"
            >
              <div className="relative isolate h-[220px]">
                <LivingField variant={f.variant} modeId={f.modeId} />
              </div>
              <div className="border-t border-[var(--color-border)] px-4 py-3">
                <p className="text-body-sm">{f.variant}</p>
                <p className="text-caption text-[var(--color-ink-muted)]">{f.note}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Orbe de presencia">
        <div className="flex flex-wrap items-end gap-10">
          <div className="flex flex-col items-center gap-3">
            <YnaraOrb size={72} />
            <p className="text-caption text-[var(--color-ink-muted)]">calmo</p>
          </div>
          <div className="flex flex-col items-center gap-3">
            <YnaraOrb size={72} thinking />
            <p className="text-caption text-[var(--color-ink-muted)]">pensando</p>
          </div>
          {MODES.map((mode) => (
            <div key={mode.id} className="flex flex-col items-center gap-3">
              <YnaraOrb size={44} modeId={mode.id} />
              <p className="text-caption text-[var(--color-ink-muted)]">{mode.label}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Botones">
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="primary">Empezar</Button>
          <Button variant="secondary">Atrás</Button>
          <Button variant="ghost">Saltar onboarding</Button>
          <Button variant="primary" disabled>
            Disabled
          </Button>
        </div>
        <div className="mt-6 flex max-w-[480px] flex-col gap-3">
          <Button variant="primary" fullWidth>
            CTA full width
          </Button>
          <Button variant="secondary" fullWidth>
            Secondary full width
          </Button>
        </div>
      </Section>

      <Section title="Cards">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card>
            <p className="text-caption text-[var(--color-ink-muted)]">Card default</p>
            <p className="text-subtitle mt-2">Estática</p>
            <p className="text-body-sm mt-1 text-[var(--color-ink-soft)]">
              Para contenido informativo sin interacción.
            </p>
          </Card>
          <Card variant="interactive">
            <p className="text-caption text-[var(--color-ink-muted)]">Card interactive</p>
            <p className="text-subtitle mt-2">Hover me</p>
            <p className="text-body-sm mt-1 text-[var(--color-ink-soft)]">
              Levita en hover. Para SuggestionCard, OptionCard, etc.
            </p>
          </Card>
        </div>
      </Section>

      <Section title="Animaciones">
        <div className="flex flex-wrap gap-6">
          <div className="anim-fade-up rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-6 py-4">
            <p className="text-body-sm">anim-fade-up</p>
          </div>
          <div className="anim-slide-in-right rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-6 py-4">
            <p className="text-body-sm">anim-slide-in-right</p>
          </div>
          <div className="anim-pulse-soft rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-soft)] px-6 py-4">
            <p className="text-body-sm">anim-pulse-soft</p>
          </div>
        </div>
      </Section>

      <Section title="Primitives interactivos">
        <InteractiveShowcase />
      </Section>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-16">
      <h2 className="text-caption mb-6 text-[var(--color-ink-muted)]">{title}</h2>
      {children}
    </section>
  );
}
