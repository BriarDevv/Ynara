/** Skeleton del detalle mientras carga (DESIGN §8.2: skeleton, no spinner). */
export function MemoryDetailSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col gap-8 px-6 pb-16 pt-6">
      <output className="sr-only">Cargando el recuerdo…</output>
      <div aria-hidden className="flex flex-col gap-8">
        <span className="anim-pulse-soft h-7 w-24 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
        <div className="anim-pulse-soft flex flex-col gap-3">
          <span className="h-7 w-full rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
          <span className="h-7 w-4/5 rounded-[var(--radius-pill)] bg-[var(--color-bg-soft)]" />
        </div>
        <div className="anim-pulse-soft grid grid-cols-2 gap-4">
          <span className="h-10 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)]" />
          <span className="h-10 rounded-[var(--radius-md)] bg-[var(--color-bg-soft)]" />
        </div>
      </div>
    </div>
  );
}
