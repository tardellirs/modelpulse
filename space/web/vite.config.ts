import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  base: "./",
  build: { outDir: "../../site", emptyOutDir: false },
  server: { proxy: { "/api": "http://127.0.0.1:7860", "/badge": "http://127.0.0.1:7860" } },
});
