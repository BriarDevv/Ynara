# TAILSCALE-SHARING.md — Usar Ynara desde otra máquina por Tailscale

> Hostear el serving + el panel admin + la web en la máquina de la GPU
> (la 4080) y usarlos desde **otra máquina del mismo tailnet**, sin abrir
> ningún puerto a internet. Todo el tráfico viaja cifrado por la red privada
> de Tailscale (`100.x.y.z`).

Asume que ya hiciste `INSTALL.md` y que el stack corre en local
(`LOCAL-DEV.md`).

## Qué se comparte

El panel admin tiene una pantalla **Conexión / Compartir**
(`/v1/admin/connectivity`) que detecta tu IP del tailnet y arma las URLs de
las cuatro superficies, en orden de uso:

| Superficie | Puerto | Para qué |
|---|---|---|
| **Panel admin** | `3002` | El playground: probar gemma4/qwen interactivo |
| **App web** | `3000` | Usar Ynara como producto (chat, memoria, agenda) |
| API (OpenAI-compatible) | `11434` | Pegarle a Ollama crudo (`/v1/chat/completions`) |
| Chat (Open WebUI) | `3001` | Chat web sobre Ollama, sin pasar por Ynara |

Los puertos son configurables (`ADMIN_PORT`, `WEB_PORT`, `OLLAMA_API_PORT`,
`OPENWEBUI_PORT` en `apps/backend/.env`). El endpoint arma la URL aunque el
servicio no esté levantado: levantá solo las superficies que quieras usar.

## Conceptos clave (leer antes de copiar comandos)

- **`<host-ip>` = la IP del tailnet de la máquina de la GPU** (donde corren
  backend + admin + web). La sacás con `tailscale ip -4` o de la pantalla
  Compartir. La otra máquina abre `http://<host-ip>:3002`, **no** `localhost`
  (su `localhost` es ella misma).
- El navegador de la otra máquina carga la app servida por el host y desde
  ahí le pega al backend. Por eso:
  - El front necesita `NEXT_PUBLIC_API_URL=http://<host-ip>:8080`.
  - El backend necesita `<host-ip>:3002` y `<host-ip>:3000` en
    `CORS_ORIGINS` (es el `Origin` del navegador remoto).

## Paso 1 — Tailscale en el host

```sh
# Instalar (Windows): https://tailscale.com/download/windows
# o winget:
winget install tailscale.tailscale

tailscale up          # logueate con tu cuenta
tailscale ip -4       # anotá la IP del tailnet, p.ej. 100.64.0.1
```

En la otra máquina: instalá Tailscale y logueate con **la misma cuenta**
(quedan en el mismo tailnet automáticamente). Si la otra máquina es de otra
persona, invitala con un *share* del nodo o por ACLs — pero para tu propio
uso, misma cuenta alcanza.

## Paso 2 — Serving real (Ollama)

El default es `LLM_BACKEND=fake` (no usa GPU). Para servir los modelos de
verdad, en `apps/backend/.env`:

```sh
LLM_BACKEND=vllm        # nombre legacy del cliente OpenAI-compatible; apunta a Ollama
LLM_SERVING=[{"base_url":"http://localhost:11434/v1","models":["gemma4","qwen"]}]
```

Y dejá Ollama corriendo con los modelos (`ollama serve` + los `gemma4`/`qwen`
ya pulleados). Verificá: `curl http://localhost:11434/api/tags`.

## Paso 3 — Backend accesible en el tailnet

El `make dev-backend` bindea a `127.0.0.1` (solo local). Para exponerlo al
tailnet, corré uvicorn con `--host 0.0.0.0`:

