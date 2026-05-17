# apps/mobile/AGENTS.md — Reglas del frontend mobile

> Fuente canónica del repo: [`../../AGENTS.md`](../../AGENTS.md).

## Reglas duras

1. **Sin cliente Supabase** (regla #5 global). Todo dato va por la
   API de FastAPI.
2. **Sin llamadas directas a APIs de IA externa** (regla #4). La
   inferencia está en el backend.
3. **TypeScript strict.**
4. **No hardcodear colores ni tipografías.** NativeWind con tokens
   compartidos con la web (mismos nombres en
   `apps/web/src/app/globals.css`). Mientras `DESIGN.md` esté
   vacío, usar tokens neutrales.
5. **Tokens en SecureStore.** No usar AsyncStorage para credenciales.
   `expo-secure-store` es obligatorio para JWT y refresh tokens.

## Patrones

- **Expo Router** file-based.
- **TanStack Query** para data del cliente, compartiendo querykeys
  con web cuando aplique.
- **Zustand** para estado global mínimo.
- **expo-notifications** para push (TODO: definir provider — Expo
  Push vs APNs/FCM directos).

## Builds

Ver [`EAS.md`](./EAS.md). Builds siempre via EAS, nunca local salvo
debugging. Submit a stores requiere confirmación humana.

## Naming

- Rutas Expo Router: kebab-case en archivos (`modo-bienestar.tsx`).
- Componentes: PascalCase.
- Hooks: useNombre.
