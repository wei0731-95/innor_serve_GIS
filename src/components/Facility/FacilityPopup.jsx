import { getCategoryLabel } from '../../config/categories.js';
import { describeCoordinateLevel, displayOrNotProvided, getDisplayName } from '../../utils/normalizeFacility.js';
import { formatDateTime } from '../../utils/formatDate.js';

/**
 * Marker popup 內容：名稱 / 類別 / 地址 / 電話，以及完整的資料來源追溯
 * （資料集名稱、來源機關、原始資料連結、資料時間、最後同步時間、座標來源）。
 * 欄位不存在時顯示「未提供」，名稱不存在時顯示「未命名機構」。
 */
export default function FacilityPopup({ facility }) {
  const rows = [
    ['名稱', getDisplayName(facility)],
    ['類別', getCategoryLabel(facility.category)],
    ['地址', displayOrNotProvided(facility.address)],
    ['電話', displayOrNotProvided(facility.phone)],
  ];
  if (facility.district) {
    rows.push(['行政區', facility.district]);
  }
  if (facility.externalType && facility.category === 'long_term_care') {
    rows.push(['長照類型', `${facility.externalType} 級單位`]);
  } else if (facility.externalType && facility.externalType !== '診所') {
    rows.push(['屬性', facility.externalType]);
  }

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

      <div className="facility-popup__source">
        <div className="facility-popup__source-title">資料來源</div>
        <dl>
          <div className="facility-popup__row">
            <dt>資料來源：</dt>
            <dd>{displayOrNotProvided(facility.source)}</dd>
          </div>
          <div className="facility-popup__row">
            <dt>來源機關：</dt>
            <dd>{displayOrNotProvided(facility.sourceOrganization)}</dd>
          </div>
          <div className="facility-popup__row">
            <dt>原始資料：</dt>
            <dd>
              {facility.sourceUrl ? (
                <a href={facility.sourceUrl} target="_blank" rel="noopener noreferrer">
                  資料集頁面
                </a>
              ) : (
                '未提供'
              )}
              {facility.sourceDownloadUrl && (
                <>
                  {' ／ '}
                  <a href={facility.sourceDownloadUrl} target="_blank" rel="noopener noreferrer">
                    原始檔案
                  </a>
                </>
              )}
            </dd>
          </div>
          {facility.rawUpdatedAt && (
            <div className="facility-popup__row">
              <dt>資料時間：</dt>
              <dd>{facility.rawUpdatedAt}</dd>
            </div>
          )}
          <div className="facility-popup__row">
            <dt>最後同步：</dt>
            <dd>{formatDateTime(facility.sourceSyncedAt)}</dd>
          </div>
          <div className="facility-popup__row">
            <dt>座標來源：</dt>
            <dd title={facility.coordinateSource || undefined}>{describeCoordinateLevel(facility)}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
