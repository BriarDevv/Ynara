# ADR-011: Auth permanece organizado por capa — criterio de feature-packages vs layer-split

## Estado
Aceptado

## Fecha
2026-06-03

## Contexto

La auditoría de arquitectura del backend (2026-06-02) levantó un finding **LOW /
organizacional**: *"`core/` se está volviendo un grab-bag (8 módulos: config, crypto,
db_guard, deps, observability, ratelimit, security, token_store); considerar mover
`token_store`/auth a un paquete `app/auth/`."* Se difirió con la condición explícita de
**escribir un ADR antes de tocar nada** — porque no es un bug, es una decisión de
límites con trade-offs reales.

El backend tiene una estructura **híbrida**, verificada contra el código:

- **Layer-split** para los dominios ordinarios: `api/v1/` (routers), `services/`
  (dominio), `schemas/` (DTOs), `core/` (infra cross-cutting), `models/` (ORM).
- **Feature-packages** SOLO para los dos subsistemas pesados y autocontenidos:
  `app/llm/` (~13-20 módulos con su propio `clients/`, `prompts/`, `tools/`, `schemas`,
  `config`) y `app/memory/` (las 3 capas de storage cifrado + `audit.py`, declaradas
  sagradas, regla #3).

La superficie de **auth** hoy se reparte por capa:

| Pieza | Ubicación | Dominio |
|---|---|---|
| Router HTTP (`/auth/*`) | `app/api/v1/auth.py` | auth |
| Service (register/authenticate) | `app/services/auth.py` | auth |
| Schemas wire | `app/schemas/auth.py` | auth |
| JWT (jose) + bcrypt | `app/core/security.py` | auth |
| Token store (blocklist jti + familia) | `app/core/token_store.py` | **compartido** |
| Rate-limit | `app/core/ratelimit.py` | **compartido** |
| Auth deps (`get_current_user`, ...) | dentro de `app/core/deps.py` | auth (wiring) |

Un **panel de diseño adversarial de 3 asientos** (consolidación / consistencia /
neutral) evaluó cuatro opciones — `full_package`, `moderate_package`,
`minimal_infra_move`, `reject_keep_layered` — verificando el acoplamiento contra el
código. Hechos clave que los tres asientos confirmaron:

- **`token_store` es infra dual**: respalda TANTO la blocklist de auth COMO las
  primitivas genéricas (`incr_with_ttl` / `set_flag` / `has_flag` / `delete`) que
  consume el rate-limit. Lo construye el lifespan de `main.py` y lo importan `deps` y
  `ratelimit`.
- **`ratelimit` NO es auth-only**: lo consumen `app/api/v1/chat.py`
  (`check_chat_rate_limit`) y `app/api/v1/memory.py` (`check_memory_export_rate_limit`)
  además de `app/api/v1/auth.py`, e importa `TokenStore` de `token_store`.
- Por lo tanto, **mover `token_store`/`ratelimit` a `app/auth/` invierte el grafo**:
  `core/ratelimit → app/auth` (infra dependiendo de un paquete de dominio), y arrastra
  a `chat`/`memory` a depender de `app/auth` para un rate-limit que no es de auth.
- **`security.py` es el único módulo 100% auth-domain y leaf** (importa solo
  `core/config`); no tiene dependencia entrante de `ratelimit`. Es el único que se
  movería sin invertir nada.
- **`services/` contiene solo `auth.py`** hoy: es una capa **joven**, preparada para
  crecer (users / billing / notifications), no un mal diseño.
- **Deuda preexistente verificada**: `core/deps.py` YA importa `app.llm.clients.*`
  (`deps.py`) para tipar `get_llm_client` — la única grieta `core→feature-package` del
  repo. Es deuda conocida, **no un modelo a replicar** con auth.

## Decisión

**Auth permanece organizado por capa**, igual que los demás dominios ordinarios
(`sessions`, `chat`, `users`). **No se crea `app/auth/`.** `token_store` y `ratelimit`
**permanecen en `core/`** por ser infra compartida. La acción de cierre del finding es
**documental**: este ADR fija el criterio y una nota de superficie en el AGENTS del
backend, para que el grab-bag de `core/` no se vuelva a leer como bug pendiente.

### D1 — Criterio de feature-package (cuándo SÍ corresponde `app/<dominio>/`)

Un dominio se gana un feature-package **solo** cuando es **pesado Y autocontenido**:
muchos módulos internos con su propia sub-estructura (como `llm/` con
`clients/`+`prompts/`+`tools/`+`schemas`+`config`, o `memory/` con varias capas de
storage + audit). El criterio es **peso y cohesión interna**, no importancia ni
preferencia estética. Los dominios ordinarios —un router + un service + un schema +
infra delgada— se quedan **layer-split**.

### D2 — Auth es un dominio ordinario, no un subsistema pesado

Auth son 1 router + 1 service + 1 schema + helpers de infra (`security`, `token_store`)
delgados. No cruza el umbral de D1. El hecho de que `services/` tenga un solo módulo
(`auth.py`) NO justifica disolver la capa: una capa con un inquilino es **señal de
juventud del dominio**, no de mal diseño; disolverla optimizaría para el presente y
rompería la simetría que hace predecible *dónde vive cada cosa*.

### D3 — `token_store` y `ratelimit` son infra compartida: se quedan en `core/`

El rate-limit sirve a chat y memory-export además de auth, y se apoya en las primitivas
genéricas de `token_store`. Moverlos a un paquete de auth invierte la dependencia
sana **dominio → infra (core)**. Se quedan en `core/` a propósito; esto deja el finding
del audit **parcialmente sin "atender"** en el sentido literal de mover archivos —
correcto, porque la premisa del finding (que esos módulos son de auth) es falsa.

### D4 — La superficie de auth se documenta (anti-re-litigación)

Se agrega una nota en `apps/backend/AGENTS.md §2` que mapea dónde vive cada pieza de
auth y por qué `token_store`/`ratelimit` están en `core/`. Sin esa nota, un lector nuevo
puede tardar en ubicar la superficie de auth (repartida en capas) o intentar el
`full_package` y reintroducir la inversión.

### D5 — Trigger de re-evaluación

Si auth **crece** —MFA, OAuth providers, password reset, sesiones server-side— al punto
de tener su propia sub-estructura (p.ej. `>6` módulos auth-only, o un `providers/` /
`clients/` propio), **se revisa esta decisión**: en ese escenario auth podría cruzar el
umbral de D1 y un `app/auth/` pasaría a justificarse. Hoy no.

## Consecuencias positivas

- **Consistencia preservada**: todos los dominios ordinarios siguen la misma regla
  layer-split; "dónde vive X" sigue siendo predecible.
- **Cero churn, cero inversión de dependencias, cero ruptura de la convención "routers
  en `api/v1/`"**.
- **El finding del audit queda atendido correctamente**: documentado con su porqué, no
  arrastrado como bug pendiente ni "arreglado" con un reorg que empeoraría el grafo.
- **Criterio explícito** para futuros dominios: zanja de antemano el debate
  "¿esto merece carpeta propia?".

## Consecuencias negativas

- **`core/` sigue con 8 módulos** (percepción de grab-bag): se acepta y se mitiga con
  esta doc + la nota de superficie. Son todos infra cross-cutting legítima.
- **La superficie de auth sigue repartida en capas**: hay que conocer el criterio para
  navegarla; mitigado por la nota en AGENTS y por esta tabla.
- **Deuda `core→llm` intacta** (`deps.py` importa `app.llm.clients.*`): este ADR no la
  resuelve, solo la nombra para no replicarla con auth.

## Alternativas descartadas

- **`full_package`** (mover router + service + schema + security + token_store +
  ratelimit + auth-deps a `app/auth/`): **INVIERTE** `core/ratelimit → app/auth` y
  arrastra a los routers de chat/memory a depender de `app/auth`; máximo churn. Rechazada
  por los tres asientos.
- **`moderate_package`** (mover router + service + schema + security + auth-deps;
  `token_store`/`ratelimit`/db-deps quedan en core): **evita la inversión** pero rompe
  la convención "routers en `api/v1/`", convierte a auth en el **único dominio ordinario
  con paquete propio** (asimetría que invita a paquetizar sessions/chat/users), y paga
  ~12-16 archivos de churn por una ganancia de navegabilidad marginal sobre un dominio
  de 3 módulos.
- **`minimal_infra_move`** (sub-paquete `app/core/auth/` con security + token_store +
  auth-deps, y split de `deps.py` en db/auth/llm con re-export): ordena el grab-bag sin
  paquete top-level, pero introduce la ambigüedad "medio feature-package", y el split de
  `deps.py` toca `get_db` (alimenta TODOS los endpoints) detrás de un re-export shim que
  tiende a volverse permanente. Riesgo > beneficio para un finding LOW.
- **Mover solo `security.py`**: es el único move sin inversión, pero aislado es
  **incoherente** con "mantener layer-split" y agrega la pregunta "¿por qué `security.py`
  es especial y no `service`/`schema`?". Se descarta a favor de la consistencia total.

## Impacto en archivos del repo

### `docs/architecture/README.md`
Agregar ADR-011 a la tabla "ADRs actuales".

### `apps/backend/AGENTS.md` (§2 — Mapa del código)
Agregar la nota de superficie de auth + el criterio de feature-package (D1) + el porqué
de `token_store`/`ratelimit` en `core/` (D3).

### Código
**Sin cambios.** Esta es una decisión de organización + documentación; no mueve ni edita
módulos de `app/`.

## Links

- [`ADR-010`](./ADR-010-memory-architecture-v2.md) — estableció el patrón feature-package
  (`memory/` como subsistema pesado autocontenido detrás de Protocols).
- [`ADR-001`](./ADR-001-monorepo-vs-multirepo.md) — organización del monorepo.
- Auditoría de arquitectura del backend (2026-06-02, finding LOW de `core/` grab-bag).
- `apps/backend/app/core/{security,token_store,ratelimit,deps}.py`,
  `app/services/auth.py`, `app/schemas/auth.py`, `app/api/v1/auth.py` — la superficie que
  este ADR decide NO mover.
- [`apps/backend/AGENTS.md`](../../../apps/backend/AGENTS.md) — §2 Mapa del código (nota
  de superficie de auth).
