# Fondo vivo en mobile (Skia) — guía de integración

> Cómo recrear el `LivingField` de web **idéntico** en mobile (React Native/Expo), compartiendo el modelo desde `@ynara/core/features/field`.
> El fondo no se puede compartir como componente (web usa Canvas2D/DOM, que no existe en RN), pero **toda la lógica que lo define ya vive en core** (clima, config por variante, geometría, animación, specs de blooms/ondas). Mobile sólo escribe el renderer con Skia, consumiendo ese modelo. Misma matemática → mismo fondo.

---

## 1. Qué quedó compartido (ya en `main`)

`@ynara/core/features/field` exporta TODO lo que define el campo:

- **Clima:** `MODE_CLIMATE` (par de hex por modo), `hexToRgb`, `dotColor(dark)`.
- **Config:** `VARIANTS` (aurora/constellation/network/paper/depth), `DENSITY_FACTOR`, `MASKS`, `FIELD` (constantes), `nodeCount`, `diamondCount`, `LINK2`, `PR2`.
- **Modelo:** `seedField(w,h,factor,particles,rng?)`, `stepNodes`, `stepDiamonds`, `advanceTime`, `breath`, `nodeTwinkle`, `linkAlpha`, `repel`.
- **Specs de dibujo:** `buildBlooms(...) → BloomSpec[]`, `buildWaves(...) → {ribbons, threads}`, `ribbonEdgeY`, `threadY`, + `RIBBON_STEP`/`THREAD_STEP`.

Web (`apps/web/.../LivingField.tsx`) ya consume esto; es la referencia 1:1 de cómo mapear cada spec a llamadas de canvas.

## 2. Instalación (mobile)

