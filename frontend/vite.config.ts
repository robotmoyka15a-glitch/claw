import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const API = process.env.CLAW_API ?? 'http://127.0.0.1:8765';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/ws': { target: API.replace('http', 'ws'), ws: true, changeOrigin: true },
    },
  },
  build: {
    // Split the two heaviest deps (Pixi.js for the isometric room, xterm.js
    // for the terminal) out of the main bundle so the initial load is lighter.
    rollupOptions: {
      output: {
        manualChunks: {
          pixi: ['pixi.js'],
          xterm: ['@xterm/xterm', '@xterm/addon-fit'],
          charts: ['recharts'],
        },
      },
    },
    chunkSizeWarningLimit: 900,
  },
});
