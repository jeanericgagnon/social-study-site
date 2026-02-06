// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://www.thesocial.study',
  vite: {
    plugins: [tailwindcss()],
    server: {
      hmr: {
        // Prevent noisy Vite overlay errors on flaky connections (mobile/LAN)
        overlay: false,
      },
    },
  },

  integrations: [sitemap()]
});