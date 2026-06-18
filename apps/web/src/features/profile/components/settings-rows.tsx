import Link from "next/link";

// ---------------------------------------------------------------------------
// Filas calmas del perfil (sin caja, separadas por hairline). Extraídas de
// TuView para mantener ese archivo bajo el umbral de 500 líneas (AI-GUIDELINES
// #3) y poder reusarlas.
// ---------------------------------------------------------------------------

/**
 * Fila aireada del perfil: ícono opcional + título + subtítulo + acción/chevron.
 * Separada de la fila anterior por un borde hairline (`border-t`) salvo la primera.
 */
export function SettingsRow({
  icon,
  title,
  sub,
  action,
  first = false,
  as: Tag = "div",
  onClick,
  href,
}: {
  icon?: React.ReactNode;
  title: string;
  sub?: string;
  action?: React.ReactNode;
  first?: boolean;
  as?: "div" | "button";
  onClick?: () => void;
  href?: string;
}) {
  const rowClass = [
    "flex items-center gap-3 py-4",
    !first ? "border-t border-[var(--color-border)]" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const inner = (
    <>
      {icon && (
        <div
          className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-bg-soft)]"
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-body font-medium text-[var(--color-ink)]">{title}</p>
        {sub && <p className="text-body-sm mt-0.5 text-[var(--color-ink-soft)]">{sub}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={`${rowClass} w-full`}>
        {inner}
      </Link>
    );
  }

  if (Tag === "button" || onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${rowClass} w-full bg-transparent text-left`}
      >
        {inner}
      </button>
    );
  }

  return <div className={rowClass}>{inner}</div>;
}

/**
 * Grupo de filas calmas con label de sección en caption uppercase.
 */
export function SettingsGroup({
  label,
  children,
  dataHeroReveal = true,
}: {
  label: string;
  children: React.ReactNode;
  dataHeroReveal?: boolean;
}) {
  return (
    <section {...(dataHeroReveal ? { "data-hero-reveal": true } : {})}>
      <p className="text-caption mb-1 font-semibold uppercase tracking-widest text-[var(--color-ink-soft)]">
        {label}
      </p>
      <div>{children}</div>
    </section>
  );
}

/**
 * Bloque de a11y con sus 3 controles — mantiene card sutil para agrupar.
 */
export function A11yCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-hero-reveal
      className="flex flex-col gap-6 rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-[var(--color-bg)] p-6"
    >
      {children}
    </div>
  );
}

/**
 * Ícono SVG de chevron derecho para las filas con navegación/acción.
 */
export function ChevronRight() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      className="text-[var(--color-ink-faint)]"
    >
      <path
        d="M6 4l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
