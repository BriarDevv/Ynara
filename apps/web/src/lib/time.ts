/**
 * Saludo según la hora del día (plan §5.2). Rangos:
 *  - 06:00–11:59 → "Buen día"
 *  - 12:00–19:59 → "Buenas tardes"
 *  - 20:00–05:59 → "Buenas noches"
 *
 * Recibe la fecha por parámetro para ser testeable sin mockear el reloj.
 */
export function getGreeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour >= 6 && hour < 12) return "Buen día";
  if (hour >= 12 && hour < 20) return "Buenas tardes";
  return "Buenas noches";
}
