import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';

export default defineConfig(({ mode }) => ({
  // mode https (npm run dev:https): a self-signed certificate, so a phone on the same Wi-Fi may use geolocation
  // (browsers allow it only on HTTPS or localhost).
  plugins: [react(), ...(mode === 'https' ? [basicSsl()] : [])],
  // /api goes to the FastAPI backend (no CORS needed).
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: false },
  server: { host: true, port: 5173, proxy: { '/api': 'http://localhost:8000' } },
}));
