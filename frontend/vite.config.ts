import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // /api goes to the FastAPI backend (no CORS needed).
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: false },
  server: { host: true, port: 5173, proxy: { '/api': 'http://localhost:8000' } },
});
