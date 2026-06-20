import type { Mode } from "@ynara/shared-schemas";

/** Ventana de reanudación: si volvés al chat antes de esto, seguís la última charla. */
export const RESUME_TIMEOUT_MS = 60_000;

type SessionMeta = { id: string; mode: Mode; updatedAt: number };

/** ¿Reanudar la sesión activa? True si hay una y el tiempo afuera es menor al umbral. */
export function shouldResume(
  activeSessionId: string | null,
  lastActiveAt: number | null,
  now: number,
  timeoutMs: number = RESUME_TIMEOUT_MS,
): boolean {
  if (!activeSessionId || lastActiveAt === null) return false;
  return now - lastActiveAt < timeoutMs;
}

/** La sesión más reciente (por updatedAt) de un modo, o undefined si no hay. */
export function mostRecentSessionOfMode(
  sessions: Record<string, SessionMeta>,
  mode: Mode,
): SessionMeta | undefined {
  return Object.values(sessions)
    .filter((session) => session.mode === mode)
    .sort((a, b) => b.updatedAt - a.updatedAt)[0];
}
