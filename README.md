# 臺北市公共服務設施 GIS（CityGap 基礎版）

臺北市公共服務設施分布地圖，是「哪裡都沒有 / CityGap 服務缺口分析平台」的基礎版本。

本版本的重點是**可靠的設施資料後端**：所有政府開放資料由 FastAPI 後端下載、解析、清洗、標準化後存入 SQLite，前端 React 地圖只呼叫自己的 REST API。每一筆設施都能追溯到原始資料集、來源機關與同步時間。

原則：

- 只使用官方政府開放資料，不用第三方 POI、不用免費 CORS proxy。
- 沒有官方座標的設施**不會出現在地圖上**，但保留在資料庫並標記 `coordinate_status = missing`，統計面板會顯示缺座標筆數。
- 任何來源同步失敗都只影響該來源，其他來源與既有資料不受影響，畫面會顯示失敗來源與錯誤訊息。
- 沒有 mock 資料、沒有隨機座標、沒有依地址猜座標、沒有 fallback 假資料。

目前地圖顯示 6 類設施：醫院、診所、幼兒園、國民小學、國民中學、長期照顧。

最快的啟動方式是 Docker（見第 13 節）：安裝 Docker Desktop 後在專案根目錄執行

```bash
docker compose up --build
```

前端 <http://localhost:3000>、後端 <http://localhost:8000>、Swagger <http://localhost:8000/docs>。不想用 Docker 時，依第 2、3 節分別啟動後端與前端。

---

## 1. Architecture

```
Browser
  ↓
React（Vite）              src/            搜尋 / 分類篩選 / 統計 / Leaflet 地圖 / Marker Cluster
  ↓  GET /api/facilities, /api/sources, /api/categories, /api/sync/status
FastAPI                    backend/app/    REST API、CORS、啟動時背景同步
  ↓
SQLite                     backend/data/citygap.db（自動建立）
  ↓  fetch → decode → parse → validate → normalize → deduplicate → 座標補足 → upsert → sync_log
Government Open Data       data.taipei、stats.moe.gov.tw、ltcpap.mohw.gov.tw、tgos.tw（NLSC）
```

前端不再直接呼叫任何政府 API，也不知道 CSV 格式、Big5 編碡、政府欄位名稱或去重規則。

---

## 2. Backend installation

需要 Python 3.11 以上（開發時使用 3.13）。

```bash
cd backend
```

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

（選用）複製環境設定範例：

```bash
copy .env.example .env
```

啟動：

```bash
uvicorn app.main:app --reload
```

第一次啟動會：

1. 建立 `backend/data/citygap.db` 與三張資料表（`facilities`、`data_sources`、`sync_logs`）。
2. 依 `app/services/source_registry.py` 初始化 `data_sources`。
3. 在背景同步所有啟用的資料來源（約 10 秒，下載量約 30 MB）。API 在同步期間即可使用，前端會每 5 秒自動重新載入直到同步完成。

執行後端測試：

```bash
python -m pytest
```

---

## 3. Frontend

需要 Node.js 18 以上。

```bash
npm install
```

```bash
npm run dev
```

開啟 `http://localhost:5173`。開發模式預設連到 `http://localhost:8000`（可用 `.env.development` 的 `VITE_API_BASE_URL` 覆寫）。

其他指令：

```bash
npm test
```

```bash
npm run build
```

---

## 4. API documentation

後端啟動後：

- Swagger UI：<http://localhost:8000/docs>（`/api/docs` 會轉址到這裡）
- ReDoc：<http://localhost:8000/redoc>
- OpenAPI：<http://localhost:8000/openapi.json>

