import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import { getCategoryConfig } from '../config/categories.js';

/**
 * 修正 Leaflet 在 bundler（Vite）環境下找不到預設 marker 圖片的問題。
 * 沒有這段的話會出現「地圖有點但 marker 圖示消失」。
 * 這裡明確用 import 取得圖片 URL，交給 Vite 處理路徑。
 */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const ICON_SIZE = 16;
const iconCache = new Map();

/**
 * 依分類取得 marker icon（依 CATEGORY_CONFIG.markerColor 上色的圓點）。
 * 同一分類共用同一個 icon 物件，避免大量 marker 時重複建立。
 */
export function getCategoryIcon(category) {
  const cached = iconCache.get(category);
  if (cached) return cached;

  const { markerColor } = getCategoryConfig(category);
  const icon = L.divIcon({
    className: 'facility-marker-icon',
    html: `<span class="facility-pin" style="background:${markerColor}"></span>`,
    iconSize: [ICON_SIZE, ICON_SIZE],
    iconAnchor: [ICON_SIZE / 2, ICON_SIZE / 2],
    popupAnchor: [0, -ICON_SIZE / 2],
  });

  iconCache.set(category, icon);
  return icon;
}
