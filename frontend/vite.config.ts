import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { TanStackRouterVite } from "@tanstack/router-plugin/vite"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    TanStackRouterVite({ routesDirectory: "./src/routes", generatedRouteTree: "./src/routeTree.gen.ts" }),
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
      },
      "/settings": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        // Bypass proxy for browser navigations (Accept: text/html) — serve SPA.
        // API fetch calls from client.ts always send Accept: application/json,
        // so those continue to proxy to the backend correctly.
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/cards": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/practice": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/decks": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/import": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/progress": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
        bypass(req) {
          const accept = req.headers.accept ?? ""
          if (accept.includes("text/html")) return "/index.html"
        },
      },
      "/services": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
      },
      "/models": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
      },
      "/openapi.json": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:7842",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../src/lingosips/static",
    emptyOutDir: true,
  },
})
