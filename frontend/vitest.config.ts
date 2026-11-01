import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const root = path.resolve(process.cwd());
const alias = {
  '@': root,
}

export default defineConfig({
  plugins: [react()],
  resolve: { alias },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    environmentOptions: { jsdom: { url: 'http://localhost/' } },
    exclude: ['**/node_modules/**', '**/e2e/**', '**/dist/**'],
  },
});
