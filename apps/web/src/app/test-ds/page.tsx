import type { Metadata } from "next";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LivingField } from "@/components/ui/LivingField";
import { MODES } from "@/components/ui/modes";
import { YnaraMark } from "@/components/ui/YnaraMark";
import { YnaraOrb } from "@/components/ui/YnaraOrb";
import { YnaraWordmark } from "@/components/ui/YnaraWordmark";
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

/* Gradientes que sobreviven en v4: el azul de acento del sandbox (§3.4). El
   logo ya no depende de estos — desde el PR #6 sus stops salen directo de la
   paleta oficial (azul/celeste/violeta/violáceo). */
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

        {/* Variantes del símbolo y el lockup (§11.1). `data-logo-gallery` es el
            anclaje del snapshot visual (scripts/snap-logo.mjs). El símbolo a
            color jamás va sobre Noche; ahí van las variantes mono-light. */}
        <div data-logo-gallery className="mt-10 flex flex-col gap-6">
          <div className="flex flex-wrap items-end gap-8">
            <LogoSwatch label="color">
              <YnaraMark size={56} variant="color" />
            </LogoSwatch>
            <LogoSwatch label="mono-dark">
              <YnaraMark size={56} variant="mono-dark" />
            </LogoSwatch>
            <LogoSwatch label="mono-light" dark>
              <YnaraMark size={56} variant="mono-light" />
            </LogoSwatch>
            <LogoSwatch label="avatar">
              <YnaraMark size={56} variant="avatar" />
            </LogoSwatch>
          </div>

          <div className="flex flex-wrap items-end gap-8">
            <LogoSwatch label="wordmark · color">
              <YnaraWordmark height={32} variant="color" />
            </LogoSwatch>
            <LogoSwatch label="wordmark · mono-light" dark>
              <YnaraWordmark height={32} variant="mono-light" />
            </LogoSwatch>
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

/**
 * Celda de muestra del logo: cada variante sobre su fondo correcto + label.
 * El fondo es FIJO (no sigue el tema): las variantes de logo son por-fondo,
 * no por-tema (§11.1). `dark` pone Noche (para mono-light/avatar); el resto va
 * sobre marfil — así el símbolo a color nunca cae sobre Noche y el mono-dark
 * nunca queda invisible, en cualquier tema del sandbox.
 */
function LogoSwatch({
  label,
  dark,
  children,
}: {
  label: string;
  dark?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2">
      <div
        className="flex min-h-[88px] min-w-[112px] items-center justify-center rounded-[var(--radius-lg)] border border-[var(--color-border)] px-5 py-4"
        style={{ backgroundColor: dark ? "var(--color-noche)" : "var(--color-marfil)" }}
      >
        {children}
      </div>
      <span className="text-caption text-[var(--color-ink-muted)]">{label}</span>
    </div>
  );
}
