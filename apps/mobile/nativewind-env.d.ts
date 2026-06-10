/// <reference types="nativewind/types" />

// Habilita la prop `className` en los componentes de React Native (NativeWind v4).
// Sin esto, `tsc --noEmit` falla con "Property 'className' does not exist on type
// ViewProps/TextProps" en todo componente con className (issue #176). El d.ts vive
// en la raiz del app (no en src/) para cubrir todo el arbol via el include de tsconfig.
