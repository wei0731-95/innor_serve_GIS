"""設施與分類的 API 回應格式。政府來源的原始欄位不會直接暴露，統一走這裡定義的 contract。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


# 資料庫存 naive UTC，輸出時補上時區，前端 new Date() 才不會誤判成本地時間
UtcDateTime = Annotated[datetime | None, PlainSerializer(_serialize_utc, return_type=str | None)]


class FacilityOut(BaseModel):
    """標準化設施：{id, name, category, address, phone, lat, lng, source, source_url, source_id, updated_at} + 座標與來源追溯欄位。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    address: str | None = None
    phone: str | None = None
    district: str | None = None

    lat: float | None = None
    lng: float | None = None
    coordinate_status: str
    coordinate_level: int | None = None
    coordinate_source: str | None = None

    # 資料來源追溯
    source: str
    source_id: str
    source_url: str | None = None
    source_organization: str | None = None
    source_download_url: str | None = None
    source_synced_at: UtcDateTime = None

    external_id: str
    external_type: str | None = None
    raw_updated_at: str | None = None
    updated_at: UtcDateTime = None


class FacilityListOut(BaseModel):
    count: int
    items: list[FacilityOut]


class CategorySourceStatus(BaseModel):
    id: str
    name: str
    organization: str
    status: str
    last_success_at: UtcDateTime = None
    last_error: str | None = None
    record_count: int


class CategoryOut(BaseModel):
    category: str
    label: str
    count: int
    with_coordinates: int
    missing_coordinates: int
    sources: list[CategorySourceStatus]
