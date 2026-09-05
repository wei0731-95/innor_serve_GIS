import { CATEGORY_CONFIG, CATEGORY_KEYS } from '../../config/categories.js';

/**
 * 統計：目前顯示筆數（搜尋 + 篩選後）與各分類筆數。
 * 所有數字都來自實際載入的資料；沒有資料來源的分類就是 0。
 */
export default function Statistics({
  status,
  visibleTotal,
  loadedTotal,
  visibleCounts,
  totalCounts,
  sourceResults,
  loadedAt,
}) {
  return (
    <div className="statistics">
      <div className="statistics__headline">
        <span>目前顯示</span>
        <strong className="statistics__headline-value">{visibleTotal}</strong>
        <span>筆</span>
      </div>
      <div className="statistics__meta">
        已載入資料：{loadedTotal} 筆
        {status === 'loading' && '（載入中）'}
      </div>

      <table className="statistics__table">
        <thead>
          <tr>
            <th scope="col">分類</th>
            <th scope="col" className="num">顯示</th>
            <th scope="col" className="num">總數</th>
          </tr>
        </thead>
        <tbody>
          {CATEGORY_KEYS.map((key) => (
            <tr key={key} className={totalCounts[key] ? undefined : 'statistics__row--empty'}>
              <td>{CATEGORY_CONFIG[key].label}</td>
              <td className="num">{visibleCounts[key] ?? 0}</td>
              <td className="num">{totalCounts[key] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {sourceResults.length > 0 && (
        <div className="statistics__sources">
          <div className="statistics__sources-title">資料來源</div>
          <ul>
            {sourceResults.map((result) => (
              <li key={result.sourceKey}>
                {result.sourceName}：{result.facilities.length} 筆有效
                {result.skipped > 0 && `，略過 ${result.skipped} 筆座標無效`}
              </li>
            ))}
          </ul>
          {loadedAt && (
            <div className="statistics__meta">載入時間：{loadedAt.toLocaleString('zh-TW', { hour12: false })}</div>
          )}
        </div>
      )}
    </div>
  );
}
