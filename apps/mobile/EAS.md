# EAS.md — Builds y submits de Ynara mobile

## Setup inicial

1. Cuenta de Expo + acceso al proyecto (TODO: confirmar slug
   organizacional).
2. `eas login` localmente para dev de configuración.
3. EAS Token guardado como secret del repo:
   `EXPO_TOKEN` (Settings → Secrets → Actions).
4. Apple Developer + Google Play accounts conectados a EAS para
   submit.

## Perfiles

Definidos en `eas.json`:

- **development** — build interna con Expo Dev Client.
- **preview** — build interna distribuible (TestFlight / Internal
  testing).
- **production** — build para stores.

## Builds

```sh
# Local dev (requiere eas login local)
eas build --profile development --platform all

# Preview (TestFlight / Internal)
eas build --profile preview --platform all

# Producción
eas build --profile production --platform all
```

En el workflow `.github/workflows/deploy-mobile.yml` se puede
disparar manualmente desde Actions con `workflow_dispatch`.

## Submits

> **Confirmación humana obligatoria** (regla #1).

```sh
eas submit --profile production --platform ios
eas submit --profile production --platform android
```

## Secrets en EAS

Configurar en el dashboard de EAS, no en el repo:

- `API_URL_PROD`
- `API_URL_STAGING`
- Push keys, ASC keys, Google Play service account JSON, etc.

## Versionado

- `app.json[expo].version` para la versión semver.
- `app.json[expo].ios.buildNumber` y `app.json[expo].android.versionCode`
  se incrementan en cada submit (auto via EAS o manual, TODO
  decidir).

## Open questions

<!-- TODO -->
- Push notifications: ¿Expo Push Service o APNs/FCM directo?
- OTA updates: ¿usar EAS Update o evitar para mantener parity con
  el backend?
- TestFlight beta interna — ¿cuántos slots / quiénes?
