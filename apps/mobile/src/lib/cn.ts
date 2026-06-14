/**
 * Une clases condicionales para `className` (NativeWind). Versión mínima sin
 * tailwind-merge: en mobile controlamos las clases que pasamos, así que no
 * necesitamos dedup de conflictos como en la web.
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
