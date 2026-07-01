"use client";

import { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  Clock,
  Color,
  DoubleSide,
  Mesh,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  ShaderMaterial,
  WebGLRenderer,
} from "three";
import { gsap, reducedMotion, registerGsap, ScrollTrigger } from "@/lib/motion";

/* ────────────────────────────────────────────────────────────────────────────
 * CAMPO CASCADA — la técnica completa de infinitefield, identidad Ynara.
 *
 *   FORMA:   UN plano 70×40 muy subdividido. El displacement por simplex se
 *            rampa a lo ancho (uv.y) y se desvanece en los extremos (x²) →
 *            cinta flotante con mucho vacío, no terreno.
 *   LUZ:     normales por diferencias finitas → el color sale de la ORIENTACIÓN
 *            de la superficie (satén azul), no de la altura. Blending aditivo.
 *   VIAJE:   la MALLA rota de piso (-π/2, vista edge-on = olas) a frente a
 *            cámara (0, vista cenital) mientras bucea (y-2, z-9).
 *   CASCADA: olas satinadas → plano azul → se disuelve en PUNTOS → TABLERO
 *            orgánico → limpia la grilla y vuelve a una onda tenue para el
 *            handoff a las cards del contenido.
 *   DRIVER:  UN timeline maestro GSAP (paused) scrubbeado por el progress
 *            global — no estados por sección.
 *
 * Modos:
 *   · Lab (/lab/field): sin props → canvas fijo z-120 opaco, progress sobre
 *     el scroll total. `window.__setFieldProgress(p)` para conducirlo a mano.
 *   · Sitio: `bare` (el wrapper lo pone Field.tsx) + `endSelector` → p llega
 *     a 1 cuando el top de ese elemento toca el top del viewport (la cascada
 *     termina exactamente donde arranca la sección horizontal).
 *
 * Implementación propia de las técnicas (noise displacement, shading por
 * normal, máscaras de celda); paleta y cierre son de Ynara.
 * ──────────────────────────────────────────────────────────────────────────── */

const SNOISE = /* glsl */ `
  vec3 mod289(vec3 x){ return x - floor(x * (1.0/289.0)) * 289.0; }
  vec2 mod289(vec2 x){ return x - floor(x * (1.0/289.0)) * 289.0; }
  vec3 permute(vec3 x){ return mod289(((x*34.0)+1.0)*x); }
  float snoise(vec2 v){
    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
    m = m*m; m = m*m;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
    vec3 g;
    g.x  = a0.x  * x0.x  + h.x  * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
  }
`;

const VERT = /* glsl */ `
  uniform float uTime;
  uniform float uWaveSlowed;
  uniform float uWavesDeform;
  uniform float uWaveColored;

  varying vec2  vUv;
  varying float vWaveNoise;
  varying vec3  vPos;
  varying vec3  vNormal;

  ${SNOISE}

  float displacement(vec3 p){
    float dz = snoise((0.09 - 0.03 * uWaveSlowed) * p.xy + vec2(-0.4, 0.04) * uTime);
    dz += 0.75 * snoise(-0.03 * p.xy + vec2(0.03, -0.04) * uTime);
    return 0.5 + 0.5 * dz;
  }

  // La firma de la cinta: rampa a lo ancho (un borde quieto, el otro ondula)
  // + taper x² (se funde en el vacío a los lados). b_w abre la rampa cuando
  // el satén se apaga (transición a plano).
  vec3 get_displacement_pos(vec3 p, float dz){
    float b_w = 1.0 - uWaveColored;
    float h = 4.0 * uWavesDeform * (dz - 0.5) * (1.0 + 2.0 * uv.y * b_w);
    h *= pow(uv.y + b_w, 1.0);
    h *= (0.8 - 0.005 * pow(p.x, 2.0) * uWaveSlowed);
    return vec3(p.xy, h);
  }

  vec3 get_displacement_normal(vec3 p, float dz){
    float e = 0.01;
    vec3 dpdx = get_displacement_pos(p + vec3(e, 0.0, 0.0), displacement(p + vec3(e, 0.0, 0.0))) - get_displacement_pos(p, dz);
    vec3 dpdy = get_displacement_pos(p + vec3(0.0, e, 0.0), displacement(p + vec3(0.0, e, 0.0))) - get_displacement_pos(p, dz);
    return normalize(cross(dpdx, dpdy));
  }

  void main(){
    vUv = uv;
    vPos = position;
    float dz = displacement(position);
    vec3 dp = get_displacement_pos(position, dz);
    vWaveNoise = dz;
    // Las normales (4 evaluaciones extra de noise por vértice) sólo se pagan
    // mientras el satén está visible; en plano/puntos/tablero no se usan.
    vNormal = vec3(0.0, 0.0, 1.0);
    if (uWaveColored > 0.001) {
      vNormal = get_displacement_normal(position, dz);
    }
    gl_Position = projectionMatrix * modelViewMatrix * vec4(dp, 1.0);
  }
`;

