import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

/**
 * Setup global de los tests de apps/admin.
 *
 * - jest-dom agrega los matchers (`toBeInTheDocument`, `toBeDisabled`, …).
 * - jsdom no implementa `window.matchMedia`: lo mockeamos (lo lee el helper de
 *   view transitions y cualquier código que consulte prefers-reduced-motion).
 *   Default: no-match.
 * - Entre tests limpiamos el árbol de RTL y reseteamos las clases del <html>,
 *   que los stores de tema/a11y mutan vía applyThemeClass/applyA11yClasses.
 */

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(), // deprecado, por compat
      removeListener: vi.fn(), // deprecado, por compat
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  document.documentElement.className = "";
});

afterEach(() => {
  cleanup();
  document.documentElement.className = "";
});
