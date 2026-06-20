import { describe, expect, it } from "vitest";

import {
  createStart,
  dragStart,
  minutesToPx,
  pxToMinutes,
  resizeDuration,
  snapMinutes,
} from "./interaction";

describe("pxToMinutes / minutesToPx", () => {
  it("convierten px↔minutos según rowPx (px por hora)", () => {
    expect(pxToMinutes(52, 52)).toBe(60); // 1 fila = 1 hora
    expect(pxToMinutes(26, 52)).toBe(30);
    expect(minutesToPx(60, 52)).toBe(52);
    expect(minutesToPx(30, 52)).toBe(26);
  });

  it("son inversos", () => {
    expect(minutesToPx(pxToMinutes(80, 44), 44)).toBeCloseTo(80, 5);
  });
});

describe("snapMinutes", () => {
  it("redondea al múltiplo de step (15 por defecto)", () => {
    expect(snapMinutes(7)).toBe(0);
    expect(snapMinutes(8)).toBe(15);
    expect(snapMinutes(22)).toBe(15);
    expect(snapMinutes(23)).toBe(30);
    expect(snapMinutes(100, 30)).toBe(90);
  });
});

describe("dragStart (mover)", () => {
  it("mueve el inicio por el delta, snappeado a 15", () => {
    // start 540 (09:00), delta +52px con rowPx 52 = +60min → 600 (10:00).
    expect(dragStart(540, 52, 52, 60)).toBe(600);
  });

  it("snappea un delta no exacto", () => {
    // +26px = +30min → 570; +10px ≈ +11.5min → snap 15 → 555.
    expect(dragStart(540, 26, 52, 60)).toBe(570);
    expect(dragStart(540, 10, 52, 60)).toBe(555);
  });

  it("clampea arriba en 0", () => {
    expect(dragStart(30, -200, 52, 60)).toBe(0);
  });

  it("clampea abajo para que el bloque no se salga del día", () => {
    // dur 60 → el inicio no puede pasar de 1380 (23:00).
    expect(dragStart(1380, 200, 52, 60)).toBe(1380);
  });
});

describe("resizeDuration (redimensionar)", () => {
  it("crece la duración por el delta, snappeada", () => {
    // dur 60 + 52px(=60min) = 120.
    expect(resizeDuration(60, 52, 52, 540)).toBe(120);
  });

  it("respeta el mínimo de un step", () => {
    expect(resizeDuration(30, -200, 52, 540)).toBe(15);
  });

  it("no excede el fin del día", () => {
    // start 1380 (23:00) → máx 60min hasta medianoche.
    expect(resizeDuration(60, 500, 52, 1380)).toBe(60);
  });
});

describe("createStart (crear arrastrando)", () => {
  it("traduce una Y desde el tope de la grilla a minutos del día (con minH)", () => {
    // minH 8 (08:00 = 480min), y=52px con rowPx 52 = +60min → 540 (09:00).
    expect(createStart(52, 8, 52)).toBe(540);
  });

  it("snappea a 15", () => {
    // minH 8 → 480; y=10px ≈ +11.5min → 491.5 → snap → 495 (08:15).
    expect(createStart(10, 8, 52)).toBe(495);
  });
});
