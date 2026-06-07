import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MODE_CLIMATE } from "@/components/ui/modes";

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

  it("los tints de modo son color plano de la paleta oficial, no gradientes (§3.5)", () => {
    const tintEsperado: Record<string, string> = {
      productividad: "color-azul",
      estudio: "color-indigo",
      bienestar: "color-violeta",
      vida: "color-violaceo",
      memoria: "color-lavanda",
    };
    for (const [modo, token] of Object.entries(tintEsperado)) {
      expect(rootBlock).toMatch(new RegExp(`--mode-${modo}\\s*:\\s*var\\(--${token}\\)`));
    }
    // Fill: el único modo con dos tonos es Memoria (lavanda-deep, AA con blanco).
    for (const [modo, token] of Object.entries(tintEsperado)) {
      const fill = modo === "memoria" ? "color-lavanda-deep" : token;
      expect(rootBlock).toMatch(new RegExp(`--mode-${modo}-fill\\s*:\\s*var\\(--${fill}\\)`));
    }
    // Ningún tint de modo apunta a un gradiente (anti-patrón §3.4).
    expect(rootBlock).not.toMatch(/--mode-[\w-]+\s*:\s*var\(--gradient/);
  });

  it("--color-memory usa lavanda-deep (fill/texto de Memoria, AA — §3.5)", () => {
    expect(rootBlock).toMatch(/--color-memory\s*:\s*var\(--color-lavanda-deep\)/);
  });

  it("jade, ámbar y el gradiente violeta quedaron retirados (fuera del manual)", () => {
    expect(css).not.toMatch(/--color-(jade|amber)-(from|to)/);
    expect(css).not.toMatch(/--gradient-(jade|amber|violet)/);
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

describe("globals.css — tema Noche (§3.1 / §16 #4)", () => {
  const darkBlock = block(/html\.theme-dark\s*\{/);
  const darkDefs = new Set([...darkBlock.matchAll(/--([\w-]+)\s*:/g)].map((m) => m[1] ?? ""));

  it("re-declara superficies, tintas, bordes, memoria y elevación", () => {
    const esperados = [
      "color-bg",
      "color-bg-canvas",
      "color-bg-soft",
      "color-ink",
      "color-ink-deep",
      "color-ink-soft",
      "color-ink-muted",
      "color-ink-faint",
      "color-on-dark",
      "color-border",
      "color-border-strong",
      "color-memory",
      "shadow-soft",
      "shadow-lifted",
    ];
    const faltantes = esperados.filter((t) => !darkDefs.has(t));
    expect(faltantes).toEqual([]);
  });

  it("usa las superficies oficiales de Noche (nunca negro puro)", () => {
    expect(darkBlock).toMatch(/--color-bg-canvas\s*:\s*#242c3f/);
    expect(darkBlock).toMatch(/--color-bg\s*:\s*#2b3346/);
    expect(darkBlock).toMatch(/--color-bg-soft\s*:\s*#313a52/);
    expect(darkBlock).not.toMatch(/#000\b|#000000/);
  });

  it("la tinta pasa a la familia marfil", () => {
    expect(darkBlock).toMatch(/--color-ink\s*:\s*#f3f0ea/);
    expect(darkBlock).toMatch(/--color-ink-deep\s*:\s*#ffffff/);
    // Tolerante al espaciado interno del rgb() (no hay formatter de CSS).
    expect(darkBlock).toMatch(/--color-ink-soft\s*:\s*rgb\(\s*243\s+240\s+234\s*\/\s*0\.65\s*\)/);
  });

  it("--color-memory en Noche vuelve al lavanda claro (§3.5)", () => {
    expect(darkBlock).toMatch(/--color-memory\s*:\s*var\(--color-lavanda\)/);
  });

  it("todo token re-declarado en Noche existe también en :root (sin tokens nuevos)", () => {
    const soloEnDark = [...darkDefs].filter((t) => !rootDefs.has(t));
    expect(soloEnDark).toEqual([]);
  });

  it("no crea un segundo @theme (el @theme inline relee var() en runtime)", () => {
    expect(css.match(/@theme/g)).toHaveLength(1);
  });

  it("declara color-scheme por tema (light en :root, dark en Noche)", () => {
    expect(rootBlock).toMatch(/color-scheme\s*:\s*light/);
    expect(darkBlock).toMatch(/color-scheme\s*:\s*dark/);
  });

  it("el alto contraste también cubre Noche (§3.3)", () => {
    const hcDark = block(/html\.theme-dark\.theme-high-contrast\s*\{/);
    for (const token of [
      "color-ink-soft",
      "color-ink-muted",
      "color-border",
      "color-border-strong",
    ]) {
      expect(hcDark).toMatch(new RegExp(`--${token}\\s*:\\s*rgb\\(\\s*243\\s+240\\s+234`));
    }
  });
});

describe("clima del canvas (§3.5) — sincronía MODE_CLIMATE ↔ paleta", () => {
  /**
   * Valor hex de un token de la paleta oficial declarado en `:root`.
   * `MODE_CLIMATE` (modes.ts) duplica estos hex porque el canvas 2D no
   * resuelve `var(--color-*)`; este guard mantiene la paleta como fuente
   * única: si un stop cambia en globals.css, el clima desincronizado falla.
   */
  function paletteHex(token: string): string {
    const m = rootBlock.match(new RegExp(`--color-${token}\\s*:\\s*(#[0-9a-fA-F]{6})`));
    if (!m?.[1]) throw new Error(`token --color-${token} sin valor hex en :root`);
    return m[1].toLowerCase();
  }

  it("cada par del clima usa los stops oficiales (§3.5, columna gradiente)", () => {
    expect(MODE_CLIMATE).toEqual({
      productividad: { a: paletteHex("azul"), b: paletteHex("celeste") },
      estudio: { a: paletteHex("indigo"), b: paletteHex("celeste") },
      bienestar: { a: paletteHex("violeta"), b: paletteHex("lavanda") },
      vida: { a: paletteHex("violaceo"), b: paletteHex("violeta") },
      memoria: { a: paletteHex("celeste"), b: paletteHex("lavanda") },
    });
  });
});
