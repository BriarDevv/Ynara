import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge extendido con las utilities tipográficas custom del repo.
 *
 * `.text-display`, `.text-hero`, `.text-title`, `.text-subtitle`, `.text-body`,
 * `.text-body-sm`, `.text-button` y `.text-caption` (definidas en
 * `globals.css @layer utilities`) empiezan con `text-`, así que tailwind-merge
 * —que no las conoce— las clasificaba como text-COLOR y las DESCARTABA al
 * combinarlas con un color arbitrario (p. ej. el ink token) dentro de un mismo
 * `cn(...)`, dejando el texto en el font-size default (16px). Declarándolas
 * como `font-size` se separan del grupo de color y conviven con el color
 * arbitrario (props CSS distintas). Entre sí siguen en conflicto (no se debe
 * usar dos a la vez).
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        { text: ["display", "hero", "title", "subtitle", "body", "body-sm", "button", "caption"] },
      ],
    },
  },
});

/**
 * Combina classNames con clsx y deduplica utilities Tailwind con tailwind-merge.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
