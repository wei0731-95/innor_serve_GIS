import { useCallback, useEffect, useState } from 'react';
import { loadFacilityData, summarizeSources } from '../services/backendApi.js';

/**
 * 資料流程：
 *   政府開放資料 → FastAPI（下載 / 解析 / 標準化 / SQLite）→ /api/facilities + /api/sources
 *   → 這個 hook → React state → 搜尋 / 篩選（純前端）→ 地圖
 *
 * 只在掛載時載入一次（以及使用者按「重新載入」時）。
 * 後端若正在同步政府資料（例如剛啟動），會每隔幾秒自動重新載入直到同步完成。
 *
 * 回傳介面沿用原本的概念：
 *   status, facilities, sourceResults, sourceErrors, error, loadedAt, reload
 * 並新增：sources, categories, pendingSources, categoriesWithSource, syncRunning
 */
const SYNC_POLL_INTERVAL_MS = 5000;

const initialState = {
  status: 'idle', // 'idle' | 'loading' | 'success' | 'error'
  facilities: [],
  sources: [],
  categories: [],
  sourceResults: [],
  sourceErrors: [],
  pendingSources: [],
  categoriesWithSource: null, // null = 尚未取得來源清單
  syncRunning: false,
  error: null,
  loadedAt: null,
};

export function useFacilities() {
  const [state, setState] = useState(initialState);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    let pollTimer = null;

    // 重新載入時保留畫面上既有資料，只切換狀態
    setState((prev) => ({
      ...prev,
      status: prev.facilities.length > 0 ? prev.status : 'loading',
      error: null,
    }));

    loadFacilityData({ signal })
      .then(({ facilities, sources, categories, syncStatus }) => {
        if (signal.aborted) return;
        const summary = summarizeSources(sources);
        const syncRunning = Boolean(syncStatus?.running);

        setState({
          status: 'success',
          facilities,
          sources,
          categories,
          sourceResults: summary.results,
          sourceErrors: summary.errors,
          pendingSources: summary.pending,
          categoriesWithSource: summary.categoriesWithSource,
          syncRunning,
          error: null,
          loadedAt: new Date(),
        });

        if (syncRunning) {
          pollTimer = setTimeout(() => setReloadToken((token) => token + 1), SYNC_POLL_INTERVAL_MS);
        }
      })
      .catch((error) => {
        if (signal.aborted || error?.name === 'AbortError') return;
        setState((prev) => ({ ...prev, status: 'error', syncRunning: false, error }));
      });

    return () => {
      controller.abort();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
