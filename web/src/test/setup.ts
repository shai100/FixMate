/**
 * Global test setup, loaded before every test file (configured in vite.config.ts).
 *
 * Importing jest-dom registers extra DOM matchers (e.g. `toBeInTheDocument()`,
 * `toHaveTextContent()`) on Vitest's `expect`, so component tests can assert
 * against rendered DOM in a readable way.
 */
import "@testing-library/jest-dom/vitest";
