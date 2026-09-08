# CityGap Facility Backend（FastAPI + SQLite）

臺北市公共服務設施資料的後端：下載政府開放資料 → 解析 → 清洗 → 標準化 → 存入 SQLite → 提供 REST API。
完整說明（架構、資料來源、同步流程、CORS、部署、已知限制）請見專案根目錄的 [README.md](../README.md)。

## 快速開始

用 Docker（在專案根目錄，連前端一起啟動）：

```bash
docker compose up --build
```

本機直接執行：

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 選用；預設值即可在本機開發
uvicorn app.main:app --reload
```

- Swagger UI：<http://localhost:8000/docs>
- 資料庫：`data/citygap.db`（第一次啟動自動建立，含 `facilities`、`data_sources`、`sync_logs`）
- 啟動後會在背景同步所有啟用的資料來源；也可 `POST /api/sync` 手動同步

## 測試

```bash
python -m pytest
```

測試使用暫存 SQLite 與假的下載函式（不連網），涵蓋 health / facilities / categories / sources / sync API、
標準化規則、座標驗證、去重、部分來源失敗、sync_logs 與來源 metadata。

## 目錄

```
app/
├─ main.py                 FastAPI app、CORS、lifespan（建表、初始化來源、背景同步）
├─ config.py               Settings（環境變數 / .env）、CATEGORY_LABELS
├─ database.py             engine / session、init_db()
├─ models/                 Facility、DataSource、SyncLog
├─ schemas/                FacilityOut、CategoryOut、SourceOut、SyncLogOut、SyncRunOut、HealthOut
├─ routers/                /api/health、/api/facilities、/api/categories、/api/sources、/api/sync
└─ services/
   ├─ source_registry.py   SOURCE_DEFINITIONS：所有官方資料來源
   ├─ fetcher.py           httpx 下載（逾時 / 重試 / SSL / 快取）
   ├─ csv_parser.py        decode_bytes()、parse_csv()
   ├─ normalizer.py        各來源 normalizer、座標驗證、去重、行政區對應
   ├─ school_geometry.py   NLSC 學校範圍圖 → 臺北市學校中心點索引、名稱對應
   └─ sync_service.py      sync_all() / sync_one()、upsert、sync_logs、背景同步
tests/
```

## 新增一個資料來源

1. 在 `services/source_registry.py` 的 `SOURCE_DEFINITIONS` 加一筆 `SourceDefinition`（URL、機關、分類、格式、編碼、必要欄位）。
2. 在 `services/normalizer.py` 寫對應的 normalizer，並登錄到 `NORMALIZERS`。
3. 若分類是新的，在 `config.py` 的 `CATEGORY_LABELS` 與前端 `src/config/categories.js` 加上 label。
4. 在 `tests/` 加上該來源的樣本列與測試。

規則不變：只用官方資料、座標無法確認就標記 missing、來源失敗就記錄錯誤，不補假資料。
