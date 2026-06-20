import type { ChatSessionMeta, ChatUiMessage } from "@ynara/core/features/chat";
import type { Mode } from "@ynara/shared-schemas";

/** Filtro temporal del panel de recientes (selección única). */
export type TimeBucket = "todos" | "hoy" | "ayer" | "semana" | "mes";

/** Una conversación lista para renderizar en el panel de recientes. */
export type RecentItem = {
  id: string;
  mode: Mode;
  /** Auto-nombre derivado del primer mensaje del usuario. */
  name: string;
  updatedAt: number;
};

/** Largo máximo del auto-nombre antes de recortar con elipsis. */
const NAME_MAX = 40;

/** Auto-nombre de una sesión sin ningún mensaje del usuario todavía. */
export const UNNAMED = "Chat nuevo";

const DAY_MS = 86_400_000;

/** Rango de "combining diacritical marks" que NFD separa de cada letra. */
const COMBINING_LO = 0x0300;
const COMBINING_HI = 0x036f;

/**
 * Auto-nombre de una conversación = primera línea del primer mensaje del usuario,
 * recortada a NAME_MAX. Sin mensaje de usuario aún → UNNAMED.
 *
 * Es derivado (no se persiste): así no toca el chat store de core (que comparte
 * web) y siempre refleja el estado actual de los mensajes.
 */
export function sessionName(messages: ChatUiMessage[] | undefined): string {
  const first = messages?.find((m) => m.role === "user" && m.text.trim() !== "");
  const line = first?.text.trim().split("\n")[0]?.trim() ?? "";
  if (line === "") return UNNAMED;
  return line.length > NAME_MAX ? `${line.slice(0, NAME_MAX).trimEnd()}…` : line;
}

/** Inicio del día calendario (00:00 local) del timestamp dado. */
function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/**
 * ¿Cae `updatedAt` dentro del bucket temporal, relativo a `now`? "hoy"/"ayer" son
 * por día calendario; "semana"/"mes" son ventanas móviles (últimos 7 / 30 días).
 */
export function inTimeBucket(updatedAt: number, now: number, bucket: TimeBucket): boolean {
  switch (bucket) {
    case "todos":
      return true;
    case "hoy":
      return updatedAt >= startOfDay(now);
    case "ayer": {
      const start = startOfDay(now);
      return updatedAt >= start - DAY_MS && updatedAt < start;
    }
    case "semana":
      return updatedAt >= now - 7 * DAY_MS;
    case "mes":
      return updatedAt >= now - 30 * DAY_MS;
  }
}

/**
 * Normaliza para comparar: minúsculas + sin diacríticos (acción ≈ accion). NFD
 * separa los acentos en combining marks y los descartamos por code point (sin
 * meter el carácter combinante en una regex), para que el filtro matchee con o
 * sin tildes.
 */
function normalize(s: string): string {
  return Array.from(s.toLocaleLowerCase().normalize("NFD"))
    .filter((ch) => {
      const cp = ch.codePointAt(0) ?? 0;
      return cp < COMBINING_LO || cp > COMBINING_HI;
    })
    .join("");
}

/** ¿El nombre matchea el query? Query vacío matchea todo. Insensible a acentos. */
export function matchesQuery(name: string, query: string): boolean {
  const q = normalize(query.trim());
  return q === "" || normalize(name).includes(q);
}

/**
 * Lista de recientes lista para la UI: filtra por bucket temporal y por query
 * (sobre el auto-nombre), deriva el nombre de cada sesión y ordena por
 * `updatedAt` desc. El componente solo aporta `query`/`bucket`/`now`.
 */
export function buildRecents(
  sessions: Record<string, ChatSessionMeta>,
  messages: Record<string, ChatUiMessage[]>,
  opts: { query: string; bucket: TimeBucket; now: number },
): RecentItem[] {
  return Object.values(sessions)
    .filter((s) => inTimeBucket(s.updatedAt, opts.now, opts.bucket))
    .map((s) => ({
      id: s.id,
      mode: s.mode,
      name: sessionName(messages[s.id]),
      updatedAt: s.updatedAt,
    }))
    .filter((item) => matchesQuery(item.name, opts.query))
    .sort((a, b) => b.updatedAt - a.updatedAt);
}