```bash
# Reanimated ya está instalado. Sumar Skia (Expo 54 lo soporta):
npx expo install @shopify/react-native-skia
```
> Aprobar la dep con el equipo (regla #1). Skia es la vía canónica para canvas/GPU en Expo y es lo que permite que el fondo quede **idéntico** (su API de Canvas es casi 1:1 con Canvas2D).

## 3. Diferencias web → mobile (a tener en cuenta)

| Web (Canvas2D) | Mobile (Skia) |
|---|---|
| `requestAnimationFrame` | `useFrameCallback` (Reanimated) |
| `ctx.createRadialGradient` | `Skia.Shader.MakeRadialGradient` / `RadialGradient` |
| `ctx.createLinearGradient` | `Skia.Shader.MakeLinearGradient` / `LinearGradient` |
| `ctx.arc` / `fillRect` | `canvas.drawCircle` / `drawRect` |
| Cursor (halo + repulsión) | **No hay cursor** → pasar `pOn=false`, el campo queda en deriva (igual que web en touch) |
| `mask-image` CSS | `<Mask>` de Skia con un gradiente equivalente a `MASKS.top`/`.full` |
| grano CSS | imagen tileada (`<Image>` con `tileMode`) — opcional, se puede omitir al inicio |
| reduced-motion | `AccessibilityInfo.isReduceMotionEnabled()` → dibujar 1 frame y no animar |

## 4. Componente de referencia (`LivingFieldNative.tsx`)

> **Referencia** — ajustar a tu versión exacta de `@shopify/react-native-skia` (la API de `createPicture`/paints cambió entre majors). La clave es: sembrar una vez, avanzar el tiempo + estado con `useFrameCallback`, y redibujar la escena con el mismo orden que web (blooms → ondas → hilos → nodos → diamantes).

```tsx
import {
  Canvas, Picture, Skia, createPicture, type SkCanvas,
} from "@shopify/react-native-skia";
import { useMemo, useRef, useState } from "react";
import { useDerivedValue, useFrameCallback, useSharedValue } from "react-native-reanimated";
import {
  MODE_CLIMATE, VARIANTS, DENSITY_FACTOR, FIELD, LINK2, hexToRgb, dotColor,
  seedField, stepNodes, stepDiamonds, advanceTime, breath as fieldBreath,
  nodeTwinkle, linkAlpha, buildBlooms, buildWaves, ribbonEdgeY, threadY,
  RIBBON_STEP, THREAD_STEP, type LivingFieldVariant, type FieldGeometry,
} from "@ynara/core/features/field";
import type { Mode } from "@ynara/shared-schemas";

const FRAME = 1000 / 60;

export function LivingFieldNative({
  variant, modeId = "productividad", dark = true,
}: { variant: LivingFieldVariant; modeId?: Mode; dark?: boolean }) {
  const cfg = VARIANTS[variant];
  const [size, setSize] = useState({ w: 0, h: 0 });
  const climate = MODE_CLIMATE[modeId];

  // Semilla 1 sola vez por tamaño/densidad (igual que el guard de resize en web).
  const geom = useMemo<FieldGeometry>(
    () => seedField(size.w, size.h, DENSITY_FACTOR[cfg.density], cfg.particles),
    [size.w, size.h, cfg.density, cfg.particles],
  );

  // Reloj del campo en el UI thread.
  const t = useSharedValue(0);
  const last = useRef(0);
  useFrameCallback((info) => {
    "worklet";
    const dt = last.current === 0 ? 1 : Math.min(3, (info.timeSincePreviousFrame ?? FRAME) / FRAME);
    last.current = info.timestamp;
    // step* y advanceTime son funciones puras de core → seguras en worklet.
    t.value = advanceTime(t.value, dt);
    stepNodes(geom.nodes, dt, size.w, size.h);
    stepDiamonds(geom.diamonds, dt);
  }, true);

  const picture = useDerivedValue(() => {
    const { w, h } = size;
    if (w === 0 || h === 0) return null;
    const tv = t.value;
    const br = fieldBreath(tv);
    const [R, G, B] = hexToRgb(climate.a);
    const [DR, DG, DB] = dotColor(dark);

    return createPicture((canvas: SkCanvas) => {
      const paint = Skia.Paint();

      // 1) Blooms (gradientes radiales)
      for (const bl of buildBlooms(w, h, tv, dark, cfg.aura, climate)) {
        const sh = Skia.Shader.MakeRadialGradient(
          { x: bl.cx, y: bl.cy }, bl.r,
          [Skia.Color(`rgba(${bl.rgb[0]},${bl.rgb[1]},${bl.rgb[2]},${bl.alpha})`),
           Skia.Color(`rgba(${bl.rgb[0]},${bl.rgb[1]},${bl.rgb[2]},0)`)],
          [0, 1], 0 /* Clamp */,
        );
        paint.setShader(sh);
        canvas.drawRect({ x: 0, y: 0, width: w, height: h }, paint);
      }

      // 2) Ondas (sólo aurora) — usar buildWaves + ribbonEdgeY/threadY,
      //    armar Skia.Path.Make() con los mismos pasos que web, y un
      //    LinearGradient horizontal con los stops 0 / 0.3 / 1.
      if (cfg.waves) {
        const { ribbons, threads } = buildWaves(w, h, tv, br, dark, climate);
        // ... (mismo loop que LivingField.tsx de web: top edge + bottom edge)
      }

      // 3) Nodos + hilos (recalcular rx/ry = posición; sin cursor: rx=x, ry=y)
      if (cfg.particles) {
        // hilos: O(N²) — en mobile el área chica baja el count solo; si hace
        // falta, cap más bajo. linkAlpha(d2, cfg.link, br, 0).
        // nodos: drawCircle con dotColor + nodeTwinkle(n.ph).
        // diamantes: drawRect rotado 45°.
      }
    });
  }, [size.w, size.h, dark, modeId]);

  return (
    <Canvas
      style={{ position: "absolute", inset: 0, opacity: dark ? 0.52 : 0.5 }}
      onLayout={(e) => setSize({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}
    >
      <Picture picture={picture} />
    </Canvas>
  );
}
```

## 5. Máscara + grano

- **Máscara** (`MASKS.top` / `.full`): envolver el contenido en `<Mask mode="luminance">` con un `<Rect>` pintado por un gradiente (vertical para `top`, radial para `full`) que vaya de blanco (opaco) a transparente con las mismas paradas que el string CSS de `MASKS`. Es lo que desvanece el campo bajo el texto (§3.8) — **no omitir**, es clave para el contraste.
- **Grano**: una `<Image>` de ruido tileada con baja opacidad (`cfg.grain`). Opcional al principio; suma el "papel" pero no es crítico.

## 6. Cómo cablearlo en las pantallas

Hoy las screens usan `bg-bg-canvas` plano (ej. `HoyScreen`). Poner el fondo detrás del contenido, con la variante por pantalla (igual que web):

| Pantalla | variant |
|---|---|
| Hoy | `aurora` |
| Chat / onboarding / paywall | `constellation` |
| Memoria / Buscar | `network` |
| Agenda | `paper` |
| Tú | `depth` |

```tsx
<View style={{ flex: 1 }}>
  <LivingFieldNative variant="aurora" modeId={activeMode} dark={dark} />
  {/* contenido por encima */}
</View>
```

## 7. Performance (mobile)

- `nodeCount` ya escala por área → en una pantalla de teléfono caen menos nodos. Si los hilos (O(N²)) pesan, bajar el cap o `cfg.link`.
- Todo el loop corre en el **UI thread** (worklet de Reanimated) → no bloquea JS.
- Pausar cuando la app va a background (`AppState`) — equivalente al `visibilitychange` de web.
- `useMemo` de la geometría: re-sembrar SÓLO al cambiar tamaño/densidad, nunca por re-tinte de modo (igual que el guard de web).

---

> **Fuente única:** si algún día se ajusta una fórmula del campo, se cambia en `@ynara/core/features/field` y las dos plataformas la heredan. Web es la referencia viva del mapeo spec→dibujo.
