import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // Relative base so the built bundle works when loaded from a file:// URL
  // inside a desktop shell (Tauri/Electron) as well as from a web server.
  base: './',
  build: { outDir: 'dist', sourcemap: true, target: 'es2022' },
  server: { port: 5173, strictPort: false },
});
