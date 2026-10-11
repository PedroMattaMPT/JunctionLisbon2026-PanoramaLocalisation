import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  // ui.tsx typeName() matches design-system components by function name (EquiScene, PerspScene, Timer ...);
  // minification would rename them and the built console would show the procedural scene, not the panorama.
  esbuild: { keepNames: true },
  resolve: { alias: { '@ds': fileURLToPath(new URL('../design_system/components/src', import.meta.url)) } },
  server: {
    fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
    proxy: { '/api': { target: process.env.AQUI_API_TARGET ?? 'http://127.0.0.1:8788' } },
  },
  test: { environment: 'node', setupFiles: ['tests/setup.ts'], pool: 'forks', poolOptions: { forks: { singleFork: true } } },
});
