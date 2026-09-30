import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: process.env.SITE_URL ?? "https://companymgmt.app",
  integrations: [sitemap()],
  vite: { plugins: [tailwindcss()] },
});
