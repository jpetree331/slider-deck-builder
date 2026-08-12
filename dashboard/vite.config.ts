import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev on 5179 (5173/5174/5178 are claimed by other projects — see RUNBOOK.md).
// All API traffic proxies to the Lantern service on 8020.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    proxy: { '/api': 'http://localhost:8020' },
  },
})
