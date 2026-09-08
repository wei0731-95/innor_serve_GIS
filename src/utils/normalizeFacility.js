import { DEFAULT_CATEGORY, isKnownCategory } from '../config/categories.js';
import { isValidLatLng, toCoordinate } from './geo.js';

/**
 * 前端統一資料格式（由後端 /api/facilities 的每一筆轉換而來）：
 * {
 *   id, name, category, address, phone, district,
 *   lat, lng,            // 只有 hasCoordinates 為 true 時有值，否則 null
 *   hasCoordinates,      // true 才會建立 marker
 *   coordinateStatus, coordinateLevel, coordinateSource,
 *   source, sourceId, sourceUrl, sourceOrganization, sourceDownloadUrl, sourceSyncedAt,
 *   externalId, externalType, rawUpdatedAt, updatedAt,
 *   raw                  // 後端回傳的原始 item，保留給除錯
 * }
 *
 * 政府資料的解析、清洗、去重、座標驗證都在後端完成（backend/app/services/normalizer.py）；
 * 這裡只做欄位命名轉換與最後一道座標防呆，絕不推估座標。
 */

export const UNNAMED_FACILITY_LABEL = '未命名機構';
export const NOT_PROVIDED_LABEL = '未提供';

function text(value) {
  if (value === undefined || value === null) return '';
  return String(value).trim();
}

function toDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * 後端 API 的一筆設施 → 前端統一格式。id 缺失時回傳 null。
 */
export function normalizeApiFacility(item) {
  if (!item || typeof item !== 'object') return null;
  const id = text(item.id);
  if (!id) return null;

  const lat = toCoordinate(item.lat);
  const lng = toCoordinate(item.lng);
  const hasCoordinates = item.coordinate_status === 'ok' && isValidLatLng(lat, lng);

  return {
    id,
    name: text(item.name),
    category: isKnownCategory(item.category) ? item.category : DEFAULT_CATEGORY,
    address: text(item.address),
    phone: text(item.phone),
    district: text(item.district),
    lat: hasCoordinates ? lat : null,
    lng: hasCoordinates ? lng : null,
    hasCoordinates,
    coordinateStatus: hasCoordinates ? 'ok' : 'missing',
    coordinateLevel: hasCoordinates ? item.coordinate_level ?? null : null,
    coordinateSource: text(item.coordinate_source),
    source: text(item.source),
    sourceId: text(item.source_id),
    sourceUrl: text(item.source_url),
    sourceOrganization: text(item.source_organization),
    sourceDownloadUrl: text(item.source_download_url),
    sourceSyncedAt: toDate(item.source_synced_at),
    externalId: text(item.external_id),
    externalType: text(item.external_type),
    rawUpdatedAt: text(item.raw_updated_at),
    updatedAt: toDate(item.updated_at),
    raw: item,
  };
}

/**
 * 批次轉換。回傳有效資料與被略過（缺 id）的筆數。
 * @returns {{ facilities: object[], skipped: number }}
 */
export function normalizeApiFacilities(items) {
  const facilities = [];
  let skipped = 0;
  (Array.isArray(items) ? items : []).forEach((item) => {
    const facility = normalizeApiFacility(item);
    if (facility) {
      facilities.push(facility);
    } else {
      skipped += 1;
    }
  });
  return { facilities, skipped };
}

/** 顯示用名稱：空名稱顯示「未命名機構」 */
export function getDisplayName(facility) {
  return facility?.name ? facility.name : UNNAMED_FACILITY_LABEL;
}

/** 顯示用欄位：空值顯示「未提供」 */
export function displayOrNotProvided(value) {
  return value ? value : NOT_PROVIDED_LABEL;
}

/** 座標可信度說明（對應後端 coordinate_level） */
export function describeCoordinateLevel(facility) {
  if (!facility?.hasCoordinates) return '無官方座標，不顯示於地圖';
  switch (facility.coordinateLevel) {
    case 1:
      return '官方資料直接提供的 WGS84 座標（Level 1）';
    case 2:
      return '由另一份官方空間資料對應取得（Level 2）';
    case 3:
      return '官方定位服務轉換（Level 3）';
    default:
      return '官方座標';
  }
}
