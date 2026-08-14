import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
  },
  build: {
    // Sourcemaps make the deployed bundle debuggable and cost nothing on a CDN.
    sourcemap: true,
  },
})
