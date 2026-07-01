# ADR-027: Web en Vercel + backend/GPU en la PC por Tailscale Funnel, con toggle de IA

## Estado
Aceptado

## Fecha
2026-06-30

## Contexto

La topología documentada
([`docs/architecture/diagrams/deploy-topology.md`](../diagrams/deploy-topology.md),
[`docs/operations/DEPLOY.md`](../../operations/DEPLOY.md)) asume el **backend +
Ollama corriendo en una VPS LATAM con la 4080, detrás de Cloudflare Tunnel**. Eso
**no matchea la realidad**: la RTX 4080 Super vive en la **PC del usuario**, no en
una VPS. Una VPS con GPU de 16 GB+ es cara y redundante teniendo la placa en la
máquina. El plan real de puesta a producción (ver notas de prod-readiness) ya es
*"cómputo → la PC, dato → Supabase"*, accesible por **Tailscale**
([`docs/operations/TAILSCALE-SHARING.md`](../../operations/TAILSCALE-SHARING.md)).

Lo que se quiere ahora:

1. **Web siempre activa y pública** (deploy en Vercel — que ya es el plan oficial:
   `DEPLOY.md` → web por Vercel Git integration).
2. **Backend + IA en la PC** del usuario (FastAPI + worker Celery + Ollama sirviendo
   gemma4/qwen/bge-m3 en la 4080, ADR-014).
3. **Control manual de la IA**: el usuario decide cuándo la IA está disponible y
   cuándo no, sin tumbar la web.

El nudo técnico: la web hace los fetch **desde el browser del cliente**
(`NEXT_PUBLIC_API_URL`, client-side — ver
[`packages/core/src/api/client.ts`](../../../packages/core/src/api/client.ts)),
no desde el server de Vercel. Vercel **no está en la tailnet**, así que el link
web→backend depende de cómo se expone el backend de la PC. Además, Vercel sirve
HTTPS: un fetch a un backend HTTP plano (`http://100.x:8080`) lo **bloquea el
browser por mixed-content**.

Como cambia la topología de infra, va por ADR (AGENTS regla #6; CONTRIBUTING
"cambios arquitectónicos").

## Decisión

### 1. Web → Vercel (sin cambios respecto al plan)

`apps/web` deploya en Vercel (Next.js 16, deploy por Git integration en push a
`main`). Siempre activa, HTTPS, dominio público.

### 2. Backend + IA → la PC del usuario, expuesto por Tailscale Funnel

