"""資料來源、同步、健康檢查的 API 回應格式。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .facility import UtcDateTime


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    organization: str
    category: str | None = None
    kind: str
    url: str
    dataset_url: str | None = None
    format: str
    encoding: str | None = None
    description: str | None = None
    enabled: bool
    last_synced_at: UtcDateTime = None
    last_success_at: UtcDateTime = None
    last_status: str
    last_error: str | None = None
    record_count: int
    skipped_count: int
    missing_coordinate_count: int


class SyncLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str
    started_at: UtcDateTime = None
    completed_at: UtcDateTime = None
    status: str
    fetched_count: int
    inserted_count: int
    updated_count: int
    deleted_count: int
    skipped_count: int
    missing_coordinate_count: int
    error_message: str | None = None
    detail: str | None = None


class SyncResultOut(BaseModel):
    source_id: str
    source_name: str
    status: str
    message: str | None = None
    log: SyncLogOut | None = None


class SyncRunOut(BaseModel):
    started_at: UtcDateTime = None
    completed_at: UtcDateTime = None
    success_count: int
    error_count: int
    results: list[SyncResultOut]


class SyncStatusOut(BaseModel):
    running: bool
    last_run_started_at: UtcDateTime = None
    last_run_completed_at: UtcDateTime = None
    last_run_success_count: int | None = None
    last_run_error_count: int | None = None


class HealthOut(BaseModel):
    status: str
    database: str
    version: str
    facility_count: int
    sync_running: bool
