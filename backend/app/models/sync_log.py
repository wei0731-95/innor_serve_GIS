"""sync_logs：每一次來源同步的紀錄（成功或失敗都會留下一筆）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from .data_source import DataSource

SYNC_RUNNING = "running"
SYNC_SUCCESS = "success"
SYNC_ERROR = "error"


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # running | success | error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SYNC_RUNNING)

    # 原始資料列數（篩選前）
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 來源中已消失、因此從 DB 移除的筆數
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 缺必要欄位 / 重複 / 無法標準化而被略過的筆數
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 已入庫但沒有可信座標、因此不會出現在地圖上的筆數
    missing_coordinate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 額外統計（JSON 字串），例如非臺北市被過濾的筆數、座標對應層級分布
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["DataSource"] = relationship(back_populates="sync_logs")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SyncLog {self.id} {self.source_id} {self.status}>"