FastAPI + Celery (worker + beat) + Redis + Ollama corren en la PC de la 4080. El
backend se expone con **Tailscale Funnel**: HTTPS público y estable en
`https://<host>.<tailnet>.ts.net` (cert Let's Encrypt gestionado por Tailscale),
alcanzable desde cualquier browser —incluidos los que sirve Vercel— sin abrir
puertos ni exponer la IP real.

Funnel (público) en vez de Serve (solo tailnet) es lo que permite que la web
pública sea **usable por terceros**, no solo por dispositivos en la tailnet del
usuario. El HTTPS de Tailscale además **resuelve el mixed-content** (Vercel HTTPS
→ backend HTTPS).

Esto **reemplaza, para la fase MVP-personal, el par VPS + Cloudflare Tunnel** del
diagrama viejo. La ruta VPS + Cloudflare Tunnel queda reservada como opción de
escala V2 (si algún día el cómputo sale de la PC).

### 3. Toggle de IA a dos niveles

El usuario controla la disponibilidad de la IA con dos switches de distinto
alcance:

- **Nivel 1 — IA pausada (recomendado para el uso diario):** apagar **solo
  Ollama**. El backend sigue vivo → `login` / `memoria` / `dashboard` / `agenda`
  andan; solo el **chat** queda sin IA. `/v1/chat` debe **degradar con un estado
  honesto** ("IA pausada ahora") en vez de romper.
- **Nivel 2 — todo apagado:** bajar el backend/Funnel (o apagar la PC). La web en
  Vercel sigue arriba pero queda como **cáscara** (landing + onboarding hasta el
  login, que fallará hasta que el backend vuelva).

### 4. Configuración asociada

- **CORS:** agregar el dominio de Vercel (`https://<app>.vercel.app` y/o el
  dominio propio) a `CORS_ORIGINS`.
- **`NEXT_PUBLIC_API_URL`** (build-time en Vercel) apunta a la URL estable
  `https://<host>.<tailnet>.ts.net`, **no** a la IP `100.x`.
- **`ENVIRONMENT=production`** en el backend: cierra `/docs`, exige CORS sin
  `localhost`, master key fija y serving real (`_reject_dev_config_in_prod`).

## Consecuencias positivas

- **Web siempre disponible** (Vercel), con URL propia y costo casi nulo.
- La **GPU/IA vive en la PC**: sin pagar una VPS con GPU; el usuario controla
  cuándo servir inferencia (ahorro de luz/GPU cuando no la usa).
- **Tailscale Funnel** da HTTPS válido sin abrir puertos, sin exponer la IP real
  y sin depender de Cloudflare.
- El **nivel 1** desacopla el switch de IA del resto de la app: sigue usable
  (login, memoria, agenda) aunque la IA esté pausada.

## Consecuencias negativas

- **Exponer el backend a internet** (Funnel) cambia la postura vs el approach
  tailnet-privado de `TAILSCALE-SHARING.md`. Mitigado por JWT + rate-limit + CORS
  allowlist + `ENVIRONMENT=production`; exige los mínimos de prod (JWT fuerte,
  master key fija, **rotar la password de DB expuesta**).
- **Dependencia de la PC prendida** para todo lo que no sea la cáscara. "Web 100%
  funcional con la PC apagada" no es posible sin **separar el backend-core de la
  IA** (fuera de alcance de este ADR).
- **Presentación honesta de "IA pausada"** (nivel 1) es trabajo nuevo.
  **Corrección factual (2026-06-30):** este ADR afirmaba que `/v1/chat` "tira 500"
  con la IA caída — es **inexacto**. La investigación (workflow, evidencia
  `file:line`) probó que `ResilientClient` ya degrada a **200 + `finish_reason=
  "degraded"`** + texto enlatado (el 500 real es solo `ModelNotServedError` o el
  cliente fake). El gap NO es atrapar un 500 sino que el front **descarta**
  `finish_reason` y muestra el texto enlatado como respuesta normal (deshonesto).
  El trabajo real = consumir `finish_reason` y renderizar un estado honesto (ver
  ENDPOINTS.md `/v1/chat`). El switch instantáneo (evitar el budget de ~90s) queda
  como fase 1b.
- **Latencia** extra: browser → edge de Funnel → PC. Aceptable para MVP.

## Alternativas descartadas

- **VPS con GPU + Cloudflare Tunnel** (topología vieja del diagrama): una VPS con
  GPU de 16 GB+ es cara y redundante teniendo la 4080 en la PC. Queda como ruta de
  escala V2.
- **Tailscale Serve (privado, sin Funnel):** más seguro (nada expuesto a
  internet), pero la web pública solo funcionaría desde browsers en la tailnet del
  usuario → no permite que otros la usen. Se conserva como el modo "privado" si en
  algún momento se prefiere.
- **Backend serverless en Vercel:** no puede correr Ollama/GPU ni procesos
  long-running (worker Celery). No aplica.
- **Port-forwarding manual en el router:** expone la IP real, sin HTTPS fácil y
  más frágil que Funnel.

## Notas de implementación (fuera del alcance de la decisión)

- Habilitar Funnel en la ACL de Tailscale + servir el backend por HTTPS
  (`tailscale funnel`); validar el cert `*.ts.net`.
- `CORS_ORIGINS` con el dominio de Vercel; `ENVIRONMENT=production`.
- Degradación de `/v1/chat` con IA pausada: estado explícito (no 500) — trabajo de
  producto/back.
- El endpoint `/v1/admin/connectivity` (ADR-017) hoy arma URLs de tailnet
  privado; podría extenderse para reflejar la URL de Funnel.
- Actualizar `deploy-topology.md` + `DEPLOY.md` para reflejar esta topología (o
  marcar la de VPS/Cloudflare como ruta V2).
- Pendientes de prod ya conocidos: master key fija, JWT fuerte, rotar la password
  de DB, worker Celery + beat corriendo.
