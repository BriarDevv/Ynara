import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guarda la coherencia del puente de tokens entre `:root` y `@theme inline`.
 *
 * Tailwind v4 (CSS-first) solo genera utilities (`bg-*`, `text-*`, …) para los
 * tokens listados en `@theme inline`, donde cada uno re-expone una var de
 * `:root` (`--color-x: var(--color-x)`). Si un token se referencia en `@theme`
 * pero no está definido en `:root`, la utility se genera pero resuelve a vacío:
 * un bug silencioso que ningún test de componente atrapa (vitest corre con
 * `css:false`, así que el CSS computado no existe en jsdom).
 *
 * Este test estático cierra ese hueco: todo `var(--color-*)` / `var(--radius-*)`
 * referenciado en `@theme inline` debe estar definido en `:root`.
 */

const rawCss = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "globals.css"), "utf8");
// Sin comentarios CSS: evita que llaves dentro de un comentario rompan el balanceo de `block()`.
const css = rawCss.replace(/\/\*[\s\S]*?\*\//g, "");

/** Devuelve el contenido (con llaves balanceadas) del primer bloque que abre `opening`. */
function block(opening: RegExp): string {
  const match = opening.exec(css);
  if (!match) throw new Error(`No se encontró el bloque \`${opening}\` en globals.css`);
  const open = match.index + match[0].length - 1; // posición de la `{`
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) return css.slice(open + 1, i);
    }
  }
  throw new Error(`Bloque \`${opening}\` sin cerrar en globals.css`);
}

const rootBlock = block(/:root\s*\{/);
const themeBlock = block(/@theme\s+inline\s*\{/);

const rootDefs = new Set([...rootBlock.matchAll(/--([\w-]+)\s*:/g)].map((m) => m[1] ?? ""));

// Solo los families que `:root` debe definir (las fuentes vienen de next/font,
// no de globals.css, así que se excluyen del chequeo).
const themeRefs = [...themeBlock.matchAll(/var\(--([\w-]+)/g)]
  .map((m) => m[1] ?? "")
  .filter((name) => name.startsWith("color-") || name.startsWith("radius-"));

describe("globals.css — puente de tokens :root ↔ @theme inline", () => {
  it("expone tokens de color y radius como utilities", () => {
    expect(themeRefs.length).toBeGreaterThan(0);
  });

  it("todo token de color/radius referenciado en @theme está definido en :root", () => {
    const faltantes = themeRefs.filter((name) => !rootDefs.has(name));
    expect(faltantes).toEqual([]);
  });

  it("define la paleta oficial v4 en :root y la expone en @theme inline", () => {
    const oficiales = [
      "color-azul",
      "color-indigo",
      "color-violaceo",
      "color-violeta",
      "color-celeste",
      "color-lavanda",
      "color-lavanda-deep",
      "color-noche",
      "color-marfil",
    ];
    const sinDefinir = oficiales.filter((t) => !rootDefs.has(t));
    const sinExponer = oficiales.filter((t) => !themeRefs.includes(t));
    expect({ sinDefinir, sinExponer }).toEqual({ sinDefinir: [], sinExponer: [] });
  });

  it("define todas las duraciones de motion (ningún componente anima en 0ms)", () => {
    const duraciones = [
      "duration-instant",
      "duration-fast",
      "duration-base",
      "duration-slow",
      "duration-screen",
    ];
    const faltantes = duraciones.filter((t) => !rootDefs.has(t));
    expect(faltantes).toEqual([]);
  });
});
