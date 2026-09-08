import { useCallback, useMemo, useState } from 'react';
import { CATEGORY_KEYS } from './config/categories.js';
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
  SyncingNotice,
} from './components/Status/DataStatus.jsx';

function buildCategorySelection(checked) {
  return Object.fromEntries(CATEGORY_KEYS.map((key) => [key, checked]));
}

export default function App() {
  const {
    status,
    facilities,
    sources,
    categories,
    sourceResults,
    sourceErrors,
    pendingSources,
    categoriesWithSource,
    syncRunning,
    error,
    loadedAt,
    reload,
  } = useFacilities();

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

  // 只有具備官方座標的設施才建立 marker；缺座標的仍會被搜尋與統計
  const mapFacilities = useMemo(() => filteredFacilities.filter((f) => f.hasCoordinates), [filteredFacilities]);

  const totalCounts = useMemo(() => countByCategory(facilities), [facilities]);
  const visibleCounts = useMemo(() => countByCategory(filteredFacilities), [filteredFacilities]);
  const missingCounts = useMemo(
    () => countByCategory(facilities.filter((f) => !f.hasCoordinates)),
    [facilities],
  );

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
          <span className="app-header__subtitle">公共服務設施分布地圖　資料由 FastAPI 後端提供</span>
        </div>
        <div className="app-header__status">
          <HeaderStatus status={status} total={facilities.length} syncRunning={syncRunning} />
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
          visibleOnMap={mapFacilities.length}
          loadedTotal={facilities.length}
          visibleCounts={visibleCounts}
          totalCounts={totalCounts}
          missingCounts={missingCounts}
          categories={categories}
          sources={sources}
          sourceResults={sourceResults}
          sourceErrors={sourceErrors}
          pendingSources={pendingSources}
          loadedAt={loadedAt}
          syncRunning={syncRunning}
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
          {status === 'success' && syncRunning && (
            <div className="map-overlay">
              <SyncingNotice pendingSources={pendingSources} />
            </div>
          )}
          {status === 'success' && !syncRunning && sourceErrors.length > 0 && (
            <div className="map-overlay">
              <PartialErrorNotice errors={sourceErrors} onRetry={reload} />
            </div>
          )}
          <FacilityMap facilities={mapFacilities} />
        </main>
      </div>
    </div>
  );
}
