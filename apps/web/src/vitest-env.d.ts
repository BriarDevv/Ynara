// Carga el module augmentation de jest-dom sobre los matchers de Vitest,
// para que `toBeInTheDocument`, `toHaveClass`, etc. estén tipados en los
// tests. Solo afecta tipos (no emite). Equivalente al import del setup,
// pero visible para `tsc` (el setup vive fuera de `src/`).
import "@testing-library/jest-dom/vitest";
