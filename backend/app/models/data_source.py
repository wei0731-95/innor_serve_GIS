"""data_sources：每個政府資料來源的定義與最近同步狀態。

回答三個問題：這筆設施從哪來？什麼時候同步？同步是否成功？
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from .facility import Facility
    from .sync_log import SyncLog


class DataSource(Base):
    __tablename__ = "data_sources"

    # 穩定的字串 id，例如 taipei_hospital、moe_elementary（見 services/source_registry.py）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    # facility 來源對應一個分類；geometry（座標補足用的空間資料）為 None
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # facility | geometry
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="facility")
    # 實際下載 URL（政府主機）
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # 資料集說明頁（例如 data.gov.tw/dataset/xxx），提供給 Popup 做來源追溯
    dataset_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # never | running | success | error
    last_status: Mapped[str] = mapped_column(String(20), nullable=False, default="never")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_coordinate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    facilities: Mapped[list["Facility"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<DataSource {self.id} status={self.last_status} records={self.record_count}>"
