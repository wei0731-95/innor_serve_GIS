/**
 * 設施分類設定（集中管理）
 *
 * 所有與「分類」有關的設定都放在這裡：顯示名稱、說明、marker 顏色、服務半徑。
 * 新增分類時只需要在 CATEGORY_CONFIG 加一個 key，UI（篩選、統計、圖例）會自動出現。
 *
 * 欄位說明：
 * - label          : UI 顯示名稱
 * - description    : 分類說明（保留給未來 tooltip / 說明面板）
 * - markerColor    : 地圖 marker 顏色（見 utils/leafletIcon.js）
 * - icon           : 保留欄位，未來可放自訂 icon（目前一律 null，使用顏色圓點）
 * - coverageRadius : 服務涵蓋半徑（公尺）。V2 Coverage 使用。
 *                    只有明確定義過的分類才填數值；尚未定義的分類為 null，
 *                    CoverageLayer 會略過 null 的分類，不會自行假設半徑。
 */
export const CATEGORY_CONFIG = {
  hospital: {
    label: '醫院',
    description: '臺北市公私立醫院',
    markerColor: '#c62828',
    icon: null,
    coverageRadius: 3000,
  },
  clinic: {
    label: '診所',
    description: '基層診所',
    markerColor: '#ef6c00',
    icon: null,
    coverageRadius: 1500,
  },
  long_term_care: {
    label: '長期照顧',
    description: '長照機構、日照中心、居家服務單位等',
    markerColor: '#6a1b9a',
    icon: null,
    coverageRadius: 1500,
  },
  pharmacy: {
    label: '藥局',
    description: '社區藥局',
    markerColor: '#2e7d32',
    icon: null,
    coverageRadius: null,
  },
  disability: {
    label: '身心障礙服務',
    description: '身心障礙者服務機構、資源中心',
    markerColor: '#00838f',
    icon: null,
    coverageRadius: null,
  },
  childcare: {
    label: '托育 / 幼兒服務',
    description: '托嬰中心、親子館、托育資源中心等',
    markerColor: '#ad1457',
    icon: null,
    coverageRadius: null,
  },
  social_welfare: {
    label: '社會福利',
    description: '社福中心、老人服務中心等',
    markerColor: '#4527a0',
    icon: null,
    coverageRadius: null,
  },
  other: {
    label: '其他',
    description: '未歸類的公共服務設施',
    markerColor: '#546e7a',
    icon: null,
    coverageRadius: null,
  },
  elementary_school: {
    label: '國民小學',
    description: '公私立國民小學',
    markerColor: '#1565c0',
    icon: null,
    coverageRadius: null,
  },
  junior_high_school: {
    label: '國民中學',
    description: '公私立國民中學',
    markerColor: '#0277bd',
    icon: null,
    coverageRadius: null,
  },
  kindergarten: {
    label: '幼兒園',
    description: '公私立幼兒園、非營利幼兒園',
    markerColor: '#f9a825',
    icon: null,
    coverageRadius: null,
  },
};

/** 分類 key 的固定順序（UI 依此順序顯示） */
export const CATEGORY_KEYS = Object.keys(CATEGORY_CONFIG);

/** 未知分類一律歸到「其他」 */
export const DEFAULT_CATEGORY = 'other';

export function isKnownCategory(key) {
  return Object.prototype.hasOwnProperty.call(CATEGORY_CONFIG, key);
}

export function getCategoryConfig(key) {
  return isKnownCategory(key) ? CATEGORY_CONFIG[key] : CATEGORY_CONFIG[DEFAULT_CATEGORY];
}

export function getCategoryLabel(key) {
  return getCategoryConfig(key).label;
}