| Method | Path | 說明 |
| --- | --- | --- |
| GET | `/api/health` | `{status, database, version, facility_count, sync_running}`；資料庫異常時回 503 |
| GET | `/api/facilities` | 所有設施 `{count, items}`。query：`category`、`search`（名稱 / 地址，臺台同義）、`district`、`with_coordinates=true` |
| GET | `/api/facilities/{id}` | 單一設施，找不到回 404 |
| GET | `/api/categories` | 每個分類的 `label`、`count`、`with_coordinates`、`missing_coordinates`、來源狀態 |
| GET | `/api/sources` | 所有資料來源：機關、URL、資料集頁面、啟用狀態、最近同步時間 / 狀態 / 錯誤、筆數、略過筆數、缺座標筆數 |
| GET | `/api/sources/{id}` | 單一資料來源 |
| GET | `/api/sources/{id}/logs` | 該來源最近的同步紀錄 |
| POST | `/api/sync` | 手動重新同步所有啟用的來源（同步執行，回傳每個來源結果；已有同步在跑時回 409） |
| POST | `/api/sync/{source_id}` | 重新同步單一來源（學校名錄會連同 NLSC 座標來源一起同步） |
| GET | `/api/sync/status` | 是否正在同步、上次執行結果 |

設施的標準化格式（`FacilityOut`）：

```json
{
  "id": "moe_elementary:313601",
  "name": "市立松山國小",
  "category": "elementary_school",
  "address": "臺北市松山區八德路四段746號",
  "phone": "(02)27672907",
  "district": "松山區",
  "lat": 25.0497, "lng": 121.5672,
  "coordinate_status": "ok", "coordinate_level": 2,
  "coordinate_source": "內政部國土測繪中心「各級學校範圍圖_121分帶」多邊形中心點（依學校名稱對應）：臺北市松山區松山國民小學（圖資 202206）",
  "source": "國民小學名錄", "source_id": "moe_elementary",
  "source_url": "https://data.gov.tw/dataset/6087",
  "source_organization": "教育部統計處",
  "source_download_url": "https://stats.moe.gov.tw/files/school/115/e1_new.csv",
  "source_synced_at": "2026-09-05T07:17:50+00:00",
  "external_id": "313601", "external_type": "公立", "raw_updated_at": "115學年度",
  "updated_at": "2026-09-05T07:17:50+00:00"
}
```

政府來源的原始欄位不會出現在 API 回應中（原始列以 JSON 保存在 `facilities.raw_json`，僅供除錯）。

---

## 5. Environment variables

### Backend（`backend/.env`，範例見 `backend/.env.example`）

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/citygap.db` | 相對路徑以 `backend/` 為基準 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 逗號分隔的允許來源；正式環境填實際網域 |
| `SYNC_ON_STARTUP` | `true` | 啟動時是否背景同步 |
| `HTTP_TIMEOUT_SECONDS` | `90` | 下載政府資料逾時 |
| `HTTP_MAX_RETRIES` | `2` | 5xx / 逾時 / 網路錯誤的重試次數（4xx 不重試） |
| `SSL_STRICT_X509` | `false` | 見第 9 節 |
| `CACHE_DIR` | `./data/cache` | 下載檔案快取（目前只用於 NLSC 學校範圍圖） |
| `LOG_LEVEL` | `INFO` | |

### Frontend（`.env.development` / build 環境，範例見 `.env.example`）

| 變數 | 說明 |
| --- | --- |
| `VITE_API_BASE_URL` | 後端位址。開發未設定時預設 `http://localhost:8000`；正式 build 未設定時使用同源相對路徑 `/api/...` |

---

## 6. Database location

`backend/data/citygap.db`（SQLite，WAL 模式），由後端第一次啟動時自動建立，已列入 `.gitignore`。

| 資料表 | 用途 | 主要欄位 |
| --- | --- | --- |
| `facilities` | 標準化設施 | `id`（`{source_id}:{external_id}`）、`name`、`category`、`address`、`phone`、`district`、`lat`、`lng`、`coordinate_status`、`coordinate_level`、`coordinate_source`、`source_id`、`source_name`、`source_url`、`external_id`、`external_type`、`raw_updated_at`、`raw_json`、`created_at`、`updated_at`；`(source_id, external_id)` 唯一 |
| `data_sources` | 資料來源與最近同步狀態 | `id`、`name`、`organization`、`category`、`kind`（facility / geometry）、`url`、`dataset_url`、`format`、`encoding`、`enabled`、`last_synced_at`、`last_success_at`、`last_status`、`last_error`、`record_count`、`skipped_count`、`missing_coordinate_count` |
| `sync_logs` | 每次同步紀錄 | `id`、`source_id`、`started_at`、`completed_at`、`status`、`fetched_count`、`inserted_count`、`updated_count`、`deleted_count`、`skipped_count`、`missing_coordinate_count`、`error_message`、`detail`（JSON） |

