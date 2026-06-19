import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guard anti-gradiente del panel admin (clon del de apps/web, mismo contrato de
 * marca). El gradiente vive SOLO en los tres portadores de marca: el fondo vivo
 * (LivingField) y el logo (YnaraMark + el orbe YnaraOrb). En componentes,
 * charts y features todo color es PLANO — un gradiente como fill/borde/texto es
 * anti-patrón (blueprint §0: charts 100% color plano por token, gradient-guard).
 *
 * Es la red grep-based que corre en la CI de frontend en cada PR: si aparece un
 * `linear-gradient`/`radial-gradient`/`conic-gradient` (o las clases utilitarias
 * de gradiente, o un campo `gradientClass`) fuera del allowlist, el test falla.
 */

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCAN_DIRS = ["components", "features"] as const;

/** Clases utilitarias de gradiente + cualquier gradiente CSS inline escrito en
 *  JS (`style`/`background`) — la regex de clases sola dejaba pasar un
 *  `radial-gradient(...)` hardcodeado en una prop de estilo. */
const FORBIDDEN =
  /bg-mode-|bg-gradient-|text-gradient-|gradientClass|(?:linear|radial|conic)-gradient\(/;

/** Únicos archivos donde el gradiente es legítimo (blueprint §0.1 + §2.2): el
 *  fondo vivo (`LivingField`), el símbolo del logo (`YnaraMark`) y el glow
 *  ambiental del orbe (`YnaraOrb`). Son los 3 portadores de gradiente que admin
 *  porta 1:1 de web; cualquier otro componente debe usar tokens planos. */
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

describe("guard anti-gradiente (blueprint §0.1)", () => {
  it("ningún componente, chart o feature usa gradiente fuera de los 3 portadores", () => {
    const hits: string[] = [];
    for (const scanDir of SCAN_DIRS) {
      const root = join(SRC_DIR, scanDir);
      // Tolerar dirs que todavía no existen (se crean a medida que avanzan las
      // pantallas en F1): el guard igual cubre lo que ya esté escrito.
      if (!existsSync(root)) continue;
      for (const file of walk(root)) {
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
