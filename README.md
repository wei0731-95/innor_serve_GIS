# 臺北市公共服務設施 GIS

臺北市公共服務設施分布地圖（V1 基礎版）。
這是「哪裡都沒有 / CityGap 服務缺口分析平台」的基礎版本：先把真實公開資料放上地圖，並預留 Coverage、Gap Analysis、設施模擬的擴充接口。

目前資料來源只有一個：臺北市資料大平台「臺北市公私立醫院」CSV。
畫面上所有設施、數量都來自這份真實資料，**沒有任何 mock / demo 資料**；API 失敗時畫面會直接顯示錯誤，不會偷偷改用假資料。

---

## 1. 專案介紹

| 項目 | 說明 |
| --- | --- |
| 目標 | 臺北市公共服務設施 GIS 基礎地圖 |
| 版本 | V1（基礎地圖） |
| 資料 | 臺北市資料大平台 Open Data（CSV） |
| 底圖 | OpenStreetMap |
| 定位 | 之後 CityGap 服務缺口分析平台的基礎 |

V1 具備：

- 真實醫院資料 marker（Marker Cluster 聚合）
- Popup 顯示名稱 / 類別 / 地址 / 電話
- 搜尋（機構名稱、地址）
- 分類 checkbox 篩選（11 個分類，全部選取 / 全部取消）
- 統計（目前顯示筆數、各分類筆數）
- API loading / error 狀態
- 統一資料格式與可擴充的分類、資料來源、Coverage 架構

---

## 2. 技術架構

- React 19 + Vite 8（JavaScript，不使用 TypeScript）
- Leaflet 1.9 + React-Leaflet 5
- Leaflet.markercluster（透過 `react-leaflet-cluster` 包裝）
- Papa Parse（CSV 解析）
- 純 CSS（無 UI framework）

資料流程：

```
Taipei Open Data（CSV）
        ↓
fetch（services/taipeiApi.js）
        ↓
Big5 / UTF-8 解碼 + Papa Parse（services/csvParser.js）
        ↓
normalizeFacility()（utils/normalizeFacility.js）
        ↓
useFacilities()（hooks/useFacilities.js）→ React state（只載入一次）
        ↓
搜尋 / 分類篩選（utils/facilityFilter.js，純前端）
        ↓
FacilityMap → MarkerClusterGroup → FacilityMarker → FacilityPopup
```

API 只在頁面載入時請求一次（以及使用者按「重新載入」時）。搜尋、切換 checkbox 都是前端 filter，不會再打 API。

---

## 3. 安裝方式

需要 Node.js 18 以上（開發時使用 Node 24）。

```bash
npm install
```

```bash
npm run dev
```

開啟終端機顯示的網址（預設 `http://localhost:5173`）。

其他指令：

```bash
npm run build
```

```bash
npm run preview
```

> `npm run preview` 是預覽正式 build 的結果，**不會**經過開發用 proxy，所以會看到 CORS 錯誤畫面。這是預期行為，請見「11. CORS 注意事項」。

---

## 4. 資料來源

| 項目 | 內容 |
| --- | --- |
| 平台 | 臺北市資料大平台（data.taipei） |
| 資料集 | 臺北市公私立醫院 |
| URL | `https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=eab7fdff-574d-427b-9324-c00833d695c8` |
| 格式 | CSV |
| 編碼 | **Big5**（回應標頭 `Content-Type: text/csv;charset=BIG-5`） |
| CORS | 回應**沒有** `Access-Control-Allow-Origin` |

兩個實測發現，寫程式時一定要注意：

1. **CSV 是 Big5，不是 UTF-8。** 瀏覽器的 `response.text()` 一律用 UTF-8 解碼，直接用會得到亂碼。本專案改用 `response.arrayBuffer()` 搭配 `TextDecoder('big5')`（見 `src/services/csvParser.js` 的 `decodeCsvBuffer`）。解碼順序是：UTF-8 BOM → 嚴格 UTF-8 → Content-Type 宣告的 charset → 資料來源設定的 `encoding` → 寬鬆 UTF-8，所以未來換成 UTF-8 的資料集也不用改程式。
2. **瀏覽器直接 fetch 會被 CORS 擋下。** 開發模式使用 Vite dev proxy 轉送同一個 URL，詳見第 11 節。

資料來源設定集中在 `src/services/taipeiApi.js` 的 `DATA_SOURCES`，component 裡不會出現 URL。

---

## 5. CSV 欄位

實際下載的 CSV 標題列（2026-09 實測）：

```
機構名稱,地址,電話,經度,緯度
```

欄位對應（`DATA_SOURCES.hospital.fieldMap`）：

| CSV 欄位 | 統一格式欄位 | 備註 |
| --- | --- | --- |
| `_id` | `id` | 這份 CSV 目前**沒有** `_id` 欄位，程式會改用 `hospital-<序號>` 當備援 id |
| `機構名稱` | `name` | 空值時顯示「未命名機構」 |
| `地址` | `address` | 空值時顯示「未提供」 |
| `電話` | `phone` | 空值時顯示「未提供」 |
| `經度` | `lng` | 必須是純數字字串，否則整筆略過 |
| `緯度` | `lat` | 必須是純數字字串，否則整筆略過 |

