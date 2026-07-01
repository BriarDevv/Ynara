/**
 * Banco de copy de Ynara — fuente única de texto para todas las secciones.
 * Voz: voseo, directa, sin tics de chatbot, sin emojis, editorial.
 * Basado en Brief, Elección del Nombre, Business Model Canvas y TONE-OF-VOICE.
 */

export const site = {
  name: "Ynara",
  domain: "ynara.app",
  tagline: "Tu asistente personal con memoria.",
  signoff: "Pensar mejor, recordar siempre.",
  description:
    "Ynara es tu asistente personal con memoria: una sola app que organiza tu vida, recuerda todo y te acompaña. Privada y on-prem.",
  verbs: ["Organiza", "Recuerda", "Acompaña"],
} as const;

export const nav = {
  links: [
    { label: "Qué hace", href: "#producto" },
    { label: "Demo", href: "#voz" },
    { label: "Privacidad", href: "#privacidad" },
    { label: "Precio", href: "#precio" },
  ],
  cta: { label: "Quiero sumarme", href: "#descargar" },
} as const;

export const hero = {
  eyebrow: "Asistente personal con memoria",
  wordmark: "Ynara",
  // El valor en una línea: QUÉ es y QUÉ hace. El acento va en la palabra clave.
  value: "Una sola app para *organizar* tu vida, *recordar* todo y *acompañarte* cada día.",
  sub: "Hoy saltás entre agenda, notas, recordatorios y una IA suelta. Ynara junta todo eso en una — y aprende cómo sos.",
  badge: "Acceso anticipado · iOS y Android · 2026",
  ctaPrimary: { label: "Quiero sumarme", href: "#descargar" },
  ctaSecondary: { label: "Ver cómo funciona", href: "#producto" },
} as const;

export const problem = {
  eyebrow: "El problema",
  // Statement grande del beat "problema" (una idea por pantalla, legible).
  statement: "Vivís entre ocho apps. Ynara es una.",
  problemLine: "Vivís entre ocho apps.",
  answerLine: "Ynara es una.",
  support:
    "Agenda, notas, recordatorios, una IA para preguntar, una app de bienestar. Ninguna se habla con la otra — el pegamento sos vos.",
  // Las "ocho apps" dispersas (el caos que Ynara reemplaza).
  apps: [
    "Agenda",
    "Notas",
    "Recordatorios",
    "Una IA suelta",
    "Bienestar",
    "Tareas",
    "Calendario",
    "Notas de voz",
  ],
  // Intro de la sección horizontal (lleva a las cards).
  pillarsEyebrow: "Lo que hace por vos",
  pillarsIntro: "Una sola app. Tres pilares que ninguna otra junta — y un cuarto que nace donde se tocan.",
  layers: [
    {
      key: "productividad",
      title: "Productividad",
      note: "Organiza y ejecuta.",
      features: [
        "Agendás por chat: «dentista mañana a las 7» y listo",
        "Cierra tareas en un mensaje, sin formularios",
        "Se anticipa: te arma el día antes de que lo pidas",
      ],
    },
    {
      key: "memoria",
      title: "Memoria",
      note: "Recuerda tu contexto.",
      features: [
        "Nombres, charlas y decisiones, con fecha y contexto",
        "Cita textual lo que recuerda — nunca inventa",
        "Le preguntás natural: «¿qué libro me recomendó Sofi?»",
      ],
    },
    {
      key: "bienestar",
      title: "Bienestar",
      note: "Acompaña sin invadir.",
      features: [
        "Lee tu energía y tus patrones de descanso",
        "Te frena antes del burnout, no después",
        "Está cuando la necesitás; se corre cuando no",
      ],
    },
    {
      key: "aconseja",
      title: "Aconseja",
      note: "Sugiere, no impone.",
      features: [
        "Te sugiere qué priorizar según tu energía y tus plazos",
        "Propone el próximo paso; la decisión la tomás vos",
        "Cada consejo sale de tu contexto, no de un manual genérico",
      ],
    },
  ],
  intersection: "Ninguna junta las tres. Ynara vive donde se tocan — y ahí te aconseja qué hacer.",
  competitors: [
    { name: "Motion", does: "organiza", but: "no recuerda ni acompaña." },
    { name: "Pi", does: "acompaña", but: "no organiza." },
    { name: "Notion AI", does: "produce", but: "no se adapta a vos." },
  ],
} as const;

