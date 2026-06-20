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
import { useEffect, useMemo } from "react";
import { useWindowDimensions, View } from "react-native";
import { useDerivedValue, useFrameCallback, useSharedValue } from "react-native-reanimated";
import { useActiveMode } from "@/hooks/useActiveMode";
import { useFieldActive } from "@/hooks/useFieldActive";

type Variant = "network" | "aurora" | "constellation" | "paper" | "depth";

type Props = {
  variant: Variant;
};

const LINK2 = FIELD.LINK * FIELD.LINK;
/** Reloj del campo: paso de tiempo por frame de 60fps (= `advanceTime`). */
const T_STEP = 0.0045;
/** Escala del radio de los nodos para que se lean en mobile. */
const NODE_SCALE = 1.7;
// Ondas de marca (espejo de model.ts): nº de cintas/hilos, paso de muestreo en
// px, y TAU para la fase de las curvas.
const RIBBONS = 7;
const THREADS = 5;
const RIBBON_STEP = 12;
const THREAD_STEP = 10;
const TAU = 6.2832;

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
 * `MODE_CLIMATE`, constantes `FIELD`). Todas las variantes comparten este
 * worklet (params de `VARIANTS`): blooms siempre; partículas (nodos + hilos +
 * diamantes) si `particles` (network/constellation/paper); ondas (cintas +
 * hilos) si `waves` (aurora); `depth` queda solo-blooms (`seedField` devuelve 0
 * nodos si `particles` es false).
 *
 * La animación corre en el hilo de UI: `useFrameCallback` avanza el reloj `t` y
 * `useDerivedValue` redibuja el `SkPicture` por frame. Las fórmulas de evolución
 * (deriva, titileo, respiración, blooms, hilos) van inline en el worklet — son
 * espejo EXACTO de `model.ts`; no se importan porque las funciones de core no
 * están marcadas `"worklet"` y reanimated no puede llamarlas en el UI thread.
 */
export function LivingField({ variant }: Props) {
  const mode = useActiveMode();
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
  // Paleta de las ondas (`waveColors` de model.ts): clima a/b + 3 stops oficiales.
  // Solo varía con el modo (clima a/b); el worklet la lee.
  const waveCols = useMemo(
    () => [
      hexToRgb(climate.a),
      hexToRgb(climate.b),
      hexToRgb(MODE_CLIMATE.memoria.b),
      hexToRgb(MODE_CLIMATE.bienestar.a),
      hexToRgb(MODE_CLIMATE.productividad.b),
    ],
    [climate.a, climate.b],
  );

  // Paints reusados (HostObjects accesibles en el worklet).
  const fill = useMemo(() => Skia.Paint(), []);
  const stroke = useMemo(() => {
    const p = Skia.Paint();
    p.setStyle(PaintStyle.Stroke);
    p.setStrokeWidth(1.1);
    return p;
  }, []);
  const recorder = useMemo(() => Skia.PictureRecorder(), []);
  // Path reusable para las ondas: se `reset()`ea por cinta/hilo en vez de allocar
  // uno por frame (drawPath snapshotea la geometría en la grabación).
  const wavePath = useMemo(() => Skia.Path.Make(), []);

  const animate = useFieldActive();
  const t = useSharedValue(0);
  // El callback corre en el hilo de UI; se prende/apaga con setActive (el worklet
  // captura `animate` por copia, así que un closure no reaccionaría a los cambios
  // de reduce-motion / foco). Al frenar, el reloj deja de avanzar → frame estático.
  const frame = useFrameCallback((info) => {
    "worklet";
    const dt = Math.min(3, (info.timeSincePreviousFrame ?? 16.67) / 16.67);
    t.value += T_STEP * dt;
  }, false);
  useEffect(() => {
    frame.setActive(animate);
  }, [animate, frame]);

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

    // ── Ondas de marca: cintas + hilos (buildWaves inline, espejo de model.ts).
    // Solo en variantes con `waves` (aurora). Cada banda/hilo lleva un gradiente
    // horizontal izq→der (de transparente al alpha del extremo). ──
    if (cfg.waves) {
      for (let k = 0; k < RIBBONS; k++) {
        const cy = h * (0.1 + k * 0.075);
        const amp = h * (0.034 + k * 0.012);
        const thick = h * (0.075 + (k % 3) * 0.022);
        const wl = w * (0.9 + (k % 3) * 0.34);
        const ph = tv * (0.32 + k * 0.13);
        const rgb = waveCols[k % waveCols.length];
        const aEnd = 0.34 * (0.84 + 0.16 * Math.sin(tv * 0.4 + k * 0.9)) * (0.8 + 0.2 * br);
        wavePath.reset();
        for (let x = 0; x <= w; x += RIBBON_STEP) {
          const u = (x / wl) * TAU;
          const y =
            cy - thick / 2 + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph * 1.2) * amp * 0.32;
          if (x === 0) wavePath.moveTo(x, y);
          else wavePath.lineTo(x, y);
        }
        for (let x = w; x >= 0; x -= RIBBON_STEP) {
          const u = (x / wl) * TAU;
          const y =
            cy + thick / 2 + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph * 1.2) * amp * 0.32;
          wavePath.lineTo(x, y);
        }
        wavePath.close();
        fill.setShader(
          Skia.Shader.MakeLinearGradient(
            { x: 0, y: 0 },
            { x: w, y: 0 },
            [
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0)`),
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${aEnd * 0.55})`),
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${aEnd})`),
            ],
            [0, 0.3, 1],
            0,
          ),
        );
        canvas.drawPath(wavePath, fill);
      }
      fill.setShader(null);

      for (let k = 0; k < THREADS; k++) {
        const cy = h * (0.12 + k * 0.1);
        const amp = h * (0.045 + k * 0.014);
        const wl = w * (0.96 + (k % 2) * 0.28);
        const ph = tv * (0.28 + k * 0.12) + k * 1.1;
        const rgb = waveCols[(k + 1) % waveCols.length];
        const aEnd = 0.42 * (0.8 + 0.2 * br);
        wavePath.reset();
        for (let x = 0; x <= w; x += THREAD_STEP) {
          const u = (x / wl) * TAU;
          const y = cy + Math.sin(u + ph) * amp + Math.sin(u * 0.5 - ph) * amp * 0.3;
          if (x === 0) wavePath.moveTo(x, y);
          else wavePath.lineTo(x, y);
        }
        stroke.setShader(
          Skia.Shader.MakeLinearGradient(
            { x: 0, y: 0 },
            { x: w, y: 0 },
            [
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0)`),
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${aEnd})`),
              Skia.Color(`rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${aEnd * 0.85})`),
            ],
            [0, 0.5, 1],
            0,
          ),
        );
        canvas.drawPath(wavePath, stroke);
      }
      stroke.setShader(null);
    }

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
  }, [w, h, climA, climB, dotC, geom, cfg, waveCols]);

  return (
    <View
      pointerEvents="none"
      // Decorativo: invisible para lectores de pantalla (iOS + Android).
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <Canvas style={{ flex: 1, opacity: 0.55 }}>
        <Picture picture={picture} />
      </Canvas>
    </View>
  );
}
