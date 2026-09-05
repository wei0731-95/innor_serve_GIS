import { getCategoryLabel } from '../../config/categories.js';
import { displayOrNotProvided, getDisplayName } from '../../utils/normalizeFacility.js';

/**
 * Marker popup 內容：名稱 / 類別 / 地址 / 電話。
 * 欄位不存在時顯示「未提供」，名稱不存在時顯示「未命名機構」。
 */
export default function FacilityPopup({ facility }) {
  const rows = [
    ['名稱', getDisplayName(facility)],
    ['類別', getCategoryLabel(facility.category)],
    ['地址', displayOrNotProvided(facility.address)],
    ['電話', displayOrNotProvided(facility.phone)],
  ];

  return (
    <div className="facility-popup">
      <dl>
        {rows.map(([label, value]) => (
          <div key={label} className="facility-popup__row">
            <dt>{label}：</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {facility.source && <p className="facility-popup__source">資料來源：{facility.source}</p>}
    </div>
  );
}