const FRAG = /* glsl */ `
  uniform float uTime;
  uniform float uGridScale;
  uniform float uWaveToPlane;
  uniform float uDotsMaskVisibility;
  uniform float uDotsRadiusGrow;
  uniform float uChecksNormalizeByNoise;
  uniform float uWaveColored;
  uniform float uWaveOpacity;
  uniform vec3  uFlat;
  uniform vec3  uViolet;
  uniform vec3  uIvory;

  varying float vWaveNoise;
  varying vec3  vPos;
  varying vec2  vUv;
  varying vec3  vNormal;

  ${SNOISE}

  float displacement(vec3 p){
    float dz = snoise(0.08 * p.xy + vec2(-0.4, 0.04) * uTime);
    dz += 0.75 * snoise(-0.03 * p.xy + vec2(0.03, -0.04) * uTime);
    return 0.5 + 0.5 * dz;
  }

  // Satén MUDO estilo Tiwis: azul-pizarra oscuro de base que sube apenas con
  // la pendiente (NO normalize → sin saturación plena que pelee con el texto).
  // La seda es una presencia oscura y suave, no un glow vibrante.
  vec3 get_wave_color(vec3 norm){
    float s = 0.5 + 0.5 * norm.x; // pendiente lateral conduce el tono
    return vec3(0.07, 0.10, 0.18) + vec3(0.09, 0.11, 0.17) * s;
  }

  float get_checks(vec2 p, float scale){
    return mod(floor(p.x * scale) + floor(p.y * scale), 2.0);
  }

  float circle(vec2 p, float r){
    vec2 d = p - vec2(0.5);
    return 1.0 - smoothstep(0.9 * r, 1.1 * r, dot(d, d) * 4.0);
  }

  void main(){
    float tile_scale = uGridScale;

    vec2 grid_uv = vPos.xy * tile_scale;
    vec2 tile_index = floor(grid_uv);
    vec2 tile_uv = fract(grid_uv);
    grid_uv = (tile_index + 0.5) / tile_scale;
    vec2 p = vPos.xy;

    // ── color: satén por normal → plano azul apagado por noise ──
    vec3 wave_color = get_wave_color(vNormal);
    // El plano va un punto más oscuro que el azul puro: el texto editorial
    // (manifesto/etimología) tiene que ganar siempre.
    vec3 flat_mix = mix(uFlat * 0.84, vec3(0.0), clamp(vWaveNoise, 0.0, 1.0));
    vec3 color = mix(wave_color, flat_mix, uWaveToPlane);

    // El violeta es el ACENTO DE SEÑAL de la identidad: los nodos (memoria)
    // viran hacia él cuando el plano se disuelve en puntos.
    color = mix(color, uViolet, uDotsMaskVisibility * 0.55);

    // ── disolución en puntos: círculo por celda × checkerboard ──
    // Radio CAPEADO (~0.45 máx): los nodos crecen pero se quedan REDONDOS y nunca
    // llenan la celda. Antes el coef 2.0 los llevaba a r≈2.1 → los círculos
    // llenaban el damero y se veían como CUADRADOS sólidos. Ahora: nodos siempre.
    float cells_mask = circle(tile_uv, 0.1 + 0.35 * pow(uDotsRadiusGrow, 2.0 + 2.0 * clamp(vWaveNoise, 0.0, 1.0)));
    float checks = get_checks(p, tile_scale);
    cells_mask *= checks;
    cells_mask = mix(1.0, cells_mask, pow(uDotsMaskVisibility, 3.0 - 2.0 * clamp(vWaveNoise, 0.0, 1.0)));

    // ── tablero orgánico: las celdas se normalizan por el MISMO noise ──
    // (el noise por-pixel sólo se paga cuando la fase de tablero está activa)
    float grid_noise = 0.0;
    if (uChecksNormalizeByNoise > 0.001) {
      grid_noise = displacement(vec3(grid_uv, 0.0));
      grid_noise = 1.0 - smoothstep(0.5 * uChecksNormalizeByNoise, 1.0 - 0.5 * uChecksNormalizeByNoise, grid_noise);
    }
    cells_mask *= mix(cells_mask, grid_noise, uChecksNormalizeByNoise);

    color = mix(color, uIvory, pow(uChecksNormalizeByNoise, 4.0));
    color = mix(vec3(0.0), color, cells_mask);

    // ── opacidad: bandas que viajan + cinta casi completa (corte suave en vUv.y) ──
    float stripe = fract(0.2 * uTime + 0.12 * vPos.y - 0.04 * sin(0.8 * vPos.x));
    stripe = smoothstep(0.0, 0.5, stripe) * (1.0 - smoothstep(0.5, 1.0, stripe));
    stripe += (1.0 + vWaveNoise) * (1.0 - uWaveColored);
    float stripe_addon = (1.0 + vWaveNoise) * pow(stripe, 50.0);
    stripe_addon += 0.3 * stripe;
    float opacity = 0.1 + uWaveColored * stripe_addon;
    // Aditivo MÁS suave (6.5 vs 12) y cap bajo (0.95) → seda oscura que no
    // estalla a blanco; el texto gana siempre.
    opacity = 6.5 * pow(opacity, 1.0 + uWaveColored);
    // La seda llena el alto: sólo se desvanece el borde inferior (antes cortaba a
    // media cinta en vUv.y ~0.3–0.5 y dejaba una banda oscura arriba).
    opacity *= smoothstep(0.02, 0.16, vUv.y);
    opacity = min(opacity, 0.95);
    opacity *= uWaveOpacity;

    gl_FragColor = vec4(color, opacity);
  }
`;

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

