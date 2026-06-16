// ESLint configuration for the web client (flat-config format).
//
// Lints all .ts/.tsx files with the recommended JavaScript + TypeScript rule
// sets, plus React-specific rules: react-hooks enforces the rules of hooks
// (correct dependency arrays, no conditional hooks), and react-refresh warns
// about patterns that break fast-refresh during development. The build output
// directories are ignored. `npm run lint` runs this with a zero-warnings policy.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  { ignores: ["dist", "dev-dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
);
