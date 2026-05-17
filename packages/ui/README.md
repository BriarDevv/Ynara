# @ynara/ui

Componentes UI compartidos entre `apps/web` y (eventualmente)
`apps/mobile`. Mientras `DESIGN.md` esté vacío, este package queda
casi vacío y usa tokens neutrales.

## Convención

- Componentes "tontos" presentacionales sin lógica de dominio.
- Re-export selectivo desde `src/index.ts` (sin barrel monstruo).
- shadcn/ui se copia con `npx shadcn add` directamente en
  `apps/web/src/components/ui/`; este package es para componentes
  **realmente** compartibles entre web y mobile.
- Para mobile, los componentes deben ser RN-compatibles (NativeWind).
  Mientras tanto, mantener web-only y duplicar en mobile si hace
  falta.
