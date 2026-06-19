/**
 * Generadores **deterministas** para los fixtures del panel (blueprint §4.7).
 *
 * Por qué no `Math.random()`: los fixtures alimentan tanto el dev server (MSW)
 * como el test de contrato (`admin-schemas.test.ts`). Necesitamos que cada corre
 * produzca EXACTAMENTE los mismos números: así un snapshot no flakea, el heatmap
 * no "salta" entre refrescos y el test es reproducible. Todo se deriva de una
 * seed fija vía un PRNG chico (mulberry32), sin estado global.
 *
 * Todas las fechas son ISO 8601 UTC y se anclan a una FECHA BASE fija (no `new
 * Date()`), por la misma razón: determinismo total, sin depender del reloj.
 */

import type { HeatLevel } from "@/features/_shared/schemas";

/**
 * Fecha base fija de los fixtures (UTC). Coincide con `currentDate` del proyecto
 * para que los datos "se vean de hoy" sin introducir no-determinismo. Cambiarla
 * desplaza TODAS las series de forma coherente.
 */
export const FIXTURE_NOW = new Date("2026-06-19T12:00:00.000Z");

/**
 * mulberry32: PRNG determinista de 32 bits. Dada una seed entera devuelve un
 * generador `() => number` en [0, 1). Rápido, sin deps, suficientemente uniforme
 * para datos de demo. NO es criptográfico (no hace falta).
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Entero determinista en `[min, max]` (ambos inclusive) para una `seed` dada.
 * Stateless: la misma `(seed, min, max)` devuelve siempre lo mismo. Útil para
 * "pinchar" un valor puntual sin arrastrar un generador.
 */
export function rngInt(seed: number, min: number, max: number): number {
  const r = mulberry32(seed)();
  return Math.floor(r * (max - min + 1)) + min;
}

/**
 * Las últimas `n` fechas (ISO, solo día `YYYY-MM-DD`) terminando en `FIXTURE_NOW`
 * (inclusive), en orden cronológico ascendente. `daysBack(7)` → 7 fechas, la
 * última es hoy.
 */
export function daysBack(n: number, now: Date = FIXTURE_NOW): string[] {
  const out: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

/**
 * ISO completo (con hora) `k` minutos antes de `FIXTURE_NOW`. Para timestamps de
 * eventos (audit, episodics) que necesitan hora, no solo día.
 */
export function minutesBack(k: number, now: Date = FIXTURE_NOW): string {
  return new Date(now.getTime() - k * 60 * 1000).toISOString();
}

/**
 * Mapea un `count` a un nivel de intensidad 0–5 para el heatmap (escala azul
 * `--heat-0..5`). Cuantiles fijos pensados para sesiones/día de la demo
 * (0 → vacío; >0 sube por umbrales). Determinista por definición.
 */
export function heatLevel(count: number): HeatLevel {
  if (count <= 0) return 0;
  if (count < 5) return 1;
  if (count < 12) return 2;
  if (count < 22) return 3;
  if (count < 35) return 4;
  return 5;
}

/**
 * Elige el elemento `i` de un array **no vacío**, devolviendo `T` (no
 * `T | undefined`). Pensado para los picks deterministas de los fixtures
 * (`pick(ARR, Math.floor(rand() * ARR.length))`), donde el índice siempre cae en
 * `[0, length)` pero `noUncheckedIndexedAccess` no lo puede probar. Si el índice
 * cayera fuera de rango, falla ruidoso en vez de devolver `undefined` silencioso.
 */
export function pick<T>(arr: readonly T[], i: number): T {
  const value = arr[i];
  if (value === undefined) {
    throw new RangeError(`pick: índice ${i} fuera de rango (len ${arr.length})`);
  }
  return value;
}

/**
 * UUID v4 **determinista** derivado de una seed entera. Mismo `seed` → mismo
 * UUID. Cumple el formato `xxxxxxxx-xxxx-4xxx-Yxxx-xxxxxxxxxxxx` (versión 4,
 * variante 10) para pasar `z.string().uuid()`. NO es aleatorio: es estable, que
 * es justo lo que querés en un fixture.
 */
export function seededUuid(seed: number): string {
  const rand = mulberry32(seed);
  const hex: string[] = [];
  for (let i = 0; i < 16; i++) {
    hex.push(
      Math.floor(rand() * 256)
        .toString(16)
        .padStart(2, "0"),
    );
  }
  // Forzar versión 4 (nibble alto del byte 6) y variante 10xx (byte 8). `pick`
  // valida el in-bounds; `.slice(1)` extrae el nibble bajo como `string` (sin
  // index access, que bajo `noUncheckedIndexedAccess` daría `string | undefined`).
  const byte6 = pick(hex, 6);
  const byte8 = pick(hex, 8);
  hex[6] = `4${byte6.slice(1)}`;
  const variantNibble = ((parseInt(byte8.slice(0, 1), 16) & 0x3) | 0x8).toString(16);
  hex[8] = `${variantNibble}${byte8.slice(1)}`;
  const s = hex.join("");
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20, 32)}`;
}

/**
 * Construye una serie temporal con estacionalidad semanal (picos lun–vie, valle
 * fin de semana) de forma determinista. Devuelve `{ date, value }[]` para los
 * últimos `days` días. `base` es el piso aproximado del día laboral; `seed`
 * desacopla series distintas (sesiones vs signups) para que no queden idénticas.
 */
export function weeklySeasonalSeries(
  days: number,
  base: number,
  seed: number,
  now: Date = FIXTURE_NOW,
): { date: string; value: number }[] {
  const dates = daysBack(days, now);
  const rand = mulberry32(seed);
  return dates.map((date, i) => {
    const dow = new Date(`${date}T00:00:00.000Z`).getUTCDay(); // 0 dom … 6 sáb
    const weekendDip = dow === 0 || dow === 6 ? 0.45 : 1;
    const trend = 1 + (i / Math.max(1, days - 1)) * 0.25; // leve crecimiento
    const jitter = 0.8 + rand() * 0.4; // ±20%
    const value = Math.max(0, Math.round(base * weekendDip * trend * jitter));
    return { date, value };
  });
}
