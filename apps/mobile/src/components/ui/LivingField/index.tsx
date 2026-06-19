import { Canvas, PaintStyle, Picture, Skia, type SkPicture } from "@shopify/react-native-skia";
import {
  DENSITY_FACTOR,
  dotColor,
  FIELD,
  hexToRgb,
  MODE_CLIMATE,
  seedField,
  VARIANTS,
} from "@ynara/core/features/field";
import type { Mode } from "@ynara/shared-schemas";
import { useMemo } from "react";
import { useWindowDimensions, View } from "react-native";
import { useDerivedValue, useFrameCallback, useSharedValue } from "react-native-reanimated";
import { useActiveMode } from "@/hooks/useActiveMode";

type Variant = "network" | "aurora" | "constellation" | "paper" | "depth";

type Props = {
  variant: Variant;
  /** Modo que tiñe el clima; default = modo activo global. */
  modeId?: Mode;
};

const LINK2 = FIELD.LINK * FIELD.LINK;
/** Reloj del campo: paso de tiempo por frame de 60fps (= `advanceTime`). */
const T_STEP = 0.0045;
/** Escala del radio de los nodos para que se lean en mobile. */
const NODE_SCALE = 1.7;

/** RNG determinístico (mulberry32): mismo seed → mismo campo, no re-randomiza. */
function mulberry32(seed: number): () => number {
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
 * Fondo vivo (F3) con **Skia**, consumiendo el modelo compartido
 * `@ynara/core/features/field` (geometría `seedField`, config `VARIANTS`, clima
 * `MODE_CLIMATE`, constantes `FIELD`). En F3 solo la variante `network`
 * (Memoria) está implementada; el resto devuelve null hasta extender.
 *
 * La animación corre en el hilo de UI: `useFrameCallback` avanza el reloj `t` y
 * `useDelivedValue` redibuja el `SkPicture` por frame. Las fórmulas de evolución
 * (deriva, titileo, respiración, blooms, hilos) van inline en el worklet — son
 * espejo EXACTO de `model.ts`; no se importan porque las funciones de core no
 * están marcadas `"worklet"` y reanimated no puede llamarlas en el UI thread.
 */
export function LivingField({ variant, modeId }: Props) {
  const activeMode = useActiveMode();
  const mode = modeId ?? activeMode;
  const { width: w, height: h } = useWindowDimensions();
  const cfg = VARIANTS[variant];
  const climate = MODE_CLIMATE[mode];

  // Geometría determinística (seed fijo): se siembra una vez por tamaño, no se
  // re-randomiza al cambiar de modo (solo cambian los colores).
  const geom = useMemo(
    () => seedField(w, h, DENSITY_FACTOR[cfg.density], cfg.particles, mulberry32(7)),
    [w, h, cfg.density, cfg.particles],
  );

  // Colores precalculados en JS (hexToRgb no es worklet); el worklet los lee.
  const climA = useMemo(() => hexToRgb(climate.a), [climate.a]);
  const climB = useMemo(() => hexToRgb(climate.b), [climate.b]);
  const dotC = useMemo(() => dotColor(true), []);

  // Paints reusados (HostObjects accesibles en el worklet).
  const fill = useMemo(() => Skia.Paint(), []);
  const stroke = useMemo(() => {
    const p = Skia.Paint();
    p.setStyle(PaintStyle.Stroke);
    p.setStrokeWidth(1.1);
    return p;
  }, []);
  const recorder = useMemo(() => Skia.PictureRecorder(), []);

  const t = useSharedValue(0);
  useFrameCallback((info) => {
    "worklet";
    const dt = Math.min(3, (info.timeSincePreviousFrame ?? 16.67) / 16.67);
    t.value += T_STEP * dt;
  }, true);

  const picture = useDerivedValue<SkPicture>(() => {
    "worklet";
    const tv = t.value;
    const F = tv / T_STEP; // frames acumulados (deriva/fase, espejo de step*)
    const br = 0.62 + 0.38 * Math.sin(tv * 1.3); // breath(t)

    const canvas = recorder.beginRecording(Skia.XYWHRect(0, 0, w, h));

    // ── Blooms (buildBlooms inline) ──
    const dxB = Math.sin(tv * 0.3) * w * 0.03;
    const dyB = Math.cos(tv * 0.26) * h * 0.03;
    const rad = Math.max(w, h);
    const blooms = [
      { cx: w * 0.26 + dxB, cy: h * 0.02 + dyB, r: rad * 0.62, rgb: climA, a: 0.4 * cfg.aura },
      { cx: w * 0.82 - dxB, cy: -h * 0.02 + dyB, r: rad * 0.55, rgb: climB, a: 0.32 * cfg.aura },
    ];
    for (const bl of blooms) {
      const sh = Skia.Shader.MakeRadialGradient(
        { x: bl.cx, y: bl.cy },
        bl.r,
        [
          Skia.Color(`rgba(${bl.rgb[0]}, ${bl.rgb[1]}, ${bl.rgb[2]}, ${bl.a})`),
          Skia.Color(`rgba(${bl.rgb[0]}, ${bl.rgb[1]}, ${bl.rgb[2]}, 0)`),
        ],
        [0, 1],
        0, // TileMode.Clamp
      );
      fill.setShader(sh);
      canvas.drawRect(Skia.XYWHRect(0, 0, w, h), fill);
    }
    fill.setShader(null);

    // ── Posiciones animadas de los nodos (stepNodes inline: deriva + wrap) ──
    const W = w + 20;
    const H = h + 20;
    const px: number[] = [];
    const py: number[] = [];
    const pa: number[] = [];
    for (const n of geom.nodes) {
      let x = n.x + n.vx * F;
      let y = n.y + n.vy * F;
      x = ((((x + 10) % W) + W) % W) - 10;
      y = ((((y + 10) % H) + H) % H) - 10;
      const ph = n.ph + 0.01 * n.tw * F;
      const tw = 0.55 + 0.45 * Math.sin(ph); // nodeTwinkle(ph)
      px.push(x);
      py.push(y);
      pa.push(tw * br);
    }

    // ── Hilos entre nodos cercanos (linkAlpha inline) ──
    for (let i = 0; i < px.length; i++) {
      for (let j = i + 1; j < px.length; j++) {
        const dx = px[i] - px[j];
        const dy = py[i] - py[j];
        const d2 = dx * dx + dy * dy;
        if (d2 < LINK2) {
          const a = (1 - d2 / LINK2) * 0.2 * cfg.link * br;
          stroke.setColor(Skia.Color(`rgba(${dotC[0]}, ${dotC[1]}, ${dotC[2]}, ${a})`));
          canvas.drawLine(px[i], py[i], px[j], py[j], stroke);
        }
      }
    }

    // ── Nodos ──
    for (let i = 0; i < px.length; i++) {
      const a = Math.min(1, pa[i]);
      fill.setColor(Skia.Color(`rgba(${dotC[0]}, ${dotC[1]}, ${dotC[2]}, ${a})`));
      canvas.drawCircle(px[i], py[i], geom.nodes[i].r * NODE_SCALE, fill);
    }

    // ── Diamantes (stepDiamonds inline: fase) ──
    for (const d of geom.diamonds) {
      const dph = d.ph + 0.006 * F;
      const a = (0.35 + 0.4 * Math.abs(Math.sin(dph))) * br;
      fill.setColor(Skia.Color(`rgba(${climB[0]}, ${climB[1]}, ${climB[2]}, ${a})`));
      canvas.save();
      canvas.translate(d.x, d.y);
      canvas.rotate(45, 0, 0);
      canvas.drawRect(Skia.XYWHRect(-d.s / 2, -d.s / 2, d.s, d.s), fill);
      canvas.restore();
    }

    return recorder.finishRecordingAsPicture();
  }, [w, h, climA, climB, dotC, geom, cfg]);

  if (variant !== "network") return null;

  return (
    <View
      pointerEvents="none"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <Canvas style={{ flex: 1, opacity: 0.55 }}>
        <Picture picture={picture} />
      </Canvas>
    </View>
  );
}
