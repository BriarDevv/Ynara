// Aprende más: https://docs.expo.dev/guides/customizing-metro
const { getDefaultConfig } = require("expo/metro-config");
const { withNativeWind } = require("nativewind/metro");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// TODO: ajustar `watchFolders` para incluir packages/* del monorepo
// cuando necesitemos hot reload sobre core / ui.

module.exports = withNativeWind(config, { input: "./src/global.css" });
