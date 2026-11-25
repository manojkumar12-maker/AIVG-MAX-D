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
  },
  preview: {
    host: true,
    allowedHosts: true,
    port: 3000,
  },
})
