# tests/

Tests E2E del repo. Los tests unitarios y de integración por app
viven en `apps/<app>/tests/`.

## Subcarpetas

- `e2e/` — Playwright E2E del frontend web (TODO configurar).

## Convención

- Los E2E corren contra un backend real (de staging o local). Sin
  mocks.
- Variables de entorno de tests vienen de `.env.test` (gitignored).
- Tests E2E disparan flows completos: signup → primer chat → memoria
  guardada → recall.

## Open questions

<!-- TODO -->
- Detox para E2E de mobile además de Playwright web?
- Frecuencia de E2E en CI (cada PR vs cada noche).
