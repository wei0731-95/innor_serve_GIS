import { decodeCsvBuffer, parseCsv } from './csvParser.js';
import { normalizeFacilities } from '../utils/normalizeFacility.js';

export const TAIPEI_OPEN_DATA_SOURCE_NAME = '臺北市資料大平台';

const TAIPEI_ORIGIN = 'https://data.taipei';

/**
 * 資料來源設定（集中管理，不要把 URL 寫在 component 裡）
 *
 * 每個資料來源欄位：
 * - key       : 唯一識別，也用來當 facility id 前綴
 * - name      : 資料集名稱（UI 顯示）
 * - category  : 對應 config/categories.js 的分類 key
 * - source    : 資料提供單位（寫入 facility.source）
 * - url       : 原始下載 URL（不要改成 proxy 路徑，proxy 由 resolveRequestUrl 處理）
 * - format    : 目前只支援 'csv'
 * - encoding  : 資料實際編碼提示（實測 data.taipei 這份 CSV 為 Big5）
 * - fieldMap  : CSV 欄位 → 統一格式欄位的對應（見 utils/normalizeFacility.js）
 * - enabled   : false 時不會載入
 *
 * 未來新增資料集（診所、長照、藥局、學校、幼兒園……）只要在此新增一個項目。
 */
export const DATA_SOURCES = {
  hospital: {
    key: 'hospital',
    name: '臺北市公私立醫院',
    category: 'hospital',
    source: TAIPEI_OPEN_DATA_SOURCE_NAME,
    url: 'https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=eab7fdff-574d-427b-9324-c00833d695c8',
    format: 'csv',
    encoding: 'big5',
    fieldMap: {
      id: '_id',
      name: '機構名稱',
      address: '地址',
      phone: '電話',
      lng: '經度',
      lat: '緯度',
    },
    enabled: true,
  },

  // 擴充範例（尚未有實際資料集，請勿填入假 URL 啟用）：
  // clinic: {
  //   key: 'clinic',
  //   name: '臺北市診所',
  //   category: 'clinic',
  //   source: TAIPEI_OPEN_DATA_SOURCE_NAME,
  //   url: 'https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=<rid>',
  //   format: 'csv',
  //   encoding: 'big5',
  //   fieldMap: { id: '_id', name: '機構名稱', address: '地址', phone: '電話', lng: '經度', lat: '緯度' },
  //   enabled: true,
  // },
};

/**
 * 資料來源錯誤。kind 用來讓 UI 判斷要顯示哪種提示：
 * - 'network' : fetch 本身失敗（無法連線、CORS、離線）
 * - 'http'    : 伺服器回應非 2xx
 * - 'format'  : 不支援的格式 / 回傳不是 CSV
 * - 'parse'   : CSV 解析失敗或欄位不符
 */
export class DataSourceError extends Error {
  constructor(message, { sourceKey, kind, cause } = {}) {
    super(message);
    this.name = 'DataSourceError';
    this.sourceKey = sourceKey;
    this.kind = kind;
    this.cause = cause;
  }
}

const PROXY_PREFIX = import.meta.env.VITE_TAIPEI_PROXY_PREFIX || '';

/**
 * 把原始 URL 換成實際要請求的 URL。
 * 只有設定了 VITE_TAIPEI_PROXY_PREFIX（預設僅開發模式）且 URL 屬於 data.taipei 時，
 * 才會改走 Vite dev proxy；其餘情況原封不動回傳。
 */
export function resolveRequestUrl(url) {
  if (PROXY_PREFIX && url.startsWith(TAIPEI_ORIGIN)) {
    return PROXY_PREFIX + url.slice(TAIPEI_ORIGIN.length);
  }
  return url;
}

export function getEnabledDataSources() {
  return Object.values(DATA_SOURCES).filter((source) => source.enabled !== false);
}

/** 目前有設定資料來源的分類集合（UI 用來標示「尚無資料來源」） */
export function getCategoriesWithDataSource() {
  return new Set(getEnabledDataSources().map((source) => source.category));
}

/**
 * 載入單一資料來源並轉成統一格式。
 *
 * @returns {Promise<{
 *   sourceKey: string, sourceName: string, facilities: object[],
 *   totalRows: number, skipped: number, fields: string[], fetchedAt: string
 * }>}
 */
export async function fetchDataSource(source, { signal } = {}) {
  const requestUrl = resolveRequestUrl(source.url);

  let response;
  try {
    response = await fetch(requestUrl, { signal });
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new DataSourceError(`無法連線至資料來源（${source.name}）：${error?.message ?? error}`, {
      sourceKey: source.key,
      kind: 'network',
      cause: error,
    });
  }

  if (!response.ok) {
    throw new DataSourceError(`資料來源回應錯誤：HTTP ${response.status}（${source.name}）`, {
      sourceKey: source.key,
      kind: 'http',
    });
  }

  if (source.format !== 'csv') {
    throw new DataSourceError(`尚不支援的資料格式：${source.format}（${source.name}）`, {
      sourceKey: source.key,
      kind: 'format',
    });
  }

  const contentType = response.headers.get('content-type') || '';
  if (/text\/html/i.test(contentType)) {
    throw new DataSourceError(`資料來源回傳的是 HTML 而不是 CSV（${source.name}），請確認 URL 或 proxy 設定`, {
      sourceKey: source.key,
      kind: 'format',
    });
  }

  const buffer = await response.arrayBuffer();
  const text = decodeCsvBuffer(buffer, { contentType, fallbackEncoding: source.encoding });

  let parsed;
  try {
    const { fieldMap } = source;
    parsed = parseCsv(text, { requiredFields: [fieldMap.name, fieldMap.lat, fieldMap.lng] });
  } catch (error) {
    throw new DataSourceError(`CSV 解析失敗（${source.name}）：${error.message}`, {
      sourceKey: source.key,
      kind: 'parse',
      cause: error,
    });
  }

  const { facilities, skipped } = normalizeFacilities(parsed.rows, {
    fieldMap: source.fieldMap,
    category: source.category,
    source: source.source,
    idPrefix: source.key,
  });

  return {
    sourceKey: source.key,
    sourceName: source.name,
    facilities,
    totalRows: parsed.rows.length,
    skipped,
    fields: parsed.fields,
    fetchedAt: new Date().toISOString(),
  };
}

/**
 * 載入所有啟用的資料來源。
 * 個別來源失敗不會讓整體失敗；全部失敗時 results 為空、errors 有內容，由呼叫端決定如何顯示。
 *
 * @returns {Promise<{ facilities: object[], results: object[], errors: Error[] }>}
 */
export async function fetchAllFacilities({ signal } = {}) {
  const sources = getEnabledDataSources();
  if (sources.length === 0) {
    throw new DataSourceError('沒有啟用任何資料來源（請檢查 services/taipeiApi.js 的 DATA_SOURCES）', {
      kind: 'format',
    });
  }

  const settled = await Promise.allSettled(sources.map((source) => fetchDataSource(source, { signal })));

  const results = [];
  const errors = [];
  settled.forEach((outcome) => {
    if (outcome.status === 'fulfilled') {
      results.push(outcome.value);
    } else {
      errors.push(outcome.reason);
    }
  });

  return {
    facilities: results.flatMap((result) => result.facilities),
    results,
    errors,
  };
}
