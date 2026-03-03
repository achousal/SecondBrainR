import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import yaml from "vite-plugin-yaml2";
import { resolve } from "path";

export default defineConfig({
  plugins: [yaml(), viteSingleFile()],
  resolve: {
    alias: {
      "@profiles": resolve(__dirname, "../profiles"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
  },
  test: {
    globals: true,
    environment: "node",
    include: ["src/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts", "src/config/**/*.ts"],
      exclude: ["src/__tests__/**", "src/main.ts"],
    },
  },
});
