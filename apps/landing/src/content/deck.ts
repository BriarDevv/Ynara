/**
 * Banco de copy del DECK institucional (/presentacion) — 30 láminas en 11
 * secciones. Mismo canon de voz que `ynara.ts` (voseo, editorial, sin
 * tics de chatbot, sin emojis). Reusa la copy canónica de la landing donde
 * aplica y agrega lo que la landing no tiene (marca, evento, promoción, roadmap).
 *
 * Cambios de §8 aplicados: "Gratuito" (no "Gratis"), 4 verbos LOCKED con
 * Aconseja = intersección, precio en USD y ARS, etimología honesta (sin
 * asterisco, sin "Sara").
 */

import { feel, problem, site } from "@/content/ynara";

/* ──────────────────────────────────────────────────────────────────────────
 * META — fuente ÚNICA del orden, el mundo (oscuro/marfil), el registro
 * (caos/calma/nodos → color del acento) y la fase del campo WebGL por lámina.
 *
 * `field` = progress 0..1 del timeline maestro de CascadeField
 * (window.__setFieldProgress). Mapa de fases:
 *   ~0.05 olas turbulentas (CAOS) · ~0.30 seda serena · ~0.45 plano azul (CALMA)
 *   ~0.60 nodos + violeta (campo de nodos) · ~0.90 seda tenue de cierre.
 * El Deck interpola entre láminas → avanzar de una lámina caos a una calma
 * ES la morfología turbulento→sereno (el motor caos↔calma del brief).
 * ────────────────────────────────────────────────────────────────────────── */

export type DeckWorld = "dark" | "ivory";
export type DeckRegister = "chaos" | "calma" | "nodes";

export interface DeckSlideMeta {
  id: number; // 1..30
  section: string; // sección institucional (§5), para aria/nav
  title: string; // etiqueta corta para el índice
  world: DeckWorld;
  register: DeckRegister;
  field: number; // fase del campo (0..1)
}

