import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev on 5179 (5173/5174/5178 are claimed by other projects — see RUNBOOK.md).
// All API traffic proxies to the Lantern service on 8021 (8020 is held by
// Docker Desktop on this machine — see RUNBOOK.md).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    proxy: { '/api': 'http://localhost:8021' },
  },
})
