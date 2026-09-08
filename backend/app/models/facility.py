"""facilities：所有來源標準化後的設施資料（前端地圖的唯一資料來源）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from .data_source import DataSource

COORDINATE_OK = "ok"
COORDINATE_MISSING = "missing"


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        # 同一來源內 external_id 唯一，避免重複資料
        UniqueConstraint("source_id", "external_id", name="uq_facilities_source_external"),
        Index("ix_facilities_category_status", "category", "coordinate_status"),
    )

    # 穩定 id：f"{source_id}:{external_id}"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    # 只有 coordinate_status == "ok" 才會有值，也才會在地圖上出現
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ok | missing
    coordinate_status: Mapped[str] = mapped_column(String(20), nullable=False, default=COORDINATE_MISSING)
    # 1 = 官方資料直接提供 WGS84；2 = 由另一份官方空間資料對應；3 = 官方定位服務
    coordinate_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 座標的來源說明（例如「內政部國土測繪中心 各級學校範圍圖 多邊形中心點」）
    coordinate_source: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 來源內的穩定識別（學校代碼、機構代碼；沒有 id 的來源用名稱+地址的雜湊）
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # 來源內的原始類型（例如長照 A/B/C、公立/私立）
    external_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 來源提供的最後異動時間（原樣保存字串）
    raw_updated_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # 原始資料列（JSON 字串），一般 API 不回傳
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    source: Mapped["DataSource"] = relationship(back_populates="facilities")

    @property
    def has_coordinates(self) -> bool:
        return self.coordinate_status == COORDINATE_OK and self.lat is not None and self.lng is not None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Facility {self.id} {self.category} {self.name!r}>"