固定值：`category = "hospital"`、`source = "臺北市資料大平台"`。

統一資料格式（所有來源都會轉成這個形狀）：

```js
{
  id: string,
  name: string,
  category: string,   // config/categories.js 的 key
  address: string,
  phone: string,
  lat: number,
  lng: number,
  source: string,
  raw: object         // 原始 CSV row
}
```

無效資料處理規則（`utils/normalizeFacility.js` + `utils/geo.js`）：

- 經緯度為空、非純數字字串（例如 `"N/A"`、`"25.03abc"`）、超出 ±90 / ±180、或等於 (0, 0)：**不建立 marker**，統計面板會顯示「略過 N 筆座標無效」。
- 名稱空白：顯示「未命名機構」。
- 地址 / 電話空白：顯示「未提供」。

---

## 6. React Component 架構

```
src/
├─ main.jsx                     進入點，載入 Leaflet / MarkerCluster CSS
├─ App.jsx                      持有搜尋 / 篩選 / 側欄狀態，組合 Sidebar 與 Map
├─ index.css                    全站樣式（政府資訊平台風格）
├─ config/
│  └─ categories.js             分類設定（label、markerColor、coverageRadius…）
├─ services/
│  ├─ taipeiApi.js              DATA_SOURCES、fetchDataSource、fetchAllFacilities
│  └─ csvParser.js              Big5 / UTF-8 解碼、Papa Parse
├─ utils/
│  ├─ normalizeFacility.js      各來源 → 統一格式
│  ├─ geo.js                    座標驗證、Haversine 距離
│  ├─ coverage.js               Coverage / Gap / Simulation 擴充接口
│  ├─ facilityFilter.js         搜尋索引、篩選、分類計數
│  └─ leafletIcon.js            Leaflet 預設 icon 路徑修正、分類顏色 icon
├─ hooks/
│  └─ useFacilities.js          載入一次資料，管理 loading / success / error
└─ components/
   ├─ Map/
   │  ├─ FacilityMap.jsx        MapContainer + OSM + MarkerClusterGroup
   │  ├─ FacilityMarker.jsx     單一 marker（memo）
   │  └─ CoverageLayer.jsx      V2 服務範圍圓（預設關閉）
   ├─ Sidebar/
   │  ├─ Sidebar.jsx
   │  ├─ SearchBar.jsx
   │  ├─ CategoryFilter.jsx
   │  └─ Statistics.jsx
   ├─ Facility/
   │  └─ FacilityPopup.jsx
   └─ Status/
      └─ DataStatus.jsx         載入中 / 錯誤 / 部分失敗 / Header 狀態標籤
```

效能考量：

- CSV 只 parse 一次、normalize 一次，結果存在 React state。
- 搜尋索引（`buildSearchIndex`）只在資料載入後建立一次，之後每次輸入只做字串 `includes`。
- `filteredFacilities`、各分類計數都用 `useMemo`。
- `FacilityMarker` 用 `memo`，facility 物件穩定就不會重建 marker。
- 同一分類共用同一個 Leaflet icon 物件。
- MarkerClusterGroup 開啟 `chunkedLoading`，大量 marker 分批加入。

---

## 7. 如何新增新的資料類別

1. 在 `src/config/categories.js` 的 `CATEGORY_CONFIG` 新增一個 key：

```js
community_center: {
  label: '社區活動中心',
  description: '……',
  markerColor: '#00695c',
  icon: null,
  coverageRadius: null,   // 尚未定義服務半徑就填 null，不要猜
},
```

2. 完成。分類 checkbox、統計表、marker 顏色都會自動出現。
   在有資料來源之前，篩選面板會標示「尚無資料來源」。

---

## 8. 如何新增新的 API（資料來源）

1. 在臺北市資料大平台找到資料集的 CSV 下載 URL（`resource.download?rid=...`）。
2. 先確認 CSV 的標題列與編碼（可用瀏覽器或 curl 下載看一下）。
3. 在 `src/services/taipeiApi.js` 的 `DATA_SOURCES` 新增一個項目：

```js
clinic: {
  key: 'clinic',
  name: '臺北市診所',
  category: 'clinic',                     // 必須是 categories.js 已有的 key
  source: TAIPEI_OPEN_DATA_SOURCE_NAME,
  url: 'https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=<rid>',
  format: 'csv',
  encoding: 'big5',                       // 依實際編碼填，解碼器會先嘗試 UTF-8
  fieldMap: {
    id: '_id',
    name: '機構名稱',                      // 依實際 CSV 欄位名稱調整
    address: '地址',
    phone: '電話',
    lng: '經度',
    lat: '緯度',
  },
  enabled: true,
},
```

4. 完成。`fetchAllFacilities` 會用 `Promise.allSettled` 同時載入所有啟用的來源；某一個來源失敗不會影響其他來源，畫面會顯示「部分資料來源載入失敗」。

