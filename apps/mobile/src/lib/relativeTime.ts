/**
 * Tiempo relativo en español rioplatense para el historial del chat
 * ("recién", "hace 5 min", "ayer", "hace 3 d"). Pura; `now` inyectable para
 * tests. No usa Intl (soporte parcial en Hermes) — aritmética simple.
 */
export function relativeTime(timestamp: number, now: number = Date.now()): string {
  const diffMin = Math.floor(Math.max(0, now - timestamp) / 60000);
  if (diffMin < 1) return "recién";
  if (diffMin < 60) return `hace ${diffMin} min`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `hace ${diffHour} h`;

  const diffDay = Math.floor(diffHour / 24);
  if (diffDay === 1) return "ayer";
  if (diffDay < 7) return `hace ${diffDay} d`;

  return `hace ${Math.floor(diffDay / 7)} sem`;
}