declare global {
  interface Window {
    __setFieldProgress?: (p: number) => void;
    __resetFieldProgress?: () => void;
  }
}

// Carbón índigo — el equivalente Ynara del #232323 de la referencia,
// armonizado con Noche #242C3F de la identidad.
const BG = 0x151823;

interface CascadeFieldProps {
  /** Sin wrapper fijo propio: el padre (Field global) provee posición y z. */
  bare?: boolean;
  /**
   * Selector del elemento donde la cascada COMPLETA (p=1 cuando su top toca
   * el top del viewport). Sin él (o si no existe), p = scroll de página total.
   */
  endSelector?: string;
}

export default function CascadeField({ bare = false, endSelector }: CascadeFieldProps = {}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    registerGsap();
    const reduced = reducedMotion();

    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({
        canvas,
        antialias: (window.devicePixelRatio || 1) < 1.5,
      });
    } catch {
      // WebGL no disponible / contexto perdido: el body ya tiene fondo
      // var(--c-void), así que la página queda oscura y legible. Degradamos
      // sin romper el render (sin esto, el throw tiraba todo el efecto).
      return;
    }
    renderer.setClearColor(BG, 1);

    const scene = new Scene();
    scene.background = new Color(BG);

    const camera = new PerspectiveCamera(45, 1, 0.01, 100);
    camera.position.set(0, 0, 5);

    const W = 70;
    const H = 40;
    // Mobile / hardware modesto: menos vértices y DPR más bajo — el shader de
    // vértice es lo caro. Al criterio de ancho le sumamos CPU/memoria para que
    // los equipos de baja potencia arranquen en la ruta liviana.
    const navInfo = navigator as Navigator & { deviceMemory?: number };
    const lowPower =
      (navInfo.hardwareConcurrency || 8) <= 4 || (navInfo.deviceMemory || 8) <= 4;
    const coarse = window.innerWidth < 768 || lowPower;
    const RES = coarse ? 4 : 6;
    const MAX_DPR = coarse ? 1.5 : 1.75;
    const geometry = new PlaneGeometry(W, H, W * RES, H * RES);

    const u = {
      uTime: { value: 0 },
      uWaveColored: { value: 1 },
      uWavesDeform: { value: 1 },
      uWaveSlowed: { value: 1 },
      uGridScale: { value: 9 },
      uWaveToPlane: { value: 0 },
      uDotsMaskVisibility: { value: 0 },
      uDotsRadiusGrow: { value: 0 },
      uChecksNormalizeByNoise: { value: 0 },
      uWaveOpacity: { value: 1 },
      uFlat: { value: new Color(0.184, 0.353, 0.651) }, // azul #2f5aa6
      uViolet: { value: new Color(0.506, 0.396, 0.639) }, // violeta #8165a3
      uIvory: { value: new Color(0.953, 0.941, 0.918) }, // marfil #f3f0ea
    };

    const material = new ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: u,
      transparent: true,
      blending: AdditiveBlending,
      depthWrite: false,
      depthTest: true,
      side: DoubleSide,
    });

    const mesh = new Mesh(geometry, material);
    mesh.rotation.x = -0.5 * Math.PI; // arranca como piso → olas edge-on
    scene.add(mesh);

    // El tiempo del noise se CONGELA durante la fase de grilla (la referencia
    // hace exactamente esto): delta *= (1 - noiseTimeIncr).
    const animParams = { noiseTimeIncr: 0 };

    /* ── TIMELINE MAESTRO — coreografía original re-paceada para que las
       fases caigan en los capítulos del sitio (héroe=olas+giro, manifesto=
       plano, memoria=puntos, handoff=tablero→vuelta sutil de onda→atenuado). ── */
    const tl = gsap.timeline({ paused: true });
    tl.to(u.uWaveSlowed, { duration: 0.7, value: 0, ease: "power1.in" }, 0)
      .to(mesh.rotation, { duration: 0.8, x: 0, ease: "power2.in" }, 0)
      .to(mesh.position, { duration: 0.5, y: -2, z: -9, ease: "power1.inOut" }, 0)
      .to(mesh.position, { duration: 0.2, y: 0, ease: "power1.inOut" }, 0.7)
      .to(u.uWaveColored, { duration: 0.8, value: 0 }, 0.65)
      .to(u.uWavesDeform, { duration: 0.45, value: 0 }, 0.85)
      .to(u.uWaveToPlane, { duration: 0.4, value: 1 }, 0.9)
      // plano → PUNTOS (Memoria = red de nodos). Entran antes y se sostienen más:
      // ya NO hay fase de "tablero de cuadrados" que los interrumpa. Sin tweens de
      // uChecksNormalizeByNoise / uGridScale / noiseTimeIncr → el noise sigue
      // fluyendo y los nodos respiran (vivos) durante todo su tramo.
      .to(u.uDotsMaskVisibility, { duration: 0.4, value: 1 }, 1.3)
      .to(u.uDotsRadiusGrow, { duration: 0.35, value: 1, ease: "none" }, 1.45)
      // Cierre: los nodos se disuelven y vuelve la seda tenue para ceder a las cards.
      .to(u.uDotsMaskVisibility, { duration: 0.26, value: 0, ease: "power1.inOut" }, 2.15)
      .to(u.uDotsRadiusGrow, { duration: 0.22, value: 0, ease: "power1.inOut" }, 2.18)
      .to(u.uWaveColored, { duration: 0.28, value: 0.32, ease: "power1.out" }, 2.15)
      .to(u.uWavesDeform, { duration: 0.28, value: 0.24, ease: "power1.out" }, 2.15)
      .to(u.uWaveToPlane, { duration: 0.28, value: 0.72, ease: "power1.out" }, 2.15)
      // Atenuación final: la onda baja la luz para cederla a las cards.
      .to(u.uWaveOpacity, { duration: 0.16, value: 0.38 }, 2.3);

    let manual: number | null = null;
    window.__setFieldProgress = (p) => {
      manual = clamp01(p);
    };
    window.__resetFieldProgress = () => {
      manual = null;
    };

    // ── anclas de scroll (medidas en layout estable: mount, resize,
    // ScrollTrigger.refresh — nunca por frame, porque el pin corre el rect):
    //   endY   = top de `endSelector` → fin de la cascada (progress=1).
    //   coverY = top de `[data-field-cover]` (el mundo claro ivory) → a partir
    //            de ahí el campo queda TAPADO y no hace falta renderizarlo.
    let endY = 0;
    let coverY = 0;
    const measureAnchors = () => {
      const scroll = window.__lenis ? window.__lenis.scroll : window.scrollY;
      if (endSelector) {
        const el = document.querySelector<HTMLElement>(endSelector);
        endY = el ? el.getBoundingClientRect().top + scroll : 0;
      }
      const cov = document.querySelector<HTMLElement>("[data-field-cover]");
      coverY = cov ? cov.getBoundingClientRect().top + scroll : 0;
    };
    ScrollTrigger.addEventListener("refresh", measureAnchors);
    const measureRaf = requestAnimationFrame(measureAnchors);

    const readProgress = () => {
      if (manual != null) return manual;
      if (reduced) return 0; // sin coreografía por scroll en reduced-motion
      const scroll = window.__lenis ? window.__lenis.scroll : window.scrollY;
      if (endY > 100) return clamp01(scroll / Math.max(1, endY));
      const l = window.__lenis;
      if (l && l.limit > 0) return clamp01(l.scroll / l.limit);
      const max = document.documentElement.scrollHeight - window.innerHeight;
      return max > 0 ? clamp01(window.scrollY / max) : 0;
    };

    const applyResize = () => {
      const w = canvas.clientWidth || window.innerWidth;
      const h = canvas.clientHeight || window.innerHeight;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_DPR));
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      measureAnchors();
      // En reduced-motion no hay RAF continuo → re-renderizá el frame estático.
      if (reduced) renderer.render(scene, camera);
    };

    // Resize con debounce (~150ms): evita una ráfaga de setSize/measureAnchors
    // durante el arrastre del borde. El mount llama applyResize() directo.
    let resizeTimer: ReturnType<typeof setTimeout> | undefined;
    const debouncedResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(applyResize, 150);
    };

    applyResize();

    // ── REDUCED-MOTION: frame estático ──────────────────────────────────────
    // Fijá el timeline a la fase de olas inicial (progress 0) con un uTime
    // "lindo" congelado, renderizá UNA vez y NO agendes RAF continuo. El campo
    // se ve (no negro) y el resize re-renderiza ese mismo frame (arriba).
    if (reduced) {
      tl.progress(0);
      u.uTime.value = 12; // momento representativo del oleaje satinado
      renderer.render(scene, camera);

      window.addEventListener("resize", debouncedResize);
      return () => {
        clearTimeout(resizeTimer);
        cancelAnimationFrame(measureRaf);
        window.removeEventListener("resize", debouncedResize);
        ScrollTrigger.removeEventListener("refresh", measureAnchors);
        window.__setFieldProgress = undefined;
        window.__resetFieldProgress = undefined;
        tl.kill();
        geometry.dispose();
        material.dispose();
        renderer.dispose();
      };
    }

    const clock = new Clock();
    let raf = 0;
    const render = () => {
      raf = requestAnimationFrame(render);
      // El reloj se consume SIEMPRE (para que el delta no salte al reanudar).
      let delta = Math.min(clock.getDelta(), 0.05);

      // Tapado por el mundo claro ivory → el RAF sigue (barato) pero NO se
      // renderiza WebGL ni se actualiza el timeline: ahorra GPU cuando no se ve.
      const scroll = window.__lenis ? window.__lenis.scroll : window.scrollY;
      if (coverY > 0 && scroll > coverY) return;

      delta *= 0.62; // las olas respiran lento — calma, no apuro
      delta *= 1 - animParams.noiseTimeIncr;
      u.uTime.value += delta;

      tl.progress(readProgress());

      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(render);

    // Tab oculta → no quemar GPU (y el reloj no salta al volver: delta clampeado).
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden) raf = requestAnimationFrame(render);
    };
    document.addEventListener("visibilitychange", onVisibility);

    window.addEventListener("resize", debouncedResize);
    return () => {
      cancelAnimationFrame(raf);
      cancelAnimationFrame(measureRaf);
      clearTimeout(resizeTimer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", debouncedResize);
      ScrollTrigger.removeEventListener("refresh", measureAnchors);
      window.__setFieldProgress = undefined;
      window.__resetFieldProgress = undefined;
      tl.kill();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, [endSelector]);

  if (bare) {
    return <canvas ref={ref} className="absolute inset-0 block h-full w-full" aria-hidden />;
  }

  return (
    <div className="fixed inset-0 z-120" style={{ background: "#14171f" }} aria-hidden>
      <canvas ref={ref} className="absolute inset-0 block h-full w-full" />
    </div>
  );
}
