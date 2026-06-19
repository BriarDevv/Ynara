# AUTH.md — Flujo de autenticación del panel

Wire de auth del panel admin contra la API real de FastAPI (`/v1/auth/*`). El
panel sigue andando 100% en dev con MSW (mock-first), sin backend.

> ⚠️ **Contrato REAL, no provisional.** El wire usa el contrato real
> `/v1/auth/*` (snake_case), mirroreado en
> [`src/features/auth/schemas.ts`](../src/features/auth/schemas.ts).
> **`@ynara/shared-schemas/auth` es provisional (camelCase `token`/`userId`/
> `expiresAt`, pendiente de acuerdo con backend) y NO se usa acá.** No
> importarlo en `apps/admin`.

---

## Contrato de endpoints (verificado)

| Endpoint | Body | OK | Errores |
|---|---|---|---|
| `POST /v1/auth/token` | `{ email, password }` | `200` `TokenOut { access_token, token_type: "bearer", refresh_token?: string\|null }` | `401` credenciales inválidas (`detail: "credenciales invalidas"`); `429` lockout (`Retry-After`) |
| `GET /v1/auth/me` (Bearer access) | — | `200` `UserOut { id, email, display_name, onboarding_completed, retention_sensitive_days, created_at, updated_at }` | `401` token inválido |
| `POST /v1/auth/logout` (Bearer access) | `{ refresh_token? }` | `204` | — |
| `GET /v1/admin/*` (Bearer access) | — | `200` | `401` (`detail: "credenciales invalidas"`) si el user **no es admin** |

`UserOut` **no** trae `is_admin`: el eje de autorización lo resuelve el backend
devolviendo `401` en `/v1/admin/*`, no un campo del payload de `/me`.

---

## Flujo

### Login (`features/auth/hooks/useLogin.ts`)

`useMutation` en dos pasos encadenados (un fallo de cualquiera cae en `onError`):

1. `POST /v1/auth/token` **sin token** (`skipAuth: true`, endpoint público) →
   `TokenOut`. Se guarda `access_token` en el admin store (`setToken`) para que
   el cliente HTTP lo adjunte al paso 2.
2. `GET /v1/auth/me` (ya con el Bearer del paso 1) → `UserOut`. Con eso se
   completa la sesión: `setAuth({ adminId: id, token, displayName: display_name })`.

Mensajes mapeados (`loginErrorMessage`): `401 → "Credenciales inválidas"`,
`429 → "Demasiados intentos, probá más tarde"`, resto → genérico. Si el paso 2
falla tras guardar el token, `onError` resetea la sesión (nada de tokens a
medias). En éxito, la página redirige a `/`.

### Logout (`features/auth/hooks/useLogout.ts`)

Best-effort: `POST /v1/auth/logout` (si falla, se traga) → `reset()` del store →
`queryClient.clear()` → `router.replace("/login")`. La sesión local se baja pase
lo que pase.

### Guard de ruta (`components/shell/AuthGuard.tsx`)

Envuelve el route group `(panel)`: si no hay token (chequeo post-mount,
SSR-safe porque el token vive en localStorage), `router.replace("/login")`. No
pinta el panel hasta verificar (sin flash de contenido protegido).

### 401 global (`app/providers.tsx`)

`QueryCache.onError`: si una query devuelve `401` (token vencido **o** user
logueado que no es admin), `useAdminStore.reset()`. El `AuthGuard` reacciona al
`token === null` y rebota; el handler además redirige a
`/login?reason=forbidden` para que el login muestre **"Necesitás permisos de
admin"** (distingue "logueado sin permisos" de "no logueado").

---

## Pantalla de login (`app/login/page.tsx`)

Pública, **fuera** del grupo `(panel)` (no monta `AdminShell`, no tiene guard).
Editorial y de marca: `YnaraWordmark`, `LivingField` sutil de atmósfera, `Card`
central con el form (email + password) sobre **react-hook-form + Zod**
(`LoginRequest`). Botón con loading state (`Entrando…`), error inline, tokens
del design system (cero hex), tema Noche por default. El input vive inline
(`Field` con `forwardRef`): el panel no tiene `TextField` propio todavía.

---

## Dev sin backend (MSW)

`fixtures/handlers.ts` mockea también `/v1/auth/*` con el contrato real, así el
flujo login → dashboard anda 100% en dev:

- `POST /v1/auth/token` → `TokenOut` fake `{ access_token: "dev-admin-token",
  token_type: "bearer", refresh_token: null }` (acepta cualquier credencial).
- `GET /v1/auth/me` → `UserOut` fake con `display_name: "Admin Dev"`.
- `POST /v1/auth/logout` → `204`.

Los fixtures se parsean con su Zod (`MeOut`/`TokenOut`), igual que el resto: si
driftean del contrato, fallan al construirse.

---

## Token (recordatorio de perímetro)

El token admin vive **solo** en `stores/admin.ts` (Zustand persist, key
`ynara.admin`). Lo consume `lib/api.ts` (`configureApi.getToken`) y el
`Bearer` **solo** viaja a nuestra API (gate de perímetro en el client de core,
reglas #2/#4). Nunca hardcodeado, nunca a un host ajeno.