```sh
cd apps/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Y agregá los orígenes del tailnet a `CORS_ORIGINS` (CSV, sin espacios).
Reemplazá `<host-ip>` por tu IP real:

```sh
CORS_ORIGINS=http://localhost:3000,http://localhost:8081,http://<host-ip>:3002,http://<host-ip>:3000
```

> En `development` el backend acepta orígenes `localhost` + el tailnet sin
> drama. **No** pongas `ENVIRONMENT=production`: el boot aborta si quedan
> orígenes de dev (`_reject_dev_config_in_prod`) y exige otras cosas (master
> key, etc.). Para compartir tu stack de dev, quedate en `development`.

## Paso 4 — Panel admin (y web) apuntando al tailnet

Para que el navegador remoto le pegue al backend correcto, el front tiene que
apuntar a `<host-ip>`, no a `localhost`. En `apps/admin/.env.local`:

```sh
NEXT_PUBLIC_API_URL=http://<host-ip>:8080
NEXT_PUBLIC_ENABLE_MOCKS=false      # pegar al backend real, no a los fixtures MSW
```

Levantá el panel escuchando en todas las interfaces (queda en `:3002`):

```sh
pnpm --filter @ynara/admin dev -- -H 0.0.0.0
```

Para la **web** (fase 2), mismo patrón en `apps/web/.env.local`
(`NEXT_PUBLIC_API_URL=http://<host-ip>:8080`) y levantala también bindeada:

```sh
pnpm --filter web dev -- -H 0.0.0.0      # queda en :3000
```

> `next dev` por defecto puede escuchar solo en `localhost` (depende de la versión
> de Next; el repo usa Next 16). El `-H 0.0.0.0` explícito garantiza que el tailnet
> la alcance — no dependas del default.

## Paso 5 — Descubrir las URLs para compartir

Entrá al panel (`http://localhost:3002` en el host) → **Conexión / Compartir**.
Si el tailnet está arriba vas a ver las cuatro URLs listas con tu `<host-ip>`.
O por API:

```sh
curl -H "Authorization: Bearer <tu-jwt-admin>" http://localhost:8080/v1/admin/connectivity
```

## Paso 6 — Entrar desde la otra máquina

1. Abrí `http://<host-ip>:3002` en el navegador de la otra máquina.
2. Login con **tu cuenta admin** (la de siempre, p.ej. `admin@ynara.app`).
3. Andá a **Playground** y probá gemma4 / qwen.

Tu cuenta tiene que ser admin: o `users.is_admin = true`, o su UUID en
`ADMIN_BOOTSTRAP_IDS` (CSV) de `apps/backend/.env`. El gate es
`user.is_admin OR str(user_id) in ADMIN_BOOTSTRAP_IDS`.

## Seguridad

- **No expongas estos puertos a internet.** Tailscale ya te da una red
  privada cifrada; no hace falta port-forwarding ni túnel público.
- El panel admin muestra métricas y audit de **todos** los usuarios. Si algún
  día compartís el tailnet con un tercero, dale acceso por **Open WebUI**
  (`:3001`) o la **API** (`:11434`), no el panel — o usá ACLs de Tailscale
  para limitar qué nodos llegan a qué puertos.
- `CORS_ORIGINS` es allowlist exacta: solo los orígenes que listes pueden
  pegarle al backend desde un navegador.

## Troubleshooting

- **La pantalla Compartir dice "Todavía no hay nada para compartir"**: el
  probe vio el tailnet abajo. Corré `tailscale status` en el host; si dice
  `NeedsLogin`, `tailscale up`.
- **CORS error en la consola del navegador remoto**: falta
  `http://<host-ip>:3002` (o `:3000`) en `CORS_ORIGINS`. Reiniciá el backend
  tras editarlo (`get_settings` cachea al boot).
- **El panel carga pero todo da error de red**: `NEXT_PUBLIC_API_URL` quedó en
  `localhost` (apunta a la máquina cliente). Tiene que ser `<host-ip>:8080`.
- **No conecta a `<host-ip>:8080`**: el backend bindeó a `127.0.0.1`. Usá
  `--host 0.0.0.0`. En Windows, aceptá el prompt del Firewall la primera vez.
- **`tailscale: command not found`**: no está instalado o no está en el PATH
  (en Windows reabrí la terminal después de instalar).
