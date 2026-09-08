import { CATEGORY_CONFIG, CATEGORY_KEYS } from '../../config/categories.js';
import { formatDateTime, latestDate } from '../../utils/formatDate.js';

const SOURCE_STATUS_LABEL = {
  success: '成功',
  error: '失敗',
  running: '同步中',
  never: '尚未同步',
};

/**
 * 統計：目前顯示筆數（搜尋 + 篩選後）、各分類筆數、缺座標筆數、資料來源同步狀態。
 * 所有數字都來自後端資料庫（/api/facilities、/api/sources、/api/categories），不在前端 hard-code。
 */
export default function Statistics({
  status,
  visibleTotal,
  visibleOnMap,
  loadedTotal,
  visibleCounts,
  totalCounts,
  missingCounts,
  sources,
  loadedAt,
  syncRunning,
}) {
  const facilitySources = (sources ?? []).filter((source) => source.kind === 'facility' && source.enabled !== false);
  const successSources = facilitySources.filter((source) => source.last_status === 'success');
  const failedSources = facilitySources.filter((source) => source.last_status === 'error');
  const skippedTotal = facilitySources.reduce((sum, source) => sum + (source.skipped_count ?? 0), 0);
  const missingTotal = facilitySources.reduce((sum, source) => sum + (source.missing_coordinate_count ?? 0), 0);
  const lastSyncAt = latestDate(facilitySources.map((source) => (source.last_success_at ? new Date(source.last_success_at) : null)));
  const hiddenByCoordinates = visibleTotal - visibleOnMap;

  return (
    <div className="statistics">
      <div className="statistics__headline">
        <span>目前顯示</span>
        <strong className="statistics__headline-value">{visibleTotal}</strong>
        <span>筆</span>
      </div>
      <div className="statistics__meta">
        地圖上 {visibleOnMap} 筆
        {hiddenByCoordinates > 0 && `，另有 ${hiddenByCoordinates} 筆缺座標不顯示`}
      </div>
      <div className="statistics__meta">
        總資料數：{loadedTotal} 筆
        {status === 'loading' && '（載入中）'}
        {syncRunning && '（後端同步中）'}
      </div>

      <table className="statistics__table">
        <thead>
          <tr>
            <th scope="col">分類</th>
            <th scope="col" className="num">顯示</th>
            <th scope="col" className="num">總數</th>
            <th scope="col" className="num">缺座標</th>
          </tr>
        </thead>
        <tbody>
          {CATEGORY_KEYS.map((key) => (
            <tr key={key} className={totalCounts[key] ? undefined : 'statistics__row--empty'}>
              <td>{CATEGORY_CONFIG[key].label}</td>
              <td className="num">{visibleCounts[key] ?? 0}</td>
              <td className="num">{totalCounts[key] ?? 0}</td>
              <td className="num">{missingCounts?.[key] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="statistics__sources">
        <div className="statistics__sources-title">資料來源同步狀態</div>
        {facilitySources.length === 0 ? (
          <div className="statistics__meta">尚未取得資料來源清單</div>
        ) : (
          <>
            <dl className="statistics__summary">
              <div>
                <dt>成功資料源</dt>
                <dd>{successSources.length}</dd>
              </div>
              <div>
                <dt>失敗資料源</dt>
                <dd className={failedSources.length > 0 ? 'is-error' : undefined}>{failedSources.length}</dd>
              </div>
              <div>
                <dt>跳過資料筆數</dt>
                <dd>{skippedTotal}</dd>
              </div>
              <div>
                <dt>缺失座標數</dt>
                <dd>{missingTotal}</dd>
              </div>
              <div>
                <dt>最後同步時間</dt>
                <dd>{formatDateTime(lastSyncAt, '尚未同步')}</dd>
              </div>
            </dl>
            <ul className="statistics__source-list">
              {facilitySources.map((source) => (
                <li key={source.id} className={`statistics__source statistics__source--${source.last_status}`}>
                  <span className="statistics__source-status" aria-hidden="true" />
                  <span className="statistics__source-name" title={source.organization}>
                    {source.name}
                  </span>
                  <span className="statistics__source-detail">
                    {SOURCE_STATUS_LABEL[source.last_status] ?? source.last_status}
                    {source.last_status === 'success' && `・${source.record_count} 筆`}
                    {source.skipped_count > 0 && `・略過 ${source.skipped_count}`}
                    {source.missing_coordinate_count > 0 && `・缺座標 ${source.missing_coordinate_count}`}
                  </span>
                  {source.last_status === 'error' && source.last_error && (
                    <span className="statistics__source-error">{source.last_error}</span>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
        {loadedAt && <div className="statistics__meta">前端載入時間：{formatDateTime(loadedAt)}</div>}
      </div>
    </div>
  );
}
