# apps/admin/docs/

Catálogos vivos del panel interno. Mantenerlos actualizados es parte del PR
correspondiente (misma regla que `apps/backend/docs/`).

## Archivos

- [`SCREENS.md`](./SCREENS.md) — las 6 pantallas + qué datos muestra cada una.
- [`COMPONENTS.md`](./COMPONENTS.md) — inventario de componentes (shell, ui,
  charts, features).
- [`DATA-CONTRACTS.md`](./DATA-CONTRACTS.md) — endpoints `/v1/admin/*` + Zod +
  nota de privacidad.
- [`AUTH.md`](./AUTH.md) — flujo de autenticación (`/v1/auth/*`): login, logout,
  guard de ruta, 401 global y mocks de dev.

## Arquitectura

Estos catálogos son el **qué**; el **cómo** y los gates viven en
[`../AGENTS.md`](../AGENTS.md). La decisión de fondo (por qué existe esta app,
qué se persiste y qué no, el eje de autorización `is_admin`) está en
[ADR-017](../../../docs/architecture/adrs/ADR-017-admin-app-observabilidad-control-plane.md).

## Regla

Si agregás una pantalla, componente, chart o contrato de API, **actualizás el
catálogo correspondiente** en el mismo PR. CI no lo verifica todavía, pero la
review humana sí.

## Invariante de privacidad

Todo lo documentado acá respeta el perímetro (reglas #2/#4): el panel muestra
**agregados** y **metadata exponible**, nunca contenido descifrado de memoria,
`record_hash`, `target_id` ni PII. Las omisiones se hacen en el **Zod schema**,
no solo en el render.
