import { z } from "zod";

/**
 * Schema de las variables de entorno expuestas al cliente mobile. Expo inlinea
 * las `EXPO_PUBLIC_*` en build time, así que se acceden por nombre directo
 * (no por destructuring dinámico, que el bundler no sabe reemplazar).
 */
const ClientEnvSchema = z.object({
  EXPO_PUBLIC_API_URL: z.string().url().default("http://localhost:8080"),
  // Mock-first del chat (FRONTEND-CHAT-PLAN.md): "true" → respuestas canned
  // locales por modo (sin LLM, reusa @ynara/core). Default off (pega al backend
  // real); hoy va "true" en .env hasta que exista el serving de IA del equipo.
  EXPO_PUBLIC_ENABLE_MOCKS: z
    .enum(["true", "false"])
    .default("false")
    .transform((v) => v === "true"),
});

export type ClientEnv = z.infer<typeof ClientEnvSchema>;

const rawEnv = {
  EXPO_PUBLIC_API_URL: process.env.EXPO_PUBLIC_API_URL,
  EXPO_PUBLIC_ENABLE_MOCKS: process.env.EXPO_PUBLIC_ENABLE_MOCKS,
};

const parsed = ClientEnvSchema.safeParse(rawEnv);

if (!parsed.success) {
  console.error("[env] Variables de entorno inválidas:", parsed.error.flatten().fieldErrors);
  throw new Error("Variables de entorno del cliente mobile inválidas. Ver consola.");
}

export const env: ClientEnv = parsed.data;
