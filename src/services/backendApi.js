/**
 * 後端 API client：前端唯一的資料來源。
 *
 *   React → FastAPI（backend/）→ SQLite → 政府開放資料
 *
 * 前端不再直接呼叫任何政府 API，也不知道 CSV / Big5 / 政府欄位名稱 / 去重規則，
 * 那些全部是後端的責任（見 backend/app/services/）。
 */

import { normalizeApiFacility } from '../utils/normalizeFacility.js';

const DEV_DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * API 位址：
 * - VITE_API_BASE_URL 有值 → 使用該值（正式環境用 build 時的環境變數指定）
 * - VITE_API_BASE_URL 明確設成空字串 → 同源相對路徑（由反向代理把 /api 轉到 FastAPI）
 * - 未設定：開發模式預設 http://localhost:8000，正式 build 預設同源
 */
export function resolveApiBaseUrl(env = import.meta.env) {
  const configured = env.VITE_API_BASE_URL;
  if (typeof configured === 'string') {
    return configured.replace(/\/+$/, '');
  }
  return env.DEV ? DEV_DEFAULT_BASE_URL : '';
}

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * kind：
 * - 'network'：fetch 直接失敗（後端未啟動、CORS 未允許、離線）
 * - 'http'   ：後端回應非 2xx
 * - 'parse'  ：回應不是 JSON
 */
export class ApiError extends Error {
  constructor(message, { kind, status = null, url = null, cause = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.url = url;
    this.cause = cause;
  }
}

export function buildUrl(path, params = {}, baseUrl = API_BASE_URL) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  return `${baseUrl}${path}${queryString ? `?${queryString}` : ''}`;
}

export async function getJson(path, { signal, params, method = 'GET' } = {}) {
  const url = buildUrl(path, params);

  let response;
  try {
    response = await fetch(url, { method, signal, headers: { Accept: 'application/json' } });
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new ApiError(`無法連線至後端 API（${url}）`, { kind: 'network', url, cause: error });
  }

  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = `：${typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)}`;
      }
    } catch {
      // 非 JSON 錯誤內容就不附帶細節
    }
    throw new ApiError(`後端 API 回應錯誤 HTTP ${response.status}${detail}`, {
      kind: 'http',
      status: response.status,
      url,
    });
  }

  try {
    return await response.json();
  } catch (error) {
    throw new ApiError(`後端 API 回應不是有效的 JSON（${url}）`, { kind: 'parse', url, cause: error });
  }
}

export const fetchHealth = (options) => getJson('/api/health', options);
export const fetchFacilities = (options) => getJson('/api/facilities', options);
export const fetchFacility = (id, options) => getJson(`/api/facilities/${encodeURIComponent(id)}`, options);
export const fetchCategories = (options) => getJson('/api/categories', options);
export const fetchSources = (options) => getJson('/api/sources', options);
export const fetchSyncStatus = (options) => getJson('/api/sync/status', options);
export const triggerSync = (options) => getJson('/api/sync', { ...options, method: 'POST' });

export function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * 把 /api/sources 整理成 UI 需要的形狀（只看啟用的 facility 類型來源）：
 * - results ：最近一次同步成功的來源
 * - errors  ：最近一次同步失敗的來源（recordCount > 0 表示 DB 仍保留上次成功的資料）
 * - pending ：尚未同步或正在同步
 * - categoriesWithSource：有資料來源的分類集合
 */
export function summarizeSources(sources) {
  const facilitySources = (Array.isArray(sources) ? sources : []).filter(
    (source) => source.kind === 'facility' && source.enabled !== false,
  );

  const describe = (source) => ({
    sourceKey: source.id,
    sourceName: source.name,
    organization: source.organization,
    category: source.category,
    status: source.last_status,
    recordCount: source.record_count ?? 0,
    skipped: source.skipped_count ?? 0,
    missingCoordinates: source.missing_coordinate_count ?? 0,
    lastSuccessAt: parseDate(source.last_success_at),
    lastSyncedAt: parseDate(source.last_synced_at),
    message: source.last_error || null,
  });

  return {
    results: facilitySources.filter((s) => s.last_status === 'success').map(describe),
    errors: facilitySources
      .filter((s) => s.last_status === 'error')
      .map((s) => ({ ...describe(s), message: s.last_error || '同步失敗（沒有錯誤訊息）' })),
    pending: facilitySources.filter((s) => s.last_status === 'never' || s.last_status === 'running').map(describe),
    categoriesWithSource: new Set(facilitySources.map((s) => s.category).filter(Boolean)),
  };
}

/**
 * 一次載入地圖需要的所有資料。任何一個請求失敗都會拋出 ApiError（由 useFacilities 顯示錯誤）。
 */
export async function loadFacilityData({ signal } = {}) {
  const [facilityList, sources, categories, syncStatus] = await Promise.all([
    fetchFacilities({ signal }),
    fetchSources({ signal }),
    fetchCategories({ signal }),
    fetchSyncStatus({ signal }),
  ]);

  const items = Array.isArray(facilityList?.items) ? facilityList.items : [];
  const facilities = items.map(normalizeApiFacility).filter(Boolean);

  return { facilities, sources, categories, syncStatus };
}
