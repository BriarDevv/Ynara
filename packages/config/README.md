# @ynara/config

Configuraciones compartidas del monorepo: `tsconfig.base.json`,
`biome.json`, `eslint.config.mjs`.

Los apps y packages extienden de acá vía `"extends"` en sus
respectivos tsconfigs.

## Archivos

- `tsconfig.base.json` — base estricta de TypeScript.
- `biome.json` — config extendida de Biome para compartir entre
  paquetes (el root también tiene su `biome.json` con paths
  específicos del monorepo).
- `eslint.config.mjs` — solo para entornos que aún requieran ESLint
  específicamente (Expo, por ejemplo). Biome cubre la mayoría.

## Convención

Cambios acá afectan a todo el repo. PR con review obligatoria.
