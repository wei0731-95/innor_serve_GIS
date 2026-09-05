import { useCallback, useEffect, useState } from 'react';
import { fetchAllFacilities } from '../services/taipeiApi.js';

/**
 * 資料流程：
 *   Taipei Open Data → fetch CSV → Papa Parse → normalizeFacility() → 這個 hook → React state
 *
 * API 只在掛載時載入一次（以及使用者按「重新載入」時）。
 * 搜尋、分類切換都是前端 filter，不會再打 API。
 *
 * status: 'idle' | 'loading' | 'success' | 'error'
 */
const initialState = {
  status: 'idle',
  facilities: [],
  sourceResults: [],
  sourceErrors: [],
  error: null,
  loadedAt: null,
};

export function useFacilities() {
  const [state, setState] = useState(initialState);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    fetchAllFacilities({ signal })
      .then(({ facilities, results, errors }) => {
        if (signal.aborted) return;

        if (results.length === 0) {
          setState({
            ...initialState,
            status: 'error',
            error: errors[0] ?? new Error('沒有任何資料來源成功載入'),
            sourceErrors: errors,
          });
          return;
        }

        setState({
          status: 'success',
          facilities,
          sourceResults: results,
          sourceErrors: errors,
          error: null,
          loadedAt: new Date(),
        });
      })
      .catch((error) => {
        if (signal.aborted || error?.name === 'AbortError') return;
        setState({ ...initialState, status: 'error', error });
      });

    return () => controller.abort();
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