export const DECK_SLIDES: readonly DeckSlideMeta[] = [
  { id: 1, section: "Presentarnos", title: "Ynara", world: "dark", register: "calma", field: 0.12 },
  {
    id: 2,
    section: "Presentarnos",
    title: "Qué es Ynara",
    world: "dark",
    register: "calma",
    field: 0.3,
  },
  {
    id: 3,
    section: "El problema",
    title: "Ocho apps",
    world: "dark",
    register: "chaos",
    field: 0.05,
  },
  {
    id: 4,
    section: "Storytelling",
    title: "Un día",
    world: "dark",
    register: "chaos",
    field: 0.04,
  },
  {
    id: 5,
    section: "Storytelling",
    title: "Un día · imagen",
    world: "dark",
    register: "chaos",
    field: 0.05,
  },
  {
    id: 6,
    section: "Storytelling",
    title: "Un día · imagen",
    world: "dark",
    register: "chaos",
    field: 0.06,
  },
  {
    id: 7,
    section: "Desarrollo de la marca",
    title: "Calma en el caos",
    world: "dark",
    register: "nodes",
    field: 0.55,
  },
  {
    id: 8,
    section: "Desarrollo de la marca",
    title: "Nombre e isotipo",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  {
    id: 9,
    section: "Desarrollo de la marca",
    title: "Tipografía y color",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  {
    id: 10,
    section: "Landing page",
    title: "La página",
    world: "dark",
    register: "calma",
    field: 0.4,
  },
  {
    id: 11,
    section: "Funcionalidades principales",
    title: "Tres pilares",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  {
    id: 12,
    section: "Funcionalidades principales",
    title: "La app",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  {
    id: 13,
    section: "Monetización",
    title: "Planes",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  {
    id: 14,
    section: "Monetización",
    title: "Viabilidad",
    world: "ivory",
    register: "calma",
    field: 0.45,
  },
  // ── Lanzamiento (Nerdearla 2026): piezas físicas → stand → escenario → demo →
  //    equipo → folletería. Cada imagen en su propia lámina, grande y clara. ──
  {
    id: 15,
    section: "Lanzamiento",
    title: "Piezas",
    world: "dark",
    register: "calma",
    field: 0.24,
  },
  {
    id: 16,
    section: "Lanzamiento",
    title: "El stand",
    world: "dark",
    register: "calma",
    field: 0.26,
  },
  {
    id: 17,
    section: "Lanzamiento",
    title: "El escenario",
    world: "dark",
    register: "calma",
    field: 0.28,
  },
  {
    id: 18,
    section: "Lanzamiento",
    title: "La demo",
    world: "dark",
    register: "calma",
    field: 0.3,
  },
  {
    id: 19,
    section: "Lanzamiento",
    title: "El equipo",
    world: "dark",
    register: "calma",
    field: 0.28,
  },
  {
    id: 20,
    section: "Lanzamiento",
    title: "Folletería",
    world: "dark",
    register: "calma",
    field: 0.3,
  },
  // ── Promoción: cada lámina muestra MÁXIMO 3 imágenes grandes (Redes 2+2,
  //    Vía pública 2+2, Objetos 3+2+2). Las imágenes mandan; el rótulo dice qué es.
  { id: 21, section: "Promoción", title: "Redes", world: "dark", register: "chaos", field: 0.05 },
  { id: 22, section: "Promoción", title: "Redes", world: "dark", register: "chaos", field: 0.05 },
  {
    id: 23,
    section: "Promoción",
    title: "Vía pública",
    world: "dark",
    register: "chaos",
    field: 0.06,
  },
  {
    id: 24,
    section: "Promoción",
    title: "Vía pública",
    world: "dark",
    register: "chaos",
    field: 0.06,
  },
  {
    id: 25,
    section: "Promoción",
    title: "Objetos",
    world: "dark",
    register: "calma",
    field: 0.45,
  },
  {
    id: 26,
    section: "Promoción",
    title: "Objetos",
    world: "dark",
    register: "calma",
    field: 0.45,
  },
  {
    id: 27,
    section: "Promoción",
    title: "Objetos",
    world: "dark",
    register: "calma",
    field: 0.45,
  },
  {
    id: 28,
    section: "Próximas funcionalidades",
    title: "Roadmap",
    world: "dark",
    register: "calma",
    field: 0.45,
  },
  { id: 29, section: "Cierre", title: "Cierre", world: "dark", register: "calma", field: 0.32 },
  { id: 30, section: "Cierre", title: "Gracias", world: "dark", register: "calma", field: 0.9 },
] as const;

export const TOTAL_SLIDES = DECK_SLIDES.length;

/** Color del acento (diamante de eyebrow, marcadores) por registro. §7: caos→violeta, calma→azul. */
export const REGISTER_ACCENT: Record<DeckRegister, string> = {
  chaos: "var(--c-violet)",
  calma: "var(--c-blue-bright)",
  nodes: "var(--c-violet)",
};

/* ──────────────────────────────────────────────────────────────────────────
 * CONTENIDO POR LÁMINA
 * ────────────────────────────────────────────────────────────────────────── */

// L01 · Presentarnos
export const d01 = {
  wordmark: site.name,
  tagline: site.tagline, // "Tu asistente personal con memoria."
  authors: ["Facundo Álvarez", "Mateo García", "Mateo Sonzogni"],
} as const;

// L02 · Presentarnos — qué es Ynara (los tres pilares)
export const d02 = {
  eyebrow: "Qué es Ynara",
  lead: "Tu asistente personal con memoria: una sola app para tres cosas que hoy andan sueltas.",
  pillars: [
    { title: "Productividad", line: "Organiza tu día y cierra tareas." },
    { title: "Memoria", line: "Recuerda todo por vos." },
    { title: "Bienestar", line: "Cuida tu energía y tus pausas." },
  ],
  intersection: "Y cuando las tres se encuentran, te aconseja qué hacer.",
} as const;

// L03 · Storytelling — un día (humano)
export const d03 = {
  eyebrow: "Un día",
  statement: "¿Vivís solo, trabajás y estudiás?",
  support:
    "la entrega del martes, el turno con el médico, pagar la luz, responderle a tu familia, acordarte de comer. Lo cargás vos, en tu cabeza.",
} as const;

// Storytelling · Un día — DOS láminas de imagen (las fotos las pega el equipo).
// Mientras `img` esté vacío, la lámina muestra un placeholder pero queda armada.
export const dDia1 = {
  eyebrow: "Un día",
  caption: "La mañana arranca y ya hay diez cosas en la cabeza.",
  img: "/promo/un-dia-manana.png",
  alt: "De día, frente a una pared cubierta de notas con pendientes, abrumada.",
} as const;
export const dDia2 = {
  eyebrow: "Un día",
  caption: "Llega la noche y seguís corriendo atrás de todo.",
  img: "/promo/un-dia-noche.png",
  alt: "De noche, llegando a casa con las compras y el teléfono en la mano, todavía corriendo.",
} as const;

// L04 · El problema — el caos (8 apps → 1)
export const d04 = {
  eyebrow: "El problema",
  problemLine: problem.problemLine, // "Vivís entre ocho apps."
  answerLine: problem.answerLine, // "Ynara es una."
  apps: problem.apps, // las ocho apps dispersas
  beats: ["Un audio a las 2:47.", "47 pestañas abiertas.", "El pegamento sos vos."],
} as const;

// L05 · Desarrollo de la marca — calma en el caos (díptico de DOS FOTOS)
export const d05 = {
  eyebrow: "La identidad",
  statement: "Calma en el caos.",
  support: "Tu día es la misma información, enredada. Ynara la pone en orden.",
  // Díptico caos→calma con dos fotos (las pega el equipo). Mientras `img` esté
  // vacío, cada panel muestra un placeholder rotulado y la lámina queda armada.
  chaos: {
    tag: "Tu día",
    img: "/promo/caos-escritorio.png",
    alt: "Un escritorio desbordado de notas y papeles — el día, enredado.",
  },
  calm: {
    tag: "Con Ynara",
    img: "/promo/calma-escritorio.png",
    alt: "El mismo escritorio en orden y la persona en calma — el día, resuelto.",
  },
} as const;

// L06a · Desarrollo de marca — NOMBRE E ISOTIPO (lockup + etimología + significado).
export const d06a = {
  eyebrow: "Nombre e isotipo",
  wordmark: site.name,
  etymology: "De una raíz celta: uno, único. La única presencia que necesitás.",
  notes: [
    { k: "La figura", v: "Una Y que es un brote abriéndose. Memoria que crece." },
    { k: "El diamante", v: "La presencia: Ynara, ahí, atenta." },
  ],
} as const;

// L06b · Desarrollo de marca — TIPOGRAFÍA Y COLOR (el sistema visual, claro).
export const d06b = {
  eyebrow: "Tipografía y color",
  palette: [
    { name: "Azul", role: "Marca", token: "var(--c-blue)", hex: "#2F5AA6" },
    { name: "Violeta", role: "Señal", token: "var(--c-violet)", hex: "#8165A3" },
    { name: "Marfil", role: "Luz", token: "var(--c-ivory)", hex: "#F3F0EA" },
    { name: "Noche", role: "Fondo", token: "var(--c-navy)", hex: "#242C3F" },
  ],
  typefaces: [
    { name: "Space Grotesk", role: "Display", varName: "var(--font-display)" },
    { name: "DM Sans", role: "Texto", varName: "var(--font-body)" },
  ],
} as const;

// L07 · Landing — capturas reales de la landing (del deck TP3).
export const d07 = {
  eyebrow: "La página",
  statement: "Que entre con dudas y salga con ganas.",
  support:
    "Lo primero que ve alguien interesado no es la app: es la landing. La primera impresión de la marca, antes de descargar nada.",
  shots: [
    { img: "/promo/tp3-12.png", alt: "Landing de Ynara — inicio" },
    { img: "/promo/tp3-22.png", alt: "Landing de Ynara — precio" },
    { img: "/promo/tp3-23.png", alt: "Landing de Ynara — cierre y CTA" },
  ],
} as const;

// L08 · Funcionalidades — los 3 pilares
export const d08 = {
  eyebrow: "Funcionalidades principales",
  intro: "Tres cosas que ninguna app junta.",
  // 3 pilares adelante (Productividad / Memoria / Bienestar). Los 5 modos son el
  // mecanismo; acá van los pilares. Aconseja = la intersección.
  pillars: problem.layers.slice(0, 3).map((l) => ({
    title: l.title,
    note: l.note,
    features: l.features,
  })),
  intersection: "Y cuando las tres se encuentran, te aconseja qué hacer.",
} as const;

// L09 · Funcionalidades — la app. Los 4 verbos funcionando: los 3 chats canónicos
// (Productividad/Memoria/Bienestar) + un 4to que ilustra Aconseja (la intersección).
export const d09 = {
  eyebrow: "La app",
  statement: "Le hablás como a una persona y resuelve.",
  chats: [
    ...feel.chats,
    {
      mode: "Aconseja",
      user: "tengo tres entregas y cero energía",
      ynara: "Arrancá por la del martes, es la más corta. El resto puede esperar a mañana.",
    },
  ],
  placeholder: "UI real de la app",
} as const;

// L10 · Monetización — planes
export const d10 = {
  eyebrow: "Monetización",
  title: "Empezás gratuito. Subís cuando quieras.",
  plans: [
    {
      name: "Gratuito",
      price: "$0",
      period: "para siempre",
      features: ["Los tres pilares", "Memoria reciente", "Un dispositivo"],
      featured: false,
    },
    {
      name: "Premium",
      price: "USD 4–6",
      priceAlt: "≈ $6.900 ARS · por Mercado Pago",
      period: "por mes",
      features: [
        "Memoria extendida",
        "Funciones avanzadas",
        "Multidispositivo",
        "Prioridad de respuesta",
      ],
      featured: true,
    },
  ],
  note: "Sin publicidad. Sin venta de datos. Nunca.",
} as const;

// L11 · Monetización — viabilidad
export const d11 = {
  eyebrow: "Viabilidad",
  statement: "Un negocio que funciona.",
  ledger: [
    { num: "$0", title: "Inversión inicial", body: "Cero capital para arrancar." },
    { num: "US$70", title: "Costo mensual", body: "Lo que cuesta sostener la infraestructura." },
    { num: "~15", title: "Break-even", body: "Rentable desde el suscriptor quince." },
  ],
} as const;

// ── Lanzamiento · Nerdearla 2026 — cada pieza en su propia lámina de imagen
//    (DeckGallery), grande y clara. Orden de oratoria: piezas → stand → escenario
//    → demo → equipo → folletería. Las imágenes mandan; el rótulo dice "qué es". ──

// Piezas físicas que ABREN la oratoria: señalética · afiche en Konex · roll-up.
export const dLanzPiezas = {
  eyebrow: "Nerdearla 2026",
  pieces: [
    { img: "/promo/tp3-08.jpg", label: "Señalética", alt: "Señalética de Ynara en Nerdearla" },
    {
      img: "/promo/tp3-07.jpg",
      label: "Afiche en Konex",
      alt: "Afiche de Ynara en una columna del Konex",
    },
    { img: "/promo/tp3-09.jpg", label: "Roll-up", alt: "Roll-up de Ynara en Nerdearla" },
  ],
} as const;

// El stand — una sola imagen grande.
export const dLanzStand = {
  eyebrow: "El stand",
  pieces: [{ img: "/promo/tp3-03.jpg", alt: "El stand de Ynara en Nerdearla 2026" }],
  caption: "El stand de Ynara, donde la gente se acercó a probarla.",
} as const;

// El escenario — imagen real del escenario principal, grande y al frente (antes
// era un fondo fantasma a opacidad 0.13 y sólo se veía el título).
export const dLanzEscenario = {
  eyebrow: "El escenario",
  pieces: [{ img: "/promo/tp3-02.jpg", alt: "Ynara en el escenario principal de Nerdearla 2026" }],
  caption: "Escenario principal de Nerdearla · charla en formato TED.",
} as const;

// El equipo acreditado — las tres credenciales del equipo fundador.
export const dLanzEquipo = {
  eyebrow: "El equipo, acreditado",
  pieces: [
    { img: "/promo/tp3-04.png", label: "Facundo Álvarez", alt: "Credencial de Facundo Álvarez" },
    { img: "/promo/tp3-05.png", label: "Mateo García", alt: "Credencial de Mateo García" },
    { img: "/promo/tp3-06.png", label: "Mateo Sonzogni", alt: "Credencial de Mateo Sonzogni" },
  ],
} as const;

// La folletería — folleto + flyers, lado a lado. Cierra el recap del evento.
export const dLanzFolleteria = {
  eyebrow: "Folletería",
  pieces: [
    { img: "/promo/tp3-10.jpg", label: "Folleto", alt: "Folleto tríptico de Ynara" },
    { img: "/promo/tp3-11.jpg", label: "Flyers", alt: "Flyers de Ynara" },
  ],
} as const;

// L13 · Lanzamiento — la demo (actuada)
export const d13 = {
  eyebrow: "La demo",
  statement: "Ynara, en treinta segundos.",
  chats: feel.chats.slice(0, 2),
  fallback: "Plan B: captura fija si no responde en 5 s",
} as const;

// Promoción · Redes — publicaciones reales de Instagram (TP2), en DOS láminas de
// 2 imágenes grandes. La cuenta no publicita la solución: documenta el problema.
export const d14 = {
  eyebrow: "Promoción · Redes",
  caption: "@ynara.app — no publicita la solución, documenta el problema.",
  a: [
    { img: "/promo/tp2-08.jpg", alt: "Publicación de Instagram de Ynara — «Menos apps»" },
    { img: "/promo/tp2-09.jpg", alt: "Publicación de Instagram de Ynara — «Tu agenda en contexto»" },
  ],
  b: [
    { img: "/promo/tp2-10.jpg", alt: "Publicación de Instagram de Ynara — «Recordá mejor»" },
    { img: "/promo/tp2-11.jpg", alt: "Publicación de Instagram de Ynara — «Dos meses gratis»" },
  ],
} as const;

// Promoción · Vía pública — renders reales de OOH (TP2), en DOS láminas de 2
// imágenes grandes rotuladas. Mismo gesto: te muestran tu propio caos en la calle.
export const d15 = {
  eyebrow: "Promoción · Vía pública",
  caption: "Tu propio caos, en la calle.",
  a: [
    { img: "/promo/tp2-12.jpg", label: "Cartel de autopista", alt: "Cartel de Ynara en una autopista" },
    { img: "/promo/tp2-13.jpg", label: "Andén de subte", alt: "Gráfica de Ynara en un andén de subte" },
  ],
  b: [
    {
      img: "/promo/tp2-14.jpg",
      label: "Parada de colectivo",
      alt: "Gráfica de Ynara en una parada de colectivo",
    },
    { img: "/promo/tp2-15.jpg", label: "Tótem digital", alt: "Tótem digital de Ynara en interior" },
  ],
} as const;

// Promoción · Objetos — renders reales de producto (TP2), en TRES láminas de
// hasta 3 imágenes grandes rotuladas (3 + 2 + 2). La marca hecha objeto.
export const d16 = {
  eyebrow: "Promoción · Objetos",
  caption: "La marca que se toca.",
  a: [
    { img: "/promo/tp2-01.jpg", label: "Funda negra", alt: "Funda de teléfono negra de Ynara" },
    { img: "/promo/tp2-02.jpg", label: "Funda marfil", alt: "Funda de teléfono marfil de Ynara" },
    { img: "/promo/tp2-03.jpg", label: "Soporte-cargador", alt: "Soporte-cargador MagSafe de Ynara" },
  ],
  b: [
    {
      img: "/promo/tp2-04.jpg",
      label: "Lapicera que graba reuniones",
      alt: "Lapicera que graba reuniones, de Ynara",
    },
    { img: "/promo/tp2-05.jpg", label: "Remera", alt: "Remera azul de Ynara" },
  ],
  c: [
    { img: "/promo/tp2-06.jpg", label: "Buzo", alt: "Buzo azul de Ynara" },
    { img: "/promo/tp2-07.jpg", label: "Tote", alt: "Tote crudo de Ynara" },
  ],
} as const;

// L17 · Próximas funcionalidades — LISTA SIMPLE DE PROMESAS (mock editable).
// El equipo carga las suyas: cada item es { title, body }. Sumá o quitá items de
// `promises` y la lámina se rearma sola. Copy claro y concreto, sin jerga.
export const d17 = {
  eyebrow: "Próximas funcionalidades",
  statement: "Subirte ahora es entrar antes que nadie.",
  promises: [
    { title: "Voz propia", body: "Le hablás y te responde con una voz natural, no robótica." },
    {
      title: "Multidispositivo",
      body: "La misma memoria, sincronizada en el teléfono y la computadora.",
    },
    {
      title: "Integraciones",
      body: "Conectás tu calendario, tu mail y tus notas en un solo lugar.",
    },
    // ← agregá acá las próximas promesas: { title: "…", body: "…" }
  ],
} as const;

// L18 · Cierre
export const d18 = {
  eyebrow: "Acceso anticipado · 2026",
  synthesis: "No tenés que acordarte de todo. Para eso está Ynara.",
  signoff: site.signoff, // "Pensar mejor, recordar siempre."
  cta: { label: "Quiero sumarme", href: "/#descargar" },
} as const;

// L19 · Gracias — cierre humano. Mundo oscuro. Logo grande + nombres del equipo.
export const dGracias = {
  word: "Gracias",
  wordmark: site.name,
  authors: ["Facundo Álvarez", "Mateo García", "Mateo Sonzogni"],
} as const;
