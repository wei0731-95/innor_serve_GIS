import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  buildUrl,
  getJson,
  loadFacilityData,
  resolveApiBaseUrl,
  summarizeSources,
} from './backendApi.js';

function jsonResponse(body, { status = 200 } = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

// 與後端 /api/sources 相同的欄位格式
const SOURCES = [
  {
    id: 'taipei_hospital', name: '臺北市公私立醫療院所－醫院', organization: '臺北市政府衛生局', category: 'hospital',
    kind: 'facility', enabled: true, last_status: 'success', last_error: null,
    last_success_at: '2026-09-05T07:17:49+00:00', last_synced_at: '2026-09-05T07:17:49+00:00',
    record_count: 37, skipped_count: 0, missing_coordinate_count: 0,
  },
  {
    id: 'mohw_ltc_abc', name: '長照ABC據點', organization: '衛生福利部', category: 'long_term_care',
    kind: 'facility', enabled: true, last_status: 'error', last_error: 'FetchError: 下載逾時（90 秒）',
    last_success_at: '2026-09-04T01:00:00+00:00', last_synced_at: '2026-09-05T07:17:54+00:00',
    record_count: 1014, skipped_count: 1732, missing_coordinate_count: 28,
  },
  {
    id: 'moe_kindergarten', name: '幼兒園名錄', organization: '教育部統計處', category: 'kindergarten',
    kind: 'facility', enabled: true, last_status: 'never', last_error: null,
    last_success_at: null, last_synced_at: null, record_count: 0, skipped_count: 0, missing_coordinate_count: 0,
  },
  {
    id: 'nlsc_school_blocks', name: '各級學校範圍圖_121分帶', organization: '內政部國土測繪中心', category: null,
    kind: 'geometry', enabled: true, last_status: 'success', last_error: null,
    last_success_at: '2026-09-05T07:17:48+00:00', last_synced_at: '2026-09-05T07:17:48+00:00',
    record_count: 289, skipped_count: 0, missing_coordinate_count: 0,
  },
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('resolveApiBaseUrl / buildUrl', () => {
  it('依環境變數決定後端位址', () => {
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: 'https://api.example.gov.tw/', DEV: false })).toBe('https://api.example.gov.tw');
    expect(resolveApiBaseUrl({ VITE_API_BASE_URL: '', DEV: true })).toBe('');
    expect(resolveApiBaseUrl({ DEV: true })).toBe('http://localhost:8000');
    expect(resolveApiBaseUrl({ DEV: false })).toBe('');
  });

  it('組合 query string，略過空值', () => {
    expect(buildUrl('/api/facilities', { category: 'hospital', search: '', district: undefined }, 'http://x')).toBe(
      'http://x/api/facilities?category=hospital',
    );
    expect(buildUrl('/api/health', {}, '')).toBe('/api/health');
  });
});

describe('getJson', () => {
  it('成功時回傳 JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ status: 'ok' })));
    await expect(getJson('/api/health')).resolves.toEqual({ status: 'ok' });
  });

  it('HTTP 錯誤 → ApiError(kind=http)，附帶後端 detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: '未知的分類「x」' }, { status: 400 })));
    const error = await getJson('/api/facilities', { params: { category: 'x' } }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe('http');
    expect(error.status).toBe(400);
    expect(error.message).toContain('HTTP 400');
    expect(error.message).toContain('未知的分類');
  });

  it('後端未啟動 / CORS 被擋（fetch reject）→ ApiError(kind=network)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const error = await getJson('/api/facilities').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe('network');
    expect(error.cause).toBeInstanceOf(TypeError);
  });

  it('回應不是 JSON → ApiError(kind=parse)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>oops</html>', { status: 200 })));
    const error = await getJson('/api/facilities').catch((e) => e);
    expect(error.kind).toBe('parse');
  });

  it('AbortError 原樣拋出（不包成 ApiError）', async () => {
    const abort = new DOMException('aborted', 'AbortError');
    vi.stubGlobal('fetch', vi.fn(async () => { throw abort; }));
    await expect(getJson('/api/facilities')).rejects.toBe(abort);
  });
});

describe('summarizeSources（部分來源失敗）', () => {
  it('分成成功 / 失敗 / 尚未同步，並忽略 geometry 來源', () => {
    const summary = summarizeSources(SOURCES);
    expect(summary.results.map((s) => s.sourceKey)).toEqual(['taipei_hospital']);
    expect(summary.errors.map((s) => s.sourceKey)).toEqual(['mohw_ltc_abc']);
    expect(summary.pending.map((s) => s.sourceKey)).toEqual(['moe_kindergarten']);
    expect([...summary.categoriesWithSource].sort()).toEqual(['hospital', 'kindergarten', 'long_term_care']);

    const failed = summary.errors[0];
    expect(failed.message).toContain('逾時');
    expect(failed.recordCount).toBe(1014); // DB 仍保留上次成功的資料
    expect(failed.lastSuccessAt).toBeInstanceOf(Date);
    expect(summary.results[0].lastSuccessAt.toISOString()).toBe('2026-09-05T07:17:49.000Z');
  });

  it('空資料', () => {
    const summary = summarizeSources([]);
    expect(summary.results).toEqual([]);
    expect(summary.errors).toEqual([]);
    expect(summary.categoriesWithSource.size).toBe(0);
    expect(summarizeSources(undefined).results).toEqual([]);
  });
});

describe('loadFacilityData', () => {
  it('同時載入設施、來源、分類、同步狀態並轉成前端格式', async () => {
    const facility = {
      id: 'taipei_hospital:abc', name: '測試醫院', category: 'hospital', address: '臺北市中正區福州街14號', phone: null,
      district: '中正區', lat: 25.0287, lng: 121.5187, coordinate_status: 'ok', coordinate_level: 1,
      coordinate_source: 'x', source: '臺北市公私立醫療院所－醫院', source_id: 'taipei_hospital',
      source_url: 'https://data.gov.tw/dataset/121182', source_organization: '臺北市政府衛生局',
      source_download_url: 'https://data.taipei/x', source_synced_at: '2026-09-05T07:17:49+00:00',
      external_id: 'abc', external_type: null, raw_updated_at: null, updated_at: '2026-09-05T07:17:49+00:00',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        if (url.includes('/api/facilities')) return jsonResponse({ count: 1, items: [facility] });
        if (url.includes('/api/sources')) return jsonResponse(SOURCES);
        if (url.includes('/api/categories')) return jsonResponse([{ category: 'hospital', label: '醫院', count: 1, with_coordinates: 1, missing_coordinates: 0, sources: [] }]);
        if (url.includes('/api/sync/status')) return jsonResponse({ running: false });
        return jsonResponse({ detail: 'not found' }, { status: 404 });
      }),
    );

    const data = await loadFacilityData();
    expect(data.facilities).toHaveLength(1);
    expect(data.facilities[0]).toMatchObject({ id: 'taipei_hospital:abc', hasCoordinates: true, sourceOrganization: '臺北市政府衛生局' });
    expect(data.sources).toHaveLength(4);
    expect(data.categories[0].label).toBe('醫院');
    expect(data.syncStatus.running).toBe(false);
  });

  it('任一請求失敗 → 整體拒絕（畫面顯示錯誤，不會自行補資料）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        if (url.includes('/api/sources')) return jsonResponse({ detail: 'db down' }, { status: 503 });
        return jsonResponse({ count: 0, items: [] });
      }),
    );
    await expect(loadFacilityData()).rejects.toBeInstanceOf(ApiError);
  });
});