export const memory = {
  eyebrow: "Privacidad",
  wordmark: "Memoria",
  // Statement grande del beat "confianza" — clave para que descarguen.
  statement: "Tus datos son tuyos. No se venden, nunca.",
  support:
    "Ynara te recuerda de verdad — nombres, charlas, tu forma de hacer las cosas. Pero la inferencia corre on-prem, privada: nada sale del perímetro.",
  layers: [
    { title: "Semántica", body: "Quién sos y qué te importa: nombres, gustos, rutinas." },
    { title: "Episódica", body: "Lo que pasó: cada conversación, con su fecha y contexto." },
    { title: "Procedural", body: "Cómo hacés las cosas: tus atajos, tu forma de trabajar." },
  ],
  pull: "Cita textual lo que recuerda. Nunca inventa.",
  privacy: ["Sin venta de datos", "Sin publicidad", "Inferencia on-prem"],
} as const;

export const feel = {
  eyebrow: "Cómo se siente",
  wordmark: "Voz",
  title: "Habla como una persona.",
  support:
    "Directa, sin sermones. Le escribís en una línea y resuelve. Cuando no sabe algo, te lo dice.",
  chats: [
    {
      mode: "Productividad",
      user: "agendá dentista mañana a las 7",
      ynara: "Listo, agendado mañana 19hs.",
    },
    {
      mode: "Memoria",
      user: "¿cómo se llamaba el libro que me recomendaron?",
      ynara: "“La sustancia”, te lo pasó Sofi el 12 de mayo.",
    },
    {
      mode: "Bienestar",
      user: "estoy fundido, ¿paro un rato?",
      ynara: "Venís a full hace 3 días. Una pausa de 20 min te viene bien.",
    },
  ],
} as const;

export const pricing = {
  eyebrow: "Precio",
  wordmark: "Gratuito",
  statement:
    "Los tres pilares y la memoria reciente, gratis para siempre. Premium suma memoria extendida, funciones avanzadas y multidispositivo por USD 4–6 al mes.",
  title: "Empezás gratis. Subís cuando quieras.",
  lead: "Lo esencial gratis, para siempre. La suscripción suma memoria extendida y funciones avanzadas.",
  plans: [
    {
      name: "Gratuito",
      price: "$0",
      period: "para siempre",
      features: ["Los tres pilares", "Memoria reciente", "Un dispositivo"],
      cta: "Quiero sumarme",
      featured: false,
    },
    {
      name: "Premium",
      price: "USD 4–6",
      period: "por mes",
      features: [
        "Memoria extendida",
        "Funciones avanzadas",
        "Multidispositivo",
        "Prioridad de respuesta",
      ],
      cta: "Quiero sumarme",
      featured: true,
    },
  ],
  note: "Sin publicidad. Sin venta de datos. Nunca.",
} as const;

export const cta = {
  eyebrow: "Acceso anticipado · 2026",
  title: "Pensar mejor, recordar siempre.",
  statement:
    "MVP en el segundo semestre de 2026, para iOS y Android. Los primeros de la lista entran al acceso anticipado y la estrenan antes que nadie. Sin spam: un solo mail, cuando esté lista.",
  lead: "Tu asistente personal con memoria. MVP en el segundo semestre de 2026, para iOS y Android.",
  primary: {
    label: "Quiero sumarme",
    href: "mailto:hola@ynara.app?subject=Quiero%20sumarme%20a%20Ynara",
  },
  stores: ["App Store — Próximamente", "Google Play — Próximamente"],
} as const;

export const footer = {
  tagline: "Organiza. Recuerda. Acompaña.",
  columns: [
    {
      title: "Producto",
      links: [
        { label: "Qué hace", href: "#producto" },
        { label: "Demo", href: "#voz" },
        { label: "Privacidad", href: "#privacidad" },
        { label: "Precio", href: "#precio" },
      ],
    },
    {
      title: "Sumate",
      links: [
        { label: "Acceso", href: "#descargar" },
        { label: "Contacto", href: "mailto:hola@ynara.app" },
      ],
    },
  ],
  meta: "Self-hosted · Hecho en Argentina",
} as const;
