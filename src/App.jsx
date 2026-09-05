import { useCallback, useMemo, useState } from 'react';
import { CATEGORY_KEYS } from './config/categories.js';
import { getCategoriesWithDataSource } from './services/taipeiApi.js';
import { useFacilities } from './hooks/useFacilities.js';
import {
  buildSearchIndex,
  countByCategory,
  filterFacilities,
  normalizeSearchText,
} from './utils/facilityFilter.js';
import FacilityMap from './components/Map/FacilityMap.jsx';
import Sidebar from './components/Sidebar/Sidebar.jsx';
import {
  ErrorNotice,
  HeaderStatus,
  LoadingNotice,
  PartialErrorNotice,
} from './components/Status/DataStatus.jsx';

function buildCategorySelection(checked) {
  return Object.fromEntries(CATEGORY_KEYS.map((key) => [key, checked]));
}

export default function App() {
  const { status, facilities, sourceResults, sourceErrors, error, loadedAt, reload } = useFacilities();

  const [searchText, setSearchText] = useState('');
  const [selectedCategories, setSelectedCategories] = useState(() => buildCategorySelection(true));
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // 只在資料載入後重建一次索引；之後每次輸入只做字串比對
  const searchIndex = useMemo(() => buildSearchIndex(facilities), [facilities]);
  const query = normalizeSearchText(searchText);

  const filteredFacilities = useMemo(
    () => filterFacilities(searchIndex, selectedCategories, query),
    [searchIndex, selectedCategories, query],
  );

  const totalCounts = useMemo(() => countByCategory(facilities), [facilities]);
  const visibleCounts = useMemo(() => countByCategory(filteredFacilities), [filteredFacilities]);
  const categoriesWithSource = useMemo(() => getCategoriesWithDataSource(), []);

  const handleToggleCategory = useCallback((key) => {
    setSelectedCategories((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);
  const handleSelectAll = useCallback(() => setSelectedCategories(buildCategorySelection(true)), []);
  const handleClearAll = useCallback(() => setSelectedCategories(buildCategorySelection(false)), []);
  const handleToggleSidebar = useCallback(() => setSidebarOpen((open) => !open), []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__title">
          <h1>臺北市公共服務設施 GIS</h1>
          <span className="app-header__subtitle">公共服務設施分布地圖　V1 基礎版</span>
        </div>
        <div className="app-header__status">
          <HeaderStatus status={status} total={facilities.length} />
        </div>
      </header>

      <div className="app-body">
        <Sidebar
          open={sidebarOpen}
          onToggle={handleToggleSidebar}
          searchText={searchText}
          onSearchChange={setSearchText}
          selectedCategories={selectedCategories}
          onToggleCategory={handleToggleCategory}
          onSelectAll={handleSelectAll}
          onClearAll={handleClearAll}
          categoriesWithSource={categoriesWithSource}
          status={status}
          visibleTotal={filteredFacilities.length}
          loadedTotal={facilities.length}
          visibleCounts={visibleCounts}
          totalCounts={totalCounts}
          sourceResults={sourceResults}
          loadedAt={loadedAt}
        />

        <main className="map-area">
          {status === 'loading' && (
            <div className="map-overlay">
              <LoadingNotice />
            </div>
          )}
          {status === 'error' && (
            <div className="map-overlay">
              <ErrorNotice error={error} onRetry={reload} />
            </div>
          )}
          {status === 'success' && sourceErrors.length > 0 && (
            <div className="map-overlay">
              <PartialErrorNotice errors={sourceErrors} onRetry={reload} />
            </div>
          )}
          <FacilityMap facilities={filteredFacilities} />
        </main>
      </div>
    </div>
  );
}
