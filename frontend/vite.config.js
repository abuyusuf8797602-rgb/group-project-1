import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Single-origin setup: the browser talks only to the Vite dev server on port
// 3000, and Vite forwards /api/* to the FastAPI service inside the compose
// network. No CORS needed.
//
// `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` (set by the platform, passed through
// compose) is appended to `server.allowedHosts` by Vite >= 6.1 so the preview's
// proxied hostname is accepted.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
})
