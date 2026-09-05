import SearchBar from './SearchBar.jsx';
import CategoryFilter from './CategoryFilter.jsx';
import Statistics from './Statistics.jsx';

/**
 * 左側固定側欄：搜尋 / 設施分類 / 統計。
 * 狀態都由 App 持有（controlled），側欄收合時內容卸載也不會遺失搜尋文字。
 */
export default function Sidebar({
  open,
  onToggle,
  searchText,
  onSearchChange,
  selectedCategories,
  onToggleCategory,
  onSelectAll,
  onClearAll,
  categoriesWithSource,
  status,
  visibleTotal,
  loadedTotal,
  visibleCounts,
  totalCounts,
  sourceResults,
  loadedAt,
}) {
  return (
    <aside className={open ? 'sidebar' : 'sidebar sidebar--collapsed'} aria-label="篩選與統計">
      <button type="button" className="sidebar__toggle" onClick={onToggle} aria-expanded={open}>
        {open ? '收合側欄 ◀' : '展開側欄 ▶'}
      </button>

      {open && (
        <div className="sidebar__content">
          <section className="sidebar__section">
            <h2>搜尋</h2>
            <SearchBar value={searchText} onChange={onSearchChange} />
          </section>

          <section className="sidebar__section">
            <h2>設施分類</h2>
            <CategoryFilter
              selected={selectedCategories}
              onToggle={onToggleCategory}
              onSelectAll={onSelectAll}
              onClearAll={onClearAll}
              categoriesWithSource={categoriesWithSource}
            />
          </section>

          <section className="sidebar__section">
            <h2>統計</h2>
            <Statistics
              status={status}
              visibleTotal={visibleTotal}
              loadedTotal={loadedTotal}
              visibleCounts={visibleCounts}
              totalCounts={totalCounts}
              sourceResults={sourceResults}
              loadedAt={loadedAt}
            />
          </section>
        </div>
      )}
    </aside>
  );
}
