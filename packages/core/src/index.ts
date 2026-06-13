// Barrel raíz de @ynara/core: lógica de app platform-agnostic compartida
// entre web y mobile (ADR-012). Se puebla a medida que se extraen módulos
// desde apps/web (query keys, cliente API, stores, hooks de data).
//
// Regla del package (ADR-012): core NO importa nada de plataforma
// (next, react-dom, expo, expo-*, react-native). Lo que difiere por
// plataforma se inyecta desde cada app.
export {};
