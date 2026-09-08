import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * 前端只呼叫自己的 FastAPI 後端（見 src/services/backendApi.js）。
 * 後端位址由 VITE_API_BASE_URL 決定（開發預設 http://localhost:8000），CORS 由 FastAPI 處理，
 * 所以這裡不再需要任何 dev proxy，也不再直接連到政府主機。
 *
 * test 區塊給 Vitest 使用（npm test）。
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.js'],
  },
});
