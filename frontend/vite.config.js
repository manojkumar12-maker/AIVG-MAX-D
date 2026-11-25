import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: process.env.BASE_PATH || '/',
  css: {
    postcss: { plugins: [] },
  },
  server: {
    host: true,
    allowedHosts: true,
    port: 3000,
    strictPort: true,
    // Dev convenience only: lets the preview browser reach a local adapter at
    // http://127.0.0.1:3000/api/* (the adapter would otherwise be reached
    // through its public tunnel URL). No effect on production builds.
    proxy: {
      '/api': {
        target: process.env.OGAI_DEV_PROXY || 'http://127.0.0.1:8202',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
      '/ws/jobs': { target: process.env.OGAI_DEV_PROXY || 'http://127.0.0.1:8189', ws: true, changeOrigin: true },
    },
  },
  preview: {
    host: true,
    allowedHosts: true,
    port: 3000,
  },
})
