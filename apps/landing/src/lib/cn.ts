import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes con resolución de conflictos. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