刪除 `citygap.db` 後重新啟動即可重建。

---

## 7. Data source list

全部為政府開放資料，定義在 `backend/app/services/source_registry.py`。2026-09-05 實際同步結果：

| source_id | 資料集（data.gov.tw） | 提供機關 | 分類 | 格式 / 編碼 | 筆數 | 缺座標 | 座標來源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `taipei_hospital` | [臺北市公私立醫療院所](https://data.gov.tw/dataset/121182)－醫院 | 臺北市政府衛生局 | hospital | CSV / Big5 | 37 | 0 | Level 1（資料內含經緯度） |
| `taipei_clinic` | [臺北市公私立醫療院所](https://data.gov.tw/dataset/121182)－診所 | 臺北市政府衛生局 | clinic | CSV / Big5 | 1,858 | 0 | Level 1 |
| `moe_kindergarten` | [幼兒園名錄](https://data.gov.tw/dataset/6086) | 教育部統計處 | kindergarten | CSV / UTF-8 | 658 | **658** | 無（見第 11 節） |
| `moe_elementary` | [國民小學名錄](https://data.gov.tw/dataset/6087) | 教育部統計處 | elementary_school | CSV / UTF-8 | 147 | 5 | Level 2（NLSC 學校範圍圖） |
| `moe_junior_high` | [國民中學名錄](https://data.gov.tw/dataset/6088) | 教育部統計處 | junior_high_school | CSV / UTF-8 | 59 | 0 | Level 2（NLSC 學校範圍圖） |
| `mohw_ltc_abc` | [長照ABC據點](https://data.gov.tw/dataset/88270) | 衛生福利部 | long_term_care | CSV / UTF-8 | 1,014 | 28 | Level 1 |
| `nlsc_school_blocks` | [各級學校範圍圖_121分帶](https://data.gov.tw/dataset/174606) | 內政部國土測繪中心 | （座標補足用） | SHP zip / EPSG:3826 | 289 個臺北市多邊形 | | |

每個來源的處理規則：

- **醫院 / 診所**：來源已依「醫院數」「診所數」分成兩個檔案，直接對應 hospital / clinic。名稱尾端的 tab 會移除；沒有官方代碼，`external_id` 為名稱 + 地址的 16 碼 SHA-1。這兩個檔案都沒有電話欄位。
- **幼兒園 / 國小 / 國中**：名錄含全國各縣市與歷年學年度，只匯入**最新學年度**（目前 115）且縣市為臺北市的資料；`external_id` 為教育部學校代碼；地址的 `[郵遞區號]` 前綴會移除。國小名錄依學年度分檔，程式會由新到舊嘗試 `files/school/{學年度}/e1_new.csv`。
- **國小 / 國中座標**：名錄沒有座標，改用內政部國土測繪中心「各級學校範圍圖」的多邊形中心點（TWD97 → WGS84，pyproj），以學校名稱對應（市立松山國小 ↔ 臺北市松山區松山國民小學；公私立分開比對；同校多個多邊形取面積最大者）。對應不到的維持 missing。
- **長照**：只匯入縣市代碼 63000（臺北市）；同一機構代碼在原始資料有多列（每項特約服務一列），合併為一筆，A / B / C 類型保留在 `external_type`（例如 `B`、`A/B`），特約服務項目保留在 `raw_json`。注意 B 級單位依官方資料包含藥局、居家服務、交通接送等單位。
- **臺北市老人福利機構名冊**（data.gov.tw 138911）沒有座標，且大多已包含在長照 ABC 資料中，本版本未啟用以避免重複。

---

## 8. Sync process

```
source（source_registry）
  ↓ fetch        httpx，逾時 / 重試，4xx 不重試；依學年度多個候選 URL 時 404 才換下一個
  ↓ decode       UTF-8 BOM → 嚴格 UTF-8 → Content-Type charset → 來源設定 encoding → 寬鬆模式
  ↓ parse        csv 模組，去除欄位與值的空白，檢查必要欄位
  ↓ validate     缺名稱 / 代碼的列略過；座標必須是純數字且落在臺灣範圍，否則 missing
  ↓ normalize    各來源的 normalizer → 統一 NormalizedFacility
  ↓ deduplicate  同一 external_id 只留第一筆（長照為合併）
  ↓ 座標補足     教育部名錄 × NLSC 學校範圍圖（Level 2）
  ↓ upsert       以 (source_id, external_id) 為鍵：新增 / 更新有變動欄位 / 刪除來源中已消失的資料
  ↓ sync_log     成功或失敗都寫一筆，並更新 data_sources 的最近狀態
```

- 每個來源各自一個 transaction。任一來源失敗（逾時、HTTP 錯誤、編碼錯誤、缺欄位、空資料集、資料庫錯誤）只會讓該來源標記為 `error` 並保留 DB 內舊資料，其他來源照常完成，API 回傳 partial status（`/api/sources`、`/api/categories`）。
- 「來源沒有任何臺北市資料」視為失敗，不會把既有資料清空。
- NLSC 學校範圍圖下載失敗時，會沿用上一次成功下載並存於 `backend/data/cache/` 的官方檔案，並在 `last_error` 明確記錄「沿用 … 下載的官方檔案」。沒有快取就標記失敗，學校座標維持 missing。
- 同一時間只允許一個同步流程；重複觸發 `POST /api/sync` 會回 409。
- 重新同步是 idempotent 的：資料沒變時 inserted / updated / deleted 都是 0。

---

## 9. CORS 與 SSL

### CORS

由 FastAPI 的 `CORSMiddleware` 處理，允許的來源完全由 `CORS_ORIGINS` 決定：

- 開發：預設 `http://localhost:5173,http://127.0.0.1:5173`。
- 正式：以環境變數設定實際網域，例如 `CORS_ORIGINS=https://citygap.example.gov.tw`。
- 不要使用 `*`。程式不會阻擋，但啟動時會印出警告；`*` 代表任何網站都能呼叫這個 API。
- 允許的方法只有 `GET, POST, OPTIONS`，不帶 credentials。

實測：帶 `Origin: http://localhost:5173` 的請求回應含 `access-control-allow-origin: http://localhost:5173`；其他 Origin 不會得到該 header。

### SSL（後端連政府主機）

Python 3.13 預設啟用嚴格 X.509 驗證（`VERIFY_X509_STRICT`），會拒絕 data.taipei、stats.moe.gov.tw、ltcpap.mohw.gov.tw、tgos.tw 的憑證鏈（缺少 Subject Key Identifier）。`SSL_STRICT_X509=false`（預設）只關閉這個嚴格旗標，CA 鏈與主機名稱驗證仍然啟用。

---

## 10. Production deployment

1. **後端**：設定 `backend/.env`（至少 `CORS_ORIGINS`、必要時 `DATABASE_URL`），以 `uvicorn app.main:app --host 0.0.0.0 --port 8000`（或 gunicorn + uvicorn worker）啟動。SQLite 檔案所在目錄需可寫。
2. **前端**：`VITE_API_BASE_URL=https://api.example.gov.tw npm run build`，把 `dist/` 交給任何靜態網站主機。若前後端同網域，可不設定 `VITE_API_BASE_URL`，改由反向代理把 `/api/*` 轉到 FastAPI（此時 CORS 也不需要跨網域設定）。
3. **資料更新**：後端每次啟動會自動同步；也可由排程呼叫 `POST /api/sync`。
4. **Docker**：`docker compose up --build` 一次啟動前端（nginx）與後端，設定與資料保存方式見第 13 節；正式環境把 `CORS_ORIGINS` 換成實際網域即可。
5. **不在本次範圍**：Redis、PostGIS、認證、Kubernetes。SQLite 足以應付目前約 4,000 筆資料。

---

## 11. 目前已知限制

- **幼兒園沒有座標。** 教育部幼兒園名錄只有地址；臺北市「各級學校分布圖」與 NLSC「各級學校範圍圖」都不含幼兒園；全國教保資訊網有地圖查詢但沒有公開座標資料集；TGOS 地址定位服務需申請帳號。658 筆幼兒園已入庫、可搜尋、可統計，但不會出現在地圖上。找到官方座標來源後，只需在後端新增一個 geometry 來源與對應規則。
- **5 所國小對應不到 NLSC 多邊形**：國立臺北教大實小、市立和平實驗國小、市立長安國小、國立政大實小、私立再興小學（NLSC 圖資中沒有獨立的學校區塊或命名不同）。這些維持 missing。
- **長照 28 筆缺座標**：官方資料本身沒有提供經緯度（多為藥局類 B 單位）。
- **醫院 / 診所沒有電話**：臺北市衛生局的這份資料沒有電話欄位。
- 醫院 / 診所沒有官方代碼，`external_id` 以名稱 + 地址雜湊；名稱或地址一旦更動會被視為新資料（舊資料刪除、新資料新增）。
- 教育部名錄的「學年度」以檔案內最新年度為準，若教育部同一檔案混有下一學年度的預告資料，會以較新者為準。
- 本版本不做 Gap Analysis、人口分析、Coverage 顯示；`src/utils/coverage.js` 與 `CoverageLayer.jsx` 仍是預留接口（呼叫分析函式會拋出 NotImplementedError）。

---

## 12. 專案結構

```
backend/
├─ app/
│  ├─ main.py                 FastAPI app、CORS、啟動流程
│  ├─ config.py               pydantic-settings、分類 label
│  ├─ database.py             SQLAlchemy engine / session、自動建表
│  ├─ models/                 facility.py、data_source.py、sync_log.py
│  ├─ schemas/                facility.py、source.py（API contract）
│  ├─ routers/                health.py、facilities.py、sources.py、sync.py
│  └─ services/
│     ├─ source_registry.py   官方資料來源定義
│     ├─ fetcher.py           httpx 下載、SSL、重試、快取
│     ├─ csv_parser.py        解碼與 CSV 解析
│     ├─ normalizer.py        各來源 → 統一格式、座標驗證、去重
│     ├─ school_geometry.py   NLSC 學校範圍圖 → 中心點索引與名稱對應
│     └─ sync_service.py      同步流程、upsert、sync_logs
├─ tests/                     pytest（82 tests）
├─ requirements.txt
├─ .env.example
└─ README.md

src/
├─ services/backendApi.js     後端 API client（前端唯一資料來源）
├─ hooks/useFacilities.js     載入 /api/facilities + /api/sources + /api/categories，同步中自動輪詢
├─ utils/normalizeFacility.js 後端欄位 → 前端統一格式、座標防呆
├─ utils/facilityFilter.js    搜尋索引、篩選、分類計數
├─ utils/geo.js               座標驗證、Haversine
├─ utils/coverage.js          V2 / V3 預留接口
├─ config/categories.js       分類 label / 顏色 / 服務半徑（UI 權威來源）
└─ components/
   ├─ Map/                    FacilityMap、FacilityMarker、CoverageLayer
   ├─ Sidebar/                Sidebar、SearchBar、CategoryFilter、Statistics
   ├─ Facility/FacilityPopup  名稱 / 類別 / 地址 / 電話 + 資料來源追溯
   └─ Status/DataStatus       載入中 / 同步中 / 錯誤 / 部分失敗
```

Docker 相關檔案（專案根目錄）：

```
Dockerfile            前端 image：node:22-alpine build → nginx:1.27-alpine
docker/nginx.conf     nginx：靜態檔 + /api、/docs、/openapi.json 反向代理到 backend container
docker-compose.yml    backend + frontend 兩個 service、port、healthcheck、bind mount
.dockerignore         前端 build context 排除 node_modules、dist、backend、.git 等
backend/Dockerfile    後端 image：python:3.13-slim + requirements.txt，uvicorn 0.0.0.0:8000
backend/.dockerignore 排除 .venv、data、.env、__pycache__
.env.example          根目錄環境變數範例（Vite 與 docker compose 共用）
```

前端測試：`npm test`（Vitest，35 tests）。後端測試：`cd backend && python -m pytest`（82 tests）。

---

## 13. Docker 使用方式

適合 demo / 展示：一個指令同時啟動前端、後端與 SQLite，宿主機不需要安裝 Python 或 Node。

### 前置需求

1. 安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 需啟用 WSL 2 後端），啟動後等到工作列圖示顯示 Engine running。
2. 確認宿主機的 8000 與 3000 沒有被其他程式或 container 占用（衝突處理見下方）。

### 指令

啟動（前景執行，第一次會 build image，約 1 到 3 分鐘）：

```bash
docker compose up --build
```

背景執行：

```bash
docker compose up -d --build
```

查看狀態（兩個 service 都應顯示 `healthy`）：

```bash
docker compose ps
```

查看 logs：

```bash
docker compose logs -f
```

只看後端（可看到政府資料同步進度）：

```bash
docker compose logs -f backend
```

停止並移除 container（資料保留）：

```bash
docker compose down
```

重新 build（不用 cache）：

```bash
docker compose build --no-cache
```

### 網址

| 服務 | 網址 |
| --- | --- |
| Frontend | <http://localhost:3000> |
| Backend | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs>（<http://localhost:3000/docs> 也可） |
| Health | <http://localhost:8000/api/health> |
| Sync status | <http://localhost:8000/api/sync/status> |

### Compose 架構

| service | image | 說明 |
| --- | --- | --- |
| `backend` | `python:3.13-slim` + `requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port 8000`（無 reload）；啟動時背景同步政府資料，不阻塞 API；healthcheck 每 15 秒打 `/api/health` |
| `frontend` | `node:22-alpine`（`npm ci` + `npm run build`）→ `nginx:1.27-alpine` | nginx 提供 `dist/`，並把 `/api/`、`/docs`、`/redoc`、`/openapi.json` 轉給 `http://backend:8000`；`depends_on: backend: condition: service_healthy` |

SQLite 不需要獨立 container。

### SQLite 資料保存位置

`./backend/data` 以 bind mount 掛到 backend container 的 `/app/data`：

- `backend/data/citygap.db`：資料庫（與本機直接跑 uvicorn 時是同一個檔案，兩種方式共用資料）
- `backend/data/cache/`：NLSC 學校範圍圖的下載快取

`docker compose down` 再 `docker compose up --build` 之後資料仍在（已實測：3,773 筆、6 個來源狀態完整保留）。要重建資料庫，刪除 `citygap.db` 後重新啟動即可；備份就是複製這個檔案。

### 前端 API 位址與 CORS

- 前端 API 位址是 Vite **build-time** 變數（`import.meta.env.VITE_API_BASE_URL`），在瀏覽器端 fetch 使用。Docker build 預設把它設為空字串，所以瀏覽器打的是**同源** `http://localhost:3000/api/...`，由 nginx 在 Docker network 內轉給 `backend:8000`。這樣 JS bundle 不會寫死宿主機的 host:port，也不需要跨網域 CORS。
- backend container 的 `CORS_ORIGINS` 預設允許 `http://localhost:3000`、`5173`、`5174`（含 `127.0.0.1`），讓本機 `npm run dev` 也能直接呼叫 Docker 後端；沒有使用 `*`。
- 要覆寫設定，在專案根目錄建立 `.env`（範例見 `.env.example`，已 gitignore），例如 `CORS_ORIGINS=...`、`SYNC_ON_STARTUP=false`、`VITE_API_BASE_URL=http://localhost:8000`（改成讓瀏覽器直接打後端）。

### Port 衝突

啟動時出現 `Bind for 0.0.0.0:8000 failed: port is already allocated`，表示 8000 被其他程式或 container 占用（用 `docker ps` 與 `netstat -ano | findstr :8000` 查看）。

- 解法一：停掉占用者，例如 `docker stop <container 名稱>`。
- 解法二：在根目錄 `.env` 設 `BACKEND_PORT=8001`（或 `FRONTEND_PORT=3001`）再 `docker compose up -d`。container 內 port 不變，前端經 nginx 仍能正常連到後端，只是 Swagger 改在 `http://localhost:8001/docs`。

### 除錯

```bash
docker compose logs backend
```

```bash
docker compose exec backend python -c "import pyproj; print(pyproj.__version__)"
```

```bash
docker compose exec backend python -m pytest
```

```bash
docker compose exec backend bash
```

```bash
docker compose exec frontend sh
```

### 本機 npm run dev 搭配 Docker 後端

只啟動後端 container，前端用 Vite dev server：

```bash
docker compose up -d backend
```

```bash
npm run dev
```

前端 dev 預設連 `http://localhost:8000`，`CORS_ORIGINS` 預設已包含 5173 / 5174。
