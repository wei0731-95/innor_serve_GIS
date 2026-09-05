import { DEFAULT_CATEGORY, isKnownCategory } from '../config/categories.js';
import { isValidLatLng, toCoordinate } from './geo.js';

/**
 * 統一資料格式（所有資料來源都要轉成這個形狀）：
 * {
 *   id: string,
 *   name: string,        // 原始名稱，可能為空字串；顯示時用 getDisplayName()
 *   category: string,    // config/categories.js 的 key
 *   address: string,     // 可能為空字串；顯示時用 displayOrNotProvided()
 *   phone: string,       // 可能為空字串；顯示時用 displayOrNotProvided()
 *   lat: number,
 *   lng: number,
 *   source: string,
 *   raw: object          // 原始 CSV row，保留給除錯與未來擴充
 * }
 */

export const UNNAMED_FACILITY_LABEL = '未命名機構';
export const NOT_PROVIDED_LABEL = '未提供';

/** 臺北市資料大平台常見欄位對應（CSV 欄位 → 統一格式欄位） */
export const DEFAULT_FIELD_MAP = {
  id: '_id',
  name: '機構名稱',
  address: '地址',
  phone: '電話',
  lng: '經度',
  lat: '緯度',
};

function pick(row, key) {
  if (!key) return '';
  const value = row[key];
  if (value === undefined || value === null) return '';
  return String(value).trim();
}

/**
 * 把一筆原始 row 轉成統一格式。
 * 座標無效（空白、非數字、超出範圍）時回傳 null，呼叫端不應為它建立 marker。
 *
 * @param {object} row Papa Parse 解析後的一列
 * @param {object} options
 * @param {object} [options.fieldMap]  欄位對應
 * @param {string} [options.category] 分類 key
 * @param {string} [options.source]   資料提供單位
 * @param {string} [options.idPrefix] id 前綴（避免不同來源 id 撞名）
 * @param {number} [options.index]    在來源中的序號，無 _id 時作為備援 id
 * @returns {object|null}
 */
export function normalizeFacility(row, options = {}) {
  const {
    fieldMap = DEFAULT_FIELD_MAP,
    category = DEFAULT_CATEGORY,
    source = '',
    idPrefix = '',
    index = 0,
  } = options;

  if (!row || typeof row !== 'object') return null;

  const lat = toCoordinate(pick(row, fieldMap.lat));
  const lng = toCoordinate(pick(row, fieldMap.lng));
  if (!isValidLatLng(lat, lng)) return null;

  const rawId = pick(row, fieldMap.id);
  const id = `${idPrefix || category}-${rawId || index + 1}`;

  return {
    id,
    name: pick(row, fieldMap.name),
    category: isKnownCategory(category) ? category : DEFAULT_CATEGORY,
    address: pick(row, fieldMap.address),
    phone: pick(row, fieldMap.phone),
    lat,
    lng,
    source,
    raw: row,
  };
}

/**
 * 批次轉換。回傳有效資料與被略過（座標無效）的筆數。
 * @returns {{ facilities: object[], skipped: number }}
 */
export function normalizeFacilities(rows, options = {}) {
  const facilities = [];
  let skipped = 0;

  rows.forEach((row, index) => {
    const facility = normalizeFacility(row, { ...options, index });
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
