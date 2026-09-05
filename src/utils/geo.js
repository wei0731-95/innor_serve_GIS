/**
 * GIS 基礎工具
 * - 座標驗證
 * - Haversine 距離（公尺）
 * 未來 Coverage / Gap Analysis 都會用到這裡的函式。
 */

/** 臺北市政府（信義區市府路 1 號）附近，作為地圖預設中心 */
export const TAIPEI_CITY_HALL = { lat: 25.0375, lng: 121.5637 };

/** 地球平均半徑（公尺） */
export const EARTH_RADIUS_M = 6371008.8;

const NUMERIC_PATTERN = /^[-+]?\d+(\.\d+)?$/;

/**
 * 把 CSV 字串轉成座標數值。
 * 只接受純數字字串；空字串、"N/A"、"25.03abc" 這類都回傳 NaN，
 * 不使用 parseFloat 以免部分解析成假座標。
 */
export function toCoordinate(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : NaN;
  if (typeof value !== 'string') return NaN;
  const trimmed = value.trim();
  if (trimmed === '' || !NUMERIC_PATTERN.test(trimmed)) return NaN;
  return Number(trimmed);
}

/**
 * 座標是否有效：必須是有限數字、落在合法範圍，且不是 (0, 0)。
 */
export function isValidLatLng(lat, lng) {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180 &&
    !(lat === 0 && lng === 0)
  );
}

function toRadians(degrees) {
  return (degrees * Math.PI) / 180;
}

/**
 * Haversine 距離（公尺）
 * @param {{lat:number, lng:number}} a
 * @param {{lat:number, lng:number}} b
 */
export function haversineDistance(a, b) {
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);

  const h =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) * Math.sin(dLng / 2);

  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** 點 b 是否在點 a 的 radius（公尺）範圍內 */
export function isWithinRadius(a, b, radius) {
  return haversineDistance(a, b) <= radius;
}
