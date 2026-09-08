"""FastAPI 進入點。

    uvicorn app.main:app --reload

啟動時：建立 SQLite / 資料表 → 初始化 data_sources → （預設）背景同步所有啟用的政府資料來源。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .config import Settings, get_settings
from .database import init_db, session_scope
from .routers import facilities, health, sources, sync
from .services.sync_service import ensure_sources, start_background_sync

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db()
        with session_scope() as session:
            ensure_sources(session)
        if settings.sync_on_startup:
            start_background_sync()
        else:
            log.info("SYNC_ON_STARTUP=false：不在啟動時同步，請用 POST /api/sync")
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "臺北市公共服務設施資料 API。所有設施資料皆來自政府開放資料，"
            "由後端下載、解析、標準化後存入 SQLite；每筆資料都可追溯到原始資料集。"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS：允許的來源完全由設定（環境變數 CORS_ORIGINS）決定，正式環境不要用 "*"。
    origins = settings.cors_origin_list
    if "*" in origins:
        log.warning("CORS_ORIGINS 包含 '*'：任何網站都能呼叫這個 API，正式環境不建議這樣設定")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(facilities.router)
    app.include_router(sources.router)
    app.include_router(sync.router)

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs", "api": "/api"}

    @app.get("/api/docs", include_in_schema=False)
    def api_docs_redirect():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
