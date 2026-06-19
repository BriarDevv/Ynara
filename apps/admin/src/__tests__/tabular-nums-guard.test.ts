import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Guard de `tabular-nums` (blueprint §0 + §2.3): todo número del panel —
 * métricas (KPI), valores de chart, conteos, latencias, paginación — usa la
 * utility `tabular-nums` para que los dígitos no "bailen" al refrescar el dato.
 * Es una regla de diseño dura, igual de fuerte que el gradient-guard.
 *
 * Heurística (admin-específica, no existe en web): si un archivo de
 * `components/charts/` o de `features/<f>/components/` muestra números —lo
 * detectamos por señales fuertes de renderizado numérico (props de formato
 * `"int"|"pct"|"ms"|"min"`, `tabular`, `toFixed`, `toLocaleString`,
 * `Intl.NumberFormat`, o un valor/conteo formateado)— ENTONCES el archivo debe
 * referenciar `tabular-nums` en algún lado. Si no lo hace, el test falla y
 * nombra el archivo.
 *
 * Escape hatch consciente: un archivo que legítimamente no renderiza dígitos
 * (p.ej. solo arma escalas/paths sin texto numérico, o un chart puramente
 * geométrico) puede marcar la línea `// tabular-nums-guard: n/a` con el motivo.
 * Es explícito y auditable, no un silencio.
 */

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Carpetas donde vive data-viz / métricas. `features/<f>/components` se expande
 *  por feature; `components/charts` es la batería de charts compartidos. */
const CHARTS_DIR = join(SRC_DIR, "components", "charts");
const FEATURES_DIR = join(SRC_DIR, "features");

/** Señales de que un archivo RENDERIZA un número en pantalla. Si matchea alguna,
 *  exigimos `tabular-nums`. Mezcla props de formato del blueprint + APIs de
 *  formateo numérico de JS + texto de dígitos en JSX. */
const RENDERS_NUMBER =
  /"(?:int|pct|ms|min)"|\.toFixed\(|\.toLocaleString\(|Intl\.NumberFormat|valueFormat|format=\{?["']|tabular/;

/** Marca de exención explícita para archivos que no pintan dígitos. */
const OPT_OUT = /tabular-nums-guard:\s*n\/a/;

/** La utility que el archivo debe contener si renderiza números. */
const HAS_TABULAR = /tabular-nums/;

function* walk(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(path);
    } else if (/\.tsx$/.test(entry.name) && !/\.(test|spec)\.tsx$/.test(entry.name)) {
      yield path;
    }
  }
}

/** Archivos de chart compartidos + cualquier `features/<f>/components/*.tsx`. */
function* candidateFiles(): Generator<string> {
  if (existsSync(CHARTS_DIR)) {
    yield* walk(CHARTS_DIR);
  }
  if (existsSync(FEATURES_DIR)) {
    for (const feature of readdirSync(FEATURES_DIR, { withFileTypes: true })) {
      if (!feature.isDirectory()) continue;
      const componentsDir = join(FEATURES_DIR, feature.name, "components");
      if (existsSync(componentsDir)) {
        yield* walk(componentsDir);
      }
    }
  }
}

describe("guard tabular-nums (blueprint §0)", () => {
  it("todo chart o componente de feature que muestra números usa tabular-nums", () => {
    const offenders: string[] = [];
    for (const file of candidateFiles()) {
      const source = readFileSync(file, "utf8");
      if (OPT_OUT.test(source)) continue;
      const rendersNumber = RENDERS_NUMBER.test(source);
      const hasTabular = HAS_TABULAR.test(source);
      if (rendersNumber && !hasTabular) {
        offenders.push(relative(SRC_DIR, file).split(sep).join("/"));
      }
    }
    expect(offenders).toEqual([]);
  });
});
