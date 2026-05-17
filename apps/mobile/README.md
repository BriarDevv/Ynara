# apps/mobile — App móvil de Ynara

Expo SDK 53+ con Expo Router + TypeScript strict + NativeWind.

## Antes de tocar nada

1. [`../../AGENTS.md`](../../AGENTS.md)
2. [`./AGENTS.md`](./AGENTS.md)
3. [`./EAS.md`](./EAS.md) — builds y submits

## Estructura

```
src/
├── app/         # Expo Router (file-based)
├── components/
├── features/
├── lib/
├── config/
└── types/
```

## Stack

- Expo SDK 53+
- Expo Router (file-based routing)
- TypeScript strict
- NativeWind (Tailwind para RN)
- TanStack Query v5 (compartido conceptualmente con web)
- Zustand v5
- expo-secure-store (tokens en keychain/keystore)
- expo-notifications
- EAS Build + Submit

## Scripts

```sh
pnpm dev            # expo start
pnpm ios            # corre en simulador iOS
pnpm android        # corre en emulador / device Android
pnpm test           # tests
pnpm typecheck
```

## Variables de entorno

Copiar `.env.example` a `.env`. Variables que arrancan con
`EXPO_PUBLIC_` van al cliente; las demás solo a build time.

> **Regla #5**: prohibido `@supabase/supabase-js` desde acá.
