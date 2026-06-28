/**
 * Fallback de carga del grupo `(app)` (build-plan / DESIGN.md §16 #8).
 *
 * Prerequisito del crossfade de pantalla: las 3 rutas `force-dynamic` de este
 * grupo (`buscar`, `chat/[sessionId]`, `memoria/[id]`) se renderizan en el
 * server en cada navegación; sin un `loading.tsx`, ese tramo mostraría un frame
 * en blanco. Como `loading.tsx` del grupo, este fallback es el boundary de
 * Suspense de TODOS los segmentos anidados, así que las cubre a las tres. (La
 * 4ta ruta force-dynamic, `onboarding/[step]`, vive fuera de `(app)` con su
 * propio layout y queda afuera, fuera de scope de #8.) Ocupa el área de
 * contenido del shell (no el viewport entero: vive dentro del `<main>`) y entra
 * con el mismo fade del `template` que lo envuelve.
 *
 * `role="status"` para que el lector de pantalla anuncie la carga sin robar el
 * foco.
 */
export default function AppLoading() {
  return (
    <div aria-busy="true" className="flex flex-1 items-center justify-center py-20">
      <p role="status" className="text-body text-[var(--color-ink-soft)]">
        Cargando…
      </p>
    </div>
  );
}
