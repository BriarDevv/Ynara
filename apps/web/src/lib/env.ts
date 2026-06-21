import { z } from "zod";

/**
 * Schema de las variables de entorno expuestas al cliente.
 * Sólo NEXT_PUBLIC_* — todo lo server-only vive en otro schema cuando aparezca.
 */
const ClientEnvSchema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8080"),
  // Default ON: la web desarrolla offline-first sobre fixtures (MSW). Para
  // apuntar al backend real se opta por salir con NEXT_PUBLIC_ENABLE_MOCKS=false
  // (más NEXT_PUBLIC_API_URL al FastAPI) en .env.local. Mismo patrón que admin.
  NEXT_PUBLIC_ENABLE_MOCKS: z
    .enum(["true", "false"])
    .default("true")
    .transform((v) => v === "true"),
});

export type ClientEnv = z.infer<typeof ClientEnvSchema>;

/**
 * En Next.js, las NEXT_PUBLIC_* se inlinean en build time. Acceder vía
 * process.env.NEXT_PUBLIC_FOO directo es lo que el bundler sabe reemplazar.
 * Si lo accedés vía destructuring dinámico, el reemplazo no ocurre.
 */
const rawEnv = {
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_ENABLE_MOCKS: process.env.NEXT_PUBLIC_ENABLE_MOCKS,
};

const parsed = ClientEnvSchema.safeParse(rawEnv);

if (!parsed.success) {
  console.error("[env] Variables de entorno inválidas:", parsed.error.flatten().fieldErrors);
  throw new Error("Variables de entorno del cliente inválidas. Ver consola.");
}

export const env: ClientEnv = parsed.data;

/**
 * True si los mocks de MSW deben prenderse en este runtime.
 *
 * **Flag-driven con default ON** (mismo patrón que apps/admin): los mocks se
 * controlan exclusivamente con `NEXT_PUBLIC_ENABLE_MOCKS`, que default-ea a
 * `true` en el schema. Resultado: `pnpm dev` sin `.env.local` sigue mockeando
 * (offline-first), y se apunta al backend real opt-out con
 * `NEXT_PUBLIC_ENABLE_MOCKS=false`.
 *
 * **Hard-gate por NODE_ENV**: en `production` los mocks SIEMPRE están off
 * sin importar el flag, para evitar accidentes que filtren MSW al bundle
 * o expongan handlers de auth fake en el ambiente real.
 */
export const shouldEnableMocks =
  process.env.NODE_ENV !== "production" && env.NEXT_PUBLIC_ENABLE_MOCKS;
