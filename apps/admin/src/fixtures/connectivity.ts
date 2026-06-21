import { ConnectivityOut, type ConnectivityOutT } from "@/features/sharing/schemas";

/**
 * Fixture de `GET /v1/admin/connectivity` (Conexión / Compartir).
 *
 * Estado feliz para dev/demo: tailnet arriba en "lonchos" (100.64.0.1) con las cuatro
 * superficies para compartir (panel admin + app web + API OpenAI-compatible de Ollama +
 * Open WebUI). El panel y la web van primero: es lo que usa un invitado.
 * Parseado por su Zod, igual que el resto de fixtures: un fixture roto tira acá.
 */
export function connectivityFixture(): ConnectivityOutT {
  return ConnectivityOut.parse({
    tailscale: {
      up: true,
      hostname: "lonchos",
      tailnet_ip: "100.64.0.1",
      detail: "up",
    },
    targets: [
      { label: "Panel admin", url: "http://100.64.0.1:3002", port: 3002 },
      { label: "App web", url: "http://100.64.0.1:3000", port: 3000 },
      { label: "API (OpenAI-compatible)", url: "http://100.64.0.1:11434/v1", port: 11434 },
      { label: "Chat (Open WebUI)", url: "http://100.64.0.1:3001", port: 3001 },
    ],
  });
}
