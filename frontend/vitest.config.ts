import path from "path"
import { defineConfig } from "vitest/config"

/**
 * Vitest configuration — kept separate from vite.config.ts so that
 * `tsc -b && vite build` does not see the `test` key (which is not part
 * of Vite's own UserConfig type and causes a TS2769 error in TS 6).
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    exclude: ["node_modules", "e2e/**"],
    passWithNoTests: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      exclude: ["e2e/**", "node_modules/**", "src/routeTree.gen.ts"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
