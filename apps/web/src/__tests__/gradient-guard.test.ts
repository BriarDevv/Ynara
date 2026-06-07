import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guard anti-gradiente (DESIGN.md §3.4/§13): el gradiente vive solo en el
 * fondo vivo (LivingField) y el logo (YnaraMark). En componentes y features
 * todo color es plano — un gradiente como fill/borde/texto es anti-patrón.
 *
 * Es la red grep-based que pide el plan v4 (§16 #3), como test de Vitest
 * para que corra en la CI de frontend en cada PR.
 */

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCAN_DIRS = ["components", "features"] as const;

/** Clases/campos del lenguaje v3 que no deben reaparecer, más cualquier
 *  gradiente CSS inline (`style`/`background`) — la regex de clases sola
 *  dejaba pasar un `radial-gradient(...)` escrito en JS. */
const FORBIDDEN =
  /bg-mode-|bg-gradient-|text-gradient-|gradientClass|(?:linear|radial|conic)-gradient\(/;

/** Únicos archivos donde el gradiente es legítimo (§3.4): el fondo vivo,
 *  el logo y el glow ambiental del orbe. */
const ALLOWLIST = new Set(["LivingField.tsx", "YnaraMark.tsx", "YnaraOrb.tsx"]);

function* walk(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(path);
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      yield path;
    }
  }
}

describe("guard anti-gradiente (§3.4)", () => {
  it("ningún componente o feature usa clases de gradiente ni gradientClass", () => {
    const hits: string[] = [];
    for (const scanDir of SCAN_DIRS) {
      for (const file of walk(join(SRC_DIR, scanDir))) {
        if (ALLOWLIST.has(file.split(sep).at(-1) ?? "")) continue;
        const lines = readFileSync(file, "utf8").split("\n");
        lines.forEach((line, i) => {
          if (FORBIDDEN.test(line)) {
            hits.push(`${relative(SRC_DIR, file)}:${i + 1} → ${line.trim()}`);
          }
        });
      }
    }
    expect(hits).toEqual([]);
  });
});
