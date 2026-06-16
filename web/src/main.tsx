/**
 * Application entry point.
 *
 * The single file the browser loads first (referenced by index.html). It finds
 * the empty <div id="root"> in the HTML and mounts the React <App> into it.
 * <StrictMode> is a dev-only wrapper that surfaces potential bugs (it
 * double-invokes some functions in development to catch side effects); it has no
 * effect in production builds.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
