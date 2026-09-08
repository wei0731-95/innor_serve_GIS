"""下載政府開放資料（httpx）：逾時、重試、SSL 設定與本機快取。

只負責「取得位元組」，不做解析。所有錯誤統一包成 FetchError，讓 sync_service 記進 sync_logs。
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from ..config import get_settings
from ..database import utcnow

log = logging.getLogger(__name__)

USER_AGENT = "CityGap-Taipei-Facility-Backend/0.2 (+https://github.com/citygap)"


class FetchError(Exception):
    """下載失敗（逾時、網路錯誤、HTTP 非 200）。"""

    def __init__(self, message: str, *, url: str | None = None, status_code: int | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.cause = cause


@dataclass
class FetchResult:
    url: str
    content: bytes
    content_type: str | None
    status_code: int
    fetched_at: datetime
    from_cache: bool = False

    @property
    def size(self) -> int:
        return len(self.content)


def build_ssl_context(strict: bool | None = None) -> ssl.SSLContext:
    """系統 / certifi CA + 主機名稱驗證照常，只依設定決定是否關閉 Python 3.13 的 VERIFY_X509_STRICT。

    台灣政府主機（data.taipei、stats.moe.gov.tw、ltcpap.mohw.gov.tw、tgos.tw）的憑證鏈缺少
    Subject Key Identifier，嚴格模式會直接拒絕連線。
    """
    if strict is None:
        strict = get_settings().ssl_strict_x509
    context = ssl.create_default_context()
    if not strict:
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def fetch_bytes(url: str, *, timeout: float | None = None, retries: int | None = None) -> FetchResult:
    """下載單一 URL。5xx / 逾時 / 網路錯誤會重試，4xx 不重試。"""
    settings = get_settings()
    timeout = settings.http_timeout_seconds if timeout is None else timeout
    retries = settings.http_max_retries if retries is None else retries
    attempts = retries + 1
    last_error: FetchError | None = None

    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(
                verify=build_ssl_context(),
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
        except httpx.TimeoutException as exc:
            last_error = FetchError(f"下載逾時（{timeout:g} 秒）：{url}", url=url, cause=exc)
        except httpx.HTTPError as exc:
            last_error = FetchError(f"網路錯誤：{exc.__class__.__name__}: {exc}", url=url, cause=exc)
        else:
            if response.status_code == 200:
                return FetchResult(
                    url=url,
                    content=response.content,
                    content_type=response.headers.get("content-type"),
                    status_code=response.status_code,
                    fetched_at=utcnow(),
                )
            last_error = FetchError(
                f"HTTP {response.status_code}：{url}", url=url, status_code=response.status_code
            )
            if response.status_code < 500:
                raise last_error

        if attempt < attempts:
            wait = attempt * 2
            log.warning("fetch attempt %d/%d failed (%s); retrying in %ds", attempt, attempts, last_error, wait)
            time.sleep(wait)

    assert last_error is not None
    raise last_error


def fetch_first_available(urls: list[str] | tuple[str, ...], **kwargs) -> FetchResult:
    """依序嘗試多個候選 URL（例如教育部依學年度分檔）。只有 404 才換下一個，其他錯誤直接拋出。"""
    if not urls:
        raise FetchError("沒有可用的下載 URL")
    last_error: FetchError | None = None
    for url in urls:
        try:
            return fetch_bytes(url, **kwargs)
        except FetchError as exc:
            if exc.status_code == 404:
                log.info("URL not found, trying next candidate: %s", url)
                last_error = exc
                continue
            raise
    assert last_error is not None
    raise FetchError(f"所有候選 URL 都回應 404：{', '.join(urls)}", url=urls[-1], status_code=404, cause=last_error)


# ---------------------------------------------------------------------------
# 本機快取：只保存「真的從政府主機下載過」的檔案，供大型輔助資料（NLSC 學校範圍圖）
# 在主機暫時無法連線時沿用上一份官方資料。使用快取時 sync_log 會明確記錄。
# ---------------------------------------------------------------------------


def _cache_paths(url: str) -> tuple[Path, Path]:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cache_dir = get_settings().cache_path
    return cache_dir / f"{digest}.bin", cache_dir / f"{digest}.meta.json"


def save_cache(result: FetchResult) -> None:
    data_path, meta_path = _cache_paths(result.url)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_bytes(result.content)
    meta_path.write_text(
        json.dumps(
            {
                "url": result.url,
                "content_type": result.content_type,
                "fetched_at": result.fetched_at.isoformat(),
                "size": result.size,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_cache(url: str) -> FetchResult | None:
    data_path, meta_path = _cache_paths(url)
    if not data_path.exists() or not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return FetchResult(
        url=url,
        content=data_path.read_bytes(),
        content_type=meta.get("content_type"),
        status_code=200,
        fetched_at=datetime.fromisoformat(meta["fetched_at"]),
        from_cache=True,
    )
