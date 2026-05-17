# SKILL: Crear un componente UI

## Cuándo usar

Cuando hace falta un componente nuevo en la web (`apps/web`) o en
mobile (`apps/mobile`).

## Decidir dónde vive

- **Solo web, presentacional** → `apps/web/src/components/`.
- **Solo web, feature** → `apps/web/src/features/<feature>/`.
- **Compartido entre web y mobile** → `packages/ui/src/` (si es
  realmente compartible — RN compatible).
- **shadcn/ui copy-paste** → `apps/web/src/components/ui/` (uso
  `npx shadcn add ...`).
- **Solo mobile** → `apps/mobile/src/components/`.

## Pre-requisitos

- Tokens disponibles en `apps/web/src/app/globals.css` (mientras
  `DESIGN.md` esté vacío, usar genéricos).
- Si el componente es nuevo en el sistema visual, **discutir con
  @MateoGs013** antes de crearlo (CODEOWNER de DESIGN.md).

## Paso a paso

1. **Decidir ubicación** (ver arriba).
2. **Archivo** en `PascalCase.tsx` si es un componente principal,
   `kebab-case.tsx` para utilitarios.
3. **Props con TS strict** — sin `any`.
4. **Server component por defecto** en web; `"use client"` solo si
   hace falta.
5. **Tokens**: usar variables CSS / clases tokenizadas, no
   hardcodear colores ni tipografías.
6. **Accesibilidad**: roles ARIA, focus visible, contraste mínimo
   AA.
7. **`prefers-reduced-motion`**: si el componente anima.
8. **Tests** (cuando estabilicemos la suite — TODO).
9. **PR** con screenshot en la descripción si es visual.

## Checklist

- [ ] Ubicación correcta.
- [ ] TS strict, sin `any`.
- [ ] Tokens en lugar de valores hardcodeados.
- [ ] Accesibilidad básica.
- [ ] Responsive (si aplica).
- [ ] Screenshot en el PR.
