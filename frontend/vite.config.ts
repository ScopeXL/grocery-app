/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The single source of truth for the version is the repo's VERSION file (docs/adr/0019).
const version = readFileSync(new URL("../VERSION", import.meta.url), "utf8").trim();

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "prompt",
      injectRegister: false,
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg,webmanifest}"],
      },
      devOptions: { enabled: false },
      manifest: {
        name: "Dinner Bell",
        short_name: "Dinner Bell",
        description: "Plan dinners and shop the list together.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#f3f4f1",
        theme_color: "#f3f4f1",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // In development, set APP_BASE_URL=http://localhost:5173 for the backend (CSRF origin check).
      "/api": { target: "http://127.0.0.1:8080", changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // tokens.test.ts reads tokens.css?raw; Vitest otherwise replaces CSS with an empty module.
    css: { include: [/tokens\.css/] },
  },
});
