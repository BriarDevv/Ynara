# CODE-STYLE.md — Estilo de código

## TypeScript

- **Strict mode** siempre (`"strict": true` en `tsconfig.json`).
- **Comillas dobles**, semicolons, trailing commas en multi-línea
  (config en `biome.json`).
- **Width**: 100 columnas.
- **Indent**: 2 espacios.
- **`type` imports**: siempre que sea posible, `import type {...}`.
- **Sin `any`**: usar `unknown` y narrowing, o tipos específicos.
- **React**: function components, hooks ordenados (state → effects →
  computed → handlers).
- **Server components por defecto** en Next.js 16 App Router; añadir
  `"use client"` solo cuando hace falta.
- **Sin barrel files gigantes**: re-exports puntuales en `index.ts`
  por package; evitar `export *` en apps.

## Python

- **Python 3.12+**.
- **Type hints siempre** en funciones públicas y métodos de clase.
- **Pydantic v2 strict** para schemas (request/response y memoria).
- **Async-first** en FastAPI: rutas `async def`, ORM async
  (SQLAlchemy 2 async).
- **Ruff** se encarga de formato + lint. Reglas en
  `apps/backend/pyproject.toml`.
- **Docstrings** estilo Google, en español:
  ```python
  def consolidate_memory(user_id: UUID) -> int:
      """Consolida memoria nueva del usuario en las 3 capas.

      Args:
          user_id: ID del usuario sobre el que consolidar.

      Returns:
          Cantidad de nuevos hechos persistidos.
      """
  ```
- **Sin `Any`** salvo en boundaries muy puntuales con justificación
  en comentario.

## CSS / Tailwind

- Tailwind v4 con `@theme`. Tokens en
  `apps/web/src/app/globals.css`.
- **No hardcodear colores ni tipografías** en componentes (regla #13
  de AI-GUIDELINES). Siempre por variable / clase tokenizada.
- **Mobile-first**: `class="text-base md:text-lg"` no al revés.
- Animaciones con GSAP + Lenis; respetar `prefers-reduced-motion`.

## React / Next.js

- App Router (Next.js 16).
- Server components por defecto.
- Suspense para data fetching donde tenga sentido.
- TanStack Query v5 para data del cliente; **no** mezclar con
  `useEffect` para fetching.
- Zustand v5 para estado global del cliente; mantenerlo chico.
- React Hook Form + Zod para formularios.

## React Native / Expo

- Expo Router (file-based, paralelo a Next App Router).
- NativeWind (Tailwind para RN) — mismos tokens que web.
- TanStack Query y Zustand compartidos desde packages cuando aplique.

## SQL / Alembic

- Naming de migraciones: `YYYYMMDD_HHMM_descripcion_corta.py`.
- Una migración = un cambio lógico atómico.
- Siempre implementar `downgrade()`.
- Tablas sagradas: review humano + 2 aprobaciones.
- Detalle: `apps/backend/docs/MIGRATIONS.md`.

## JSON / YAML

- 2 espacios de indent.
- `biome.json` con `trailingCommas: "none"` para JSON.

## Markdown

- 80 columnas (excepción: tablas y bloques de código).
- Headers ATX (`#`, `##`, ...).
- Listas con `-`, no `*`.
- Code blocks con fence triple + language hint (` ```ts ` no
  ` ``` `).
- Sin emojis salvo pedido explícito.