如果新來源不是 CSV（例如 JSON），在 `fetchDataSource` 依 `format` 分支處理即可，normalize 之後的格式不變。

---

## 9. 未來 Coverage 擴充方式（V2）

已經準備好的接口：

- `config/categories.js`：每個分類的 `coverageRadius`（公尺）。目前只有醫院 3000、診所 1500、長期照顧 1500 有值，其餘為 `null`。
- `utils/coverage.js`：
  - `getCoverageRadius(category)`：讀設定檔，沒有定義就回傳 `null`。
  - `calculateCoverage(facilities, { radiusByCategory })`：回傳每個設施的服務範圍圓（純幾何）。
  - `isPointCovered(point, circles)`：某點是否落在任一範圍內。
- `components/Map/CoverageLayer.jsx`：依 `calculateCoverage` 結果畫 `<Circle>`，目前 `enabled` 預設 `false`。

V2 要做的事：

1. 在 Sidebar 新增「顯示服務範圍」開關，狀態放在 `App.jsx`。
2. 把該狀態傳給 `<FacilityMap showCoverage={...} />`，`FacilityMap` 已經會把它交給 `CoverageLayer`。
3. 依文獻或政策確認各分類的服務半徑，補齊 `coverageRadius`。

大量設施時建議把 `Circle` 改為 canvas renderer（`MapContainer` 的 `preferCanvas`），或只畫目前視窗範圍內的圓。

---

## 10. 未來 Gap Analysis 擴充方式（V3 / V4）

概念：

```
服務供給（設施 + 服務半徑）
+ 人口需求（村里人口、年齡結構）
+ 距離 / 可及性
↓
Gap Score
```

`utils/coverage.js` 已放好三個函式的介面，目前呼叫都會拋出 `NotImplementedError`，**不會回傳任何虛構數字**：

| 函式 | 預期輸入 | 預期輸出 |
| --- | --- | --- |
| `calculateCoveredPopulation(coverageCircles, populationUnits)` | 服務範圍圓、真實人口單元 `[{ id, name, lat, lng, population }]` | `{ coveredPopulation, uncoveredPopulation, coveredUnitIds }` |
| `calculateGap({ facilities, populationUnits, category, options })` | 設施、人口單元、分類 | `[{ unitId, supply, demand, accessibility, gapScore }]` |
| `simulateFacility({ facilities, populationUnits, newFacility })` | 現有設施、人口單元、模擬新增的設施 | `{ before, after, deltaCoveredPopulation, deltaGapScore }` |

V3 步驟：

1. 取得真實人口資料（例如臺北市各里人口統計 + 里界 / 里代表點）。
2. 在 `services/` 新增人口資料來源與 normalize。
3. 實作 `calculateCoveredPopulation` 與 `calculateGap`，距離計算用 `utils/geo.js` 的 `haversineDistance`。
4. 新增 Gap 圖層（例如 choropleth）與 Sidebar 面板。

V4 步驟：

1. 地圖點擊事件取得座標（React-Leaflet `useMapEvents`）。
2. 呼叫 `simulateFacility` 比較新增前後的覆蓋人口與 Gap Score。

在沒有真實人口與供給資料之前，**不要**在畫面上顯示任何 Gap Score 或人口推估。

---

## 11. CORS 注意事項

實測（2026-09）`data.taipei` 的 CSV 下載端點**不回傳** `Access-Control-Allow-Origin`，即使帶 `Origin` header 也一樣，所以瀏覽器直接 `fetch` 一定會被擋下。

本專案的處理方式：

| 模式 | 行為 |
| --- | --- |
| `npm run dev` | `.env.development` 設定 `VITE_TAIPEI_PROXY_PREFIX=/taipei-proxy`，程式把 `https://data.taipei/...` 改成 `/taipei-proxy/...`，由 `vite.config.js` 的 `server.proxy` 轉送到 **同一個原始 URL**。沒有後端、沒有改資料來源。 |
| `npm run build` / `npm run preview` | 沒有該環境變數，程式直接呼叫原始 URL，瀏覽器會被 CORS 擋下，畫面顯示「目前瀏覽器無法直接存取資料來源，可能受到 CORS 限制。」 |

相關程式：

- `vite.config.js`：`server.proxy['/taipei-proxy']` → `https://data.taipei`
- `.env.development`：`VITE_TAIPEI_PROXY_PREFIX`
- `src/services/taipeiApi.js`：`resolveRequestUrl()` 只在有前綴設定時改寫 URL

正式部署時可選擇：

1. **Reverse proxy**：在 Nginx / Caddy 加一條 `/taipei-proxy/` → `https://data.taipei/` 的轉送，並在 build 時設定 `VITE_TAIPEI_PROXY_PREFIX=/taipei-proxy`。
2. **FastAPI backend proxy**：後端提供 `/api/facilities`，由後端下載 CSV、解碼、normalize 後回傳 JSON；前端只要在 `DATA_SOURCES` 換 URL 與 `format`。這也是 V3 需要人口資料時比較自然的架構。

無論哪一種，都不會、也不應該在 API 失敗時改用假資料。

