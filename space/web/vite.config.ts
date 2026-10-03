import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  base: "/",
  // fonts stay separate files: inlined into the CSS they would delay the first render
  build: { outDir: "../../site", emptyOutDir: false, assetsInlineLimit: (file) => (/\.woff2?$/.test(file) ? false : undefined) },
  server: { proxy: { "/api": "http://127.0.0.1:7860", "/badge": "http://127.0.0.1:7860" } },
});
