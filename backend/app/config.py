"""應用程式設定：由環境變數或 backend/.env 讀入（pydantic-settings）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# 後端支援的分類 key 與顯示名稱。前端 config/categories.js 仍是 UI 顯示的權威來源，
# 這裡只用來讓 /api/categories 能回傳 label，並限制 facilities.category 的合法值。
CATEGORY_LABELS: dict[str, str] = {
    "hospital": "醫院",
    "clinic": "診所",
    "kindergarten": "幼兒園",
    "elementary_school": "國民小學",
    "junior_high_school": "國民中學",
    "long_term_care": "長期照顧",
}
CATEGORY_KEYS: tuple[str, ...] = tuple(CATEGORY_LABELS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CityGap Facility API"
    app_version: str = "0.2.0"

    # 相對路徑一律以 backend/ 為基準（見 resolved_database_url / cache_path）
    database_url: str = "sqlite:///./data/citygap.db"

    # 逗號分隔。開發預設允許 Vite dev server；正式環境請用環境變數覆寫成實際網域。
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    sync_on_startup: bool = True
    http_timeout_seconds: float = 90.0
    http_max_retries: int = 2

    # Python 3.13 預設的 VERIFY_X509_STRICT 會拒絕台灣政府主機的憑證鏈（缺 Subject Key Identifier）。
    # False 只關閉「嚴格」旗標，CA 鏈與主機名稱驗證仍然啟用。
    ssl_strict_x509: bool = False

    cache_dir: str = "./data/cache"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def cache_path(self) -> Path:
        return self.resolve_path(self.cache_dir)

    @property
    def resolved_database_url(self) -> str:
        """把 sqlite 相對路徑轉成以 backend/ 為基準的絕對路徑，避免因啟動目錄不同而建出多個 DB。"""
        prefix = "sqlite:///"
        url = self.database_url
        if not url.startswith(prefix) or url == "sqlite:///:memory:":
            return url
        raw_path = url[len(prefix) :]
        if Path(raw_path).is_absolute():
            return url
        return prefix + self.resolve_path(raw_path).as_posix()


@lru_cache
def get_settings() -> Settings:
    return Settings()
