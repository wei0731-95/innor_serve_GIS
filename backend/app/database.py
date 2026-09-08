"""SQLAlchemy engine / session 管理。SQLite 檔案與資料表在第一次啟動時自動建立。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """資料庫一律存 naive UTC；輸出到 API 時再補上 UTC 時區（見 schemas）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _ensure_sqlite_directory(url: str) -> None:
    path = url.removeprefix("sqlite:///")
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def configure_database(url: str) -> Engine:
    """建立（或重新建立）engine。測試會用暫存 SQLite 呼叫這個函式。"""
    global _engine, _session_factory

    if _engine is not None:
        _engine.dispose()

    connect_args: dict = {}
    is_sqlite = url.startswith("sqlite")
    if is_sqlite:
        # 同步在背景執行緒進行、API 在其他執行緒讀取，所以要允許跨執行緒使用連線
        connect_args["check_same_thread"] = False
        _ensure_sqlite_directory(url)

    _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

    if is_sqlite:

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    log.info("database configured: %s", url)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        configure_database(get_settings().resolved_database_url)
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    """建立所有資料表（facilities / data_sources / sync_logs）。已存在的表不會被改動。"""
    from . import models  # noqa: F401  確保所有 model 已註冊到 Base.metadata

    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency。"""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
