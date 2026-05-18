import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combina classNames con clsx y deduplica utilities Tailwind con tailwind-merge.
 * Reemplaza el helper inline de Sesión 1 (Button, Card).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
