import { describe, expect, it } from 'vitest';
import {
  describeCoordinateLevel,
  displayOrNotProvided,
  getDisplayName,
  normalizeApiFacilities,
  normalizeApiFacility,
  NOT_PROVIDED_LABEL,
  UNNAMED_FACILITY_LABEL,
} from './normalizeFacility.js';

// 與後端 /api/facilities 回應相同的欄位格式
const apiItem = {
  id: 'taipei_hospital:1e0a1a22501e840d',
  name: '三軍總醫院北投分院附設民眾診療服務處',
  category: 'hospital',
  address: '臺北市北投區新民路６０號 中和街二五○號',
  phone: null,
  district: '北投區',
  lat: 25.1398048,
  lng: 121.5097013,
  coordinate_status: 'ok',
  coordinate_level: 1,
  coordinate_source: '臺北市政府衛生局「臺北市公私立醫療院所」提供之 WGS84 經緯度',
  source: '臺北市公私立醫療院所－醫院',
  source_id: 'taipei_hospital',
  source_url: 'https://data.gov.tw/dataset/121182',
  source_organization: '臺北市政府衛生局',
  source_download_url: 'https://data.taipei/api/dataset/ffdd5753/resource/04a3d195/download',
  source_synced_at: '2026-09-05T07:17:49.063713+00:00',
  external_id: '1e0a1a22501e840d',
  external_type: null,
  raw_updated_at: null,
  updated_at: '2026-09-05T07:17:49.063713+00:00',
};

describe('normalizeApiFacility', () => {
  it('把後端欄位轉成前端統一格式', () => {
    const facility = normalizeApiFacility(apiItem);
    expect(facility).toMatchObject({
      id: 'taipei_hospital:1e0a1a22501e840d',
      name: '三軍總醫院北投分院附設民眾診療服務處',
      category: 'hospital',
      address: '臺北市北投區新民路６０號 中和街二五○號',
      phone: '',
      district: '北投區',
      lat: 25.1398048,
      lng: 121.5097013,
      hasCoordinates: true,
      coordinateStatus: 'ok',
      coordinateLevel: 1,
      source: '臺北市公私立醫療院所－醫院',
      sourceId: 'taipei_hospital',
      sourceUrl: 'https://data.gov.tw/dataset/121182',
      sourceOrganization: '臺北市政府衛生局',
      externalId: '1e0a1a22501e840d',
      externalType: '',
      rawUpdatedAt: '',
    });
    expect(facility.sourceSyncedAt).toBeInstanceOf(Date);
    expect(facility.sourceSyncedAt.toISOString()).toBe('2026-09-05T07:17:49.063Z');
    expect(facility.updatedAt).toBeInstanceOf(Date);
    expect(facility.raw).toBe(apiItem);
  });

  it('缺座標的設施保留在清單但 hasCoordinates 為 false', () => {
    const facility = normalizeApiFacility({
      ...apiItem,
      id: 'moe_kindergarten:391X1E',
      category: 'kindergarten',
      lat: null,
      lng: null,
      coordinate_status: 'missing',
      coordinate_level: null,
      coordinate_source: null,
    });
    expect(facility.hasCoordinates).toBe(false);
    expect(facility.lat).toBeNull();
    expect(facility.lng).toBeNull();
    expect(facility.coordinateStatus).toBe('missing');
    expect(facility.coordinateLevel).toBeNull();
  });

  it('後端宣稱 ok 但座標無效時，前端仍不建立 marker（防呆，不推估）', () => {
    const facility = normalizeApiFacility({ ...apiItem, lat: 0, lng: 0 });
    expect(facility.hasCoordinates).toBe(false);
    expect(facility.lat).toBeNull();
    const swapped = normalizeApiFacility({ ...apiItem, lat: 121.5, lng: 25.0 });
    expect(swapped.hasCoordinates).toBe(false);
  });

  it('未知分類歸到 other；缺 id 回傳 null', () => {
    expect(normalizeApiFacility({ ...apiItem, category: 'spaceport' }).category).toBe('other');
    expect(normalizeApiFacility({ ...apiItem, id: '' })).toBeNull();
    expect(normalizeApiFacility(null)).toBeNull();
    expect(normalizeApiFacility('not an object')).toBeNull();
  });

  it('無效日期字串轉成 null', () => {
    const facility = normalizeApiFacility({ ...apiItem, source_synced_at: 'not-a-date', updated_at: null });
    expect(facility.sourceSyncedAt).toBeNull();
    expect(facility.updatedAt).toBeNull();
  });
});

describe('normalizeApiFacilities', () => {
  it('空資料回傳空陣列', () => {
    expect(normalizeApiFacilities([])).toEqual({ facilities: [], skipped: 0 });
    expect(normalizeApiFacilities(undefined)).toEqual({ facilities: [], skipped: 0 });
  });

  it('略過無效項目並計數', () => {
    const result = normalizeApiFacilities([apiItem, null, { ...apiItem, id: '' }]);
    expect(result.facilities).toHaveLength(1);
    expect(result.skipped).toBe(2);
  });
});

describe('顯示用輔助函式', () => {
  it('缺值顯示未提供 / 未命名機構', () => {
    expect(getDisplayName({ name: '' })).toBe(UNNAMED_FACILITY_LABEL);
    expect(getDisplayName({ name: '松山國小' })).toBe('松山國小');
    expect(displayOrNotProvided('')).toBe(NOT_PROVIDED_LABEL);
    expect(displayOrNotProvided('02-12345678')).toBe('02-12345678');
  });

  it('座標可信度說明', () => {
    expect(describeCoordinateLevel({ hasCoordinates: false })).toContain('無官方座標');
    expect(describeCoordinateLevel({ hasCoordinates: true, coordinateLevel: 1 })).toContain('Level 1');
    expect(describeCoordinateLevel({ hasCoordinates: true, coordinateLevel: 2 })).toContain('Level 2');
  });
});
