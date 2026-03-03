import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import remarkWikiLinks from "./src/plugins/remark-wiki-links.mjs";

export default defineConfig({
  site: "https://achousal.github.io",
  base: "/EngramR/",
  output: "static",
  markdown: {
    remarkPlugins: [remarkWikiLinks],
    shikiConfig: {
      theme: "github-dark-dimmed",
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
