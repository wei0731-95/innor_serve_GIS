import { CATEGORY_CONFIG, CATEGORY_KEYS } from '../../config/categories.js';

/**
 * 分類 checkbox。分類清單來自 config/categories.js，新增分類不需要改這裡。
 * 目前沒有資料來源的分類會標示「尚無資料來源」，避免誤以為該分類真的是 0 間。
 */
export default function CategoryFilter({ selected, onToggle, onSelectAll, onClearAll, categoriesWithSource }) {
  return (
    <div className="category-filter">
      <div className="category-filter__actions">
        <button type="button" className="btn btn--small" onClick={onSelectAll}>
          全部選取
        </button>
        <button type="button" className="btn btn--small" onClick={onClearAll}>
          全部取消
        </button>
      </div>

      <ul className="category-filter__list">
        {CATEGORY_KEYS.map((key) => {
          const config = CATEGORY_CONFIG[key];
          const hasSource = categoriesWithSource.has(key);
          return (
            <li key={key}>
              <label className="category-filter__item">
                <input type="checkbox" checked={Boolean(selected[key])} onChange={() => onToggle(key)} />
                <span className="category-swatch" style={{ backgroundColor: config.markerColor }} aria-hidden="true" />
                <span className="category-filter__label">{config.label}</span>
                {!hasSource && <span className="category-filter__tag">尚無資料來源</span>}
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
