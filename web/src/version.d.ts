/**
 * Ambient declaration for the build-time version global.
 *
 * `__APP_VERSION__` is replaced at build time by Vite's `define` (see
 * vite.config.ts) with a string like `0.1.42+ab8ceaa`: major.minor from
 * package.json, the git commit count as an auto-incrementing patch number, and
 * the short commit hash. It is a compile-time constant, not a runtime variable.
 */
declare const __APP_VERSION__: string;
