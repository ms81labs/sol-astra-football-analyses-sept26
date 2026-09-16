import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiTarget = process.env.PILOT_API_TARGET || 'http://localhost:8000'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      },
      '/ws': {
        target: apiTarget.replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    target: 'es2022'
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/testSetup.ts'],
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'es2022'
    }
  }
})
