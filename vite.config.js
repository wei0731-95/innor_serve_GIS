import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * 臺北市資料大平台的 CSV 下載端點（data.taipei）沒有回傳 Access-Control-Allow-Origin，
 * 瀏覽器直接 fetch 會被 CORS 擋下（實測 2026-09）。
 *
 * 開發模式（npm run dev）由 Vite dev server 把 `/taipei-proxy/...` 轉送到
 * `https://data.taipei/...`。這只是「同一個 URL 的轉送」，不改變資料來源、不引入後端。
 *
 * 是否使用 proxy 由 .env.development 的 VITE_TAIPEI_PROXY_PREFIX 控制，
 * 正式 build 沒有該變數時會直接呼叫原始 URL（詳見 README「CORS 注意事項」）。
 */
const TAIPEI_PROXY_PREFIX = '/taipei-proxy';
const TAIPEI_ORIGIN = 'https://data.taipei';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      [TAIPEI_PROXY_PREFIX]: {
        target: TAIPEI_ORIGIN,
        changeOrigin: true,
        rewrite: (path) => path.replace(new RegExp(`^${TAIPEI_PROXY_PREFIX}`), ''),
      },
    },
  },
});
