"""同步流程：

    source → fetch → decode → parse → validate → normalize → deduplicate
           → (座標補足：NLSC 學校範圍圖) → upsert DB → sync_log

規則：
- 每個來源各自一個 transaction；任一來源失敗不影響其他來源，也不會讓既有資料消失。
- 成功或失敗都寫 sync_logs，並更新 data_sources 的最近狀態。
- 來源沒有任何可用資料（空資料集）視為失敗，保留 DB 內舊資料。
- 絕不在失敗時填入假資料。
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import session_scope, utcnow
from ..models import DataSource, Facility, SyncLog
from ..models.facility import COORDINATE_OK
from ..models.sync_log import SYNC_ERROR, SYNC_RUNNING, SYNC_SUCCESS
from ..schemas.source import SyncLogOut, SyncResultOut, SyncRunOut
from .csv_parser import decode_bytes, parse_csv
from .fetcher import FetchError, FetchResult, fetch_first_available, load_cache, save_cache
from .normalizer import NormalizeResult, get_normalizer
from .school_geometry import COORDINATE_LEVEL_GEOMETRY, GEOMETRY_SOURCE_LABEL, SchoolGeometryIndex, build_index_from_zip
from .source_registry import KIND_FACILITY, KIND_GEOMETRY, SOURCE_DEFINITIONS, SourceDefinition, enabled_sources, get_source_definition

log = logging.getLogger(__name__)

# 下載函式型別：接受候選 URL tuple，回傳 FetchResult。測試會注入假的 fetcher。
Fetcher = Callable[[tuple[str, ...]], FetchResult]

MAX_ERROR_LENGTH = 2000


class SyncAlreadyRunning(Exception):
    """同一時間只允許一個同步流程。"""


class SyncError(Exception):
    """單一來源同步失敗（已寫入 sync_logs）。"""


class SyncState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_run: SyncRunOut | None = None
        self.current_started_at: datetime | None = None

    @property
    def running(self) -> bool:
        return self.lock.locked()


state = SyncState()


# ---------------------------------------------------------------------------
# data_sources 初始化
# ---------------------------------------------------------------------------


def ensure_sources(session: Session) -> None:
    """依 SOURCE_DEFINITIONS 建立或更新 data_sources 的靜態欄位；同步統計欄位保留。"""
    for definition in SOURCE_DEFINITIONS:
        source = session.get(DataSource, definition.id)
        if source is None:
            source = DataSource(id=definition.id, url=definition.primary_url)
            session.add(source)
        source.name = definition.name
        source.organization = definition.organization
        source.category = definition.category
        source.kind = definition.kind
        source.dataset_url = definition.dataset_url
        source.format = definition.format
        source.encoding = definition.encoding
        source.description = definition.description
        source.enabled = definition.enabled
        if not source.url:
            source.url = definition.primary_url
    session.commit()


# ---------------------------------------------------------------------------
# 共用：sync_log 開始 / 失敗
# ---------------------------------------------------------------------------


def _start_log(session: Session, source: DataSource) -> SyncLog:
    sync_log = SyncLog(source_id=source.id, status=SYNC_RUNNING, started_at=utcnow())
    source.last_status = SYNC_RUNNING
    source.last_synced_at = sync_log.started_at
    session.add(sync_log)
    session.commit()
    return sync_log


def _finish_error(session: Session, source_id: str, log_id: int, message: str) -> SyncLog:
    """回滾這個來源的所有變更（既有資料保留），並把錯誤寫進 sync_logs / data_sources。"""
    session.rollback()
    source = session.get(DataSource, source_id)
    sync_log = session.get(SyncLog, log_id)
    message = message[:MAX_ERROR_LENGTH]
    now = utcnow()
    if sync_log is not None:
        sync_log.status = SYNC_ERROR
        sync_log.completed_at = now
        sync_log.error_message = message
    if source is not None:
        source.last_status = SYNC_ERROR
        source.last_error = message
        source.last_synced_at = now
    session.commit()
    return sync_log


def _describe(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


# ---------------------------------------------------------------------------
# 座標補足（教育部名錄 → NLSC 學校範圍圖）
# ---------------------------------------------------------------------------


def enrich_coordinates(normalized: NormalizeResult, index: SchoolGeometryIndex | None) -> dict:
    stats = {"index_available": index is not None, "matched": 0, "unmatched": 0, "unmatched_names": []}
    if index is None:
        stats["unmatched"] = normalized.missing_coordinate_count
        return stats
    for facility in normalized.facilities:
        if facility.coordinate_status == COORDINATE_OK:
            continue
        point = index.match(facility.match_name or facility.name, facility.is_private)
        if point is None:
            stats["unmatched"] += 1
            if len(stats["unmatched_names"]) < 50:
                stats["unmatched_names"].append(facility.name)
            continue
        facility.lat = point.lat
        facility.lng = point.lng
        facility.coordinate_status = COORDINATE_OK
        facility.coordinate_level = COORDINATE_LEVEL_GEOMETRY
        facility.coordinate_source = f"{GEOMETRY_SOURCE_LABEL}：{point.name}（圖資 {point.yyyymm}）"
        stats["matched"] += 1
    return stats


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

_FACILITY_FIELDS = (
    "name",
    "category",
    "address",
    "phone",
    "district",
    "lat",
    "lng",
    "coordinate_status",
    "coordinate_level",
    "coordinate_source",
    "external_type",
    "raw_updated_at",
)


def upsert_facilities(session: Session, source: DataSource, normalized: NormalizeResult) -> dict[str, int]:
    """以 (source_id, external_id) 為鍵：新增 / 更新有變動的欄位 / 移除來源中已消失的資料。"""
    existing = {
        facility.external_id: facility
        for facility in session.scalars(select(Facility).where(Facility.source_id == source.id))
    }
    counts = {"inserted": 0, "updated": 0, "deleted": 0, "unchanged": 0}
    now = utcnow()

    for item in normalized.facilities:
        values = {field_name: getattr(item, field_name) for field_name in _FACILITY_FIELDS}
        values["source_name"] = source.name
        values["source_url"] = source.dataset_url
        values["raw_json"] = item.raw_json

        current = existing.pop(item.external_id, None)
        if current is None:
            session.add(
                Facility(
                    id=f"{source.id}:{item.external_id}",
                    source_id=source.id,
                    external_id=item.external_id,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
            )
            counts["inserted"] += 1
            continue

        changed = False
        for field_name, value in values.items():
            if getattr(current, field_name) != value:
                setattr(current, field_name, value)
                changed = True
        if changed:
            current.updated_at = now
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1

    for stale in existing.values():
        session.delete(stale)
        counts["deleted"] += 1

    session.flush()
    return counts


# ---------------------------------------------------------------------------
# 單一來源同步
# ---------------------------------------------------------------------------


def sync_geometry_source(session: Session, definition: SourceDefinition, fetcher: Fetcher = fetch_first_available) -> tuple[SchoolGeometryIndex, SyncLog]:
    """下載 NLSC 學校範圍圖並建立索引。主機暫時無法連線時沿用上次下載的官方檔案（會明確記錄）。"""
    source = session.get(DataSource, definition.id)
    sync_log = _start_log(session, source)
    try:
        download_error: str | None = None
        try:
            result = fetcher(definition.urls)
            save_cache(result)
        except FetchError as exc:
            cached = load_cache(definition.primary_url)
            if cached is None:
                raise
            download_error = _describe(exc)
            log.warning("geometry download failed (%s); using cached copy fetched at %s", exc, cached.fetched_at)
            result = cached

        index = build_index_from_zip(result.content)

        now = utcnow()
        sync_log.status = SYNC_SUCCESS
        sync_log.completed_at = now
        sync_log.fetched_count = len(index)
        sync_log.detail = json.dumps(
            {
                "url": result.url,
                "bytes": result.size,
                "from_cache": result.from_cache,
                "file_fetched_at": result.fetched_at.isoformat(),
                "download_error": download_error,
                "taipei_polygons": len(index),
            },
            ensure_ascii=False,
        )
        source.last_status = SYNC_SUCCESS
        source.last_success_at = now
        source.last_synced_at = now
        source.last_error = (
            f"本次下載失敗（{download_error}），沿用 {result.fetched_at.isoformat()} 下載的官方檔案"
            if download_error
            else None
        )
        source.record_count = len(index)
        source.url = result.url
        session.commit()
        return index, sync_log
    except Exception as exc:  # noqa: BLE001 - 任何錯誤都要寫進 sync_logs
        message = _describe(exc)
        log.error("geometry source %s failed: %s", definition.id, message)
        _finish_error(session, definition.id, sync_log.id, message)
        raise SyncError(message) from exc


def sync_facility_source(
    session: Session,
    definition: SourceDefinition,
    geometry_index: SchoolGeometryIndex | None = None,
    fetcher: Fetcher = fetch_first_available,
) -> SyncLog:
    source = session.get(DataSource, definition.id)
    sync_log = _start_log(session, source)
    try:
        result = fetcher(definition.urls)
        text, encoding = decode_bytes(result.content, content_type=result.content_type, fallback_encoding=definition.encoding)
        rows, fields = parse_csv(text, required_fields=definition.required_fields)
        normalized = get_normalizer(definition.normalizer)(rows)

        geometry_stats = None
        if definition.coordinate_source_id:
            geometry_stats = enrich_coordinates(normalized, geometry_index)

        counts = upsert_facilities(session, source, normalized)

        now = utcnow()
        sync_log.status = SYNC_SUCCESS
        sync_log.completed_at = now
        sync_log.fetched_count = normalized.fetched_count
        sync_log.inserted_count = counts["inserted"]
        sync_log.updated_count = counts["updated"]
        sync_log.deleted_count = counts["deleted"]
        sync_log.skipped_count = normalized.skipped_count + normalized.duplicate_count
        sync_log.missing_coordinate_count = normalized.missing_coordinate_count
        sync_log.detail = json.dumps(
            {
                "url": result.url,
                "bytes": result.size,
                "content_type": result.content_type,
                "encoding": encoding,
                "fields": fields,
                "filtered_out": normalized.filtered_out_count,
                "duplicates_merged": normalized.duplicate_count,
                "skipped_reasons": dict(normalized.skipped_reasons),
                "unchanged": counts["unchanged"],
                "notes": normalized.notes,
                "geometry": geometry_stats,
            },
            ensure_ascii=False,
        )

        source.last_status = SYNC_SUCCESS
        source.last_success_at = now
        source.last_synced_at = now
        source.last_error = None
        source.record_count = len(normalized.facilities)
        source.skipped_count = sync_log.skipped_count
        source.missing_coordinate_count = sync_log.missing_coordinate_count
        source.url = result.url
        session.commit()
        log.info(
            "source %s synced: %d records (+%d ~%d -%d), skipped %d, missing coords %d",
            definition.id,
            source.record_count,
            counts["inserted"],
            counts["updated"],
            counts["deleted"],
            sync_log.skipped_count,
            sync_log.missing_coordinate_count,
        )
        return sync_log
    except Exception as exc:  # noqa: BLE001 - FetchError / ParseError / NormalizeError / DB 錯誤都要記錄
        message = _describe(exc)
        log.error("source %s failed: %s", definition.id, message)
        _finish_error(session, definition.id, sync_log.id, message)
        raise SyncError(message) from exc


# ---------------------------------------------------------------------------
# 整體同步
# ---------------------------------------------------------------------------


def _result_from_log(definition: SourceDefinition, sync_log: SyncLog | None, status: str, message: str | None = None) -> SyncResultOut:
    return SyncResultOut(
        source_id=definition.id,
        source_name=definition.name,
        status=status,
        message=message,
        log=SyncLogOut.model_validate(sync_log) if sync_log is not None else None,
    )


def _latest_log(session: Session, source_id: str) -> SyncLog | None:
    return session.scalars(
        select(SyncLog).where(SyncLog.source_id == source_id).order_by(SyncLog.id.desc()).limit(1)
    ).first()


def _run_definitions(definitions: list[SourceDefinition], fetcher: Fetcher) -> SyncRunOut:
    started_at = utcnow()
    results: list[SyncResultOut] = []
    geometry_indexes: dict[str, SchoolGeometryIndex] = {}

    with session_scope() as session:
        ensure_sources(session)

    # 先同步空間資料（座標來源），再同步設施來源
    ordered = [d for d in definitions if d.kind == KIND_GEOMETRY] + [d for d in definitions if d.kind == KIND_FACILITY]

    for definition in ordered:
        with session_scope() as session:
            try:
                if definition.kind == KIND_GEOMETRY:
                    index, sync_log = sync_geometry_source(session, definition, fetcher)
                    geometry_indexes[definition.id] = index
                else:
                    index = geometry_indexes.get(definition.coordinate_source_id) if definition.coordinate_source_id else None
                    sync_log = sync_facility_source(session, definition, index, fetcher)
                results.append(_result_from_log(definition, sync_log, SYNC_SUCCESS))
            except SyncError as exc:
                results.append(_result_from_log(definition, _latest_log(session, definition.id), SYNC_ERROR, str(exc)))
            except Exception as exc:  # noqa: BLE001 - 連寫 log 都失敗時也不能中斷其他來源
                log.exception("unexpected error while syncing %s", definition.id)
                results.append(_result_from_log(definition, None, SYNC_ERROR, _describe(exc)))

    run = SyncRunOut(
        started_at=started_at,
        completed_at=utcnow(),
        success_count=sum(1 for r in results if r.status == SYNC_SUCCESS),
        error_count=sum(1 for r in results if r.status != SYNC_SUCCESS),
        results=results,
    )
    return run


def _with_lock(runner: Callable[[], SyncRunOut]) -> SyncRunOut:
    if not state.lock.acquire(blocking=False):
        raise SyncAlreadyRunning("同步正在執行中")
    try:
        state.current_started_at = utcnow()
        run = runner()
        state.last_run = run
        return run
    finally:
        state.current_started_at = None
        state.lock.release()


def _resolve_fetcher(fetcher: Fetcher | None) -> Fetcher:
    # 在呼叫時才查模組屬性，讓測試可以 monkeypatch sync_service.fetch_first_available
    return fetcher if fetcher is not None else fetch_first_available


def sync_all(fetcher: Fetcher | None = None) -> SyncRunOut:
    """同步所有啟用的來源。"""
    resolved = _resolve_fetcher(fetcher)
    return _with_lock(lambda: _run_definitions(enabled_sources(), resolved))


def sync_one(source_id: str, fetcher: Fetcher | None = None) -> SyncRunOut:
    """同步單一來源；教育部學校名錄會連同其座標來源（NLSC）一起同步。"""
    definition = get_source_definition(source_id)
    if definition is None:
        raise KeyError(source_id)
    definitions = [definition]
    if definition.coordinate_source_id:
        dependency = get_source_definition(definition.coordinate_source_id)
        if dependency is not None:
            definitions.insert(0, dependency)
    resolved = _resolve_fetcher(fetcher)
    return _with_lock(lambda: _run_definitions(definitions, resolved))


def start_background_sync() -> threading.Thread:
    """啟動時在背景執行 sync_all，不阻擋 API 服務。"""

    def _run() -> None:
        try:
            run = sync_all()
            log.info("startup sync finished: %d ok, %d failed", run.success_count, run.error_count)
        except SyncAlreadyRunning:
            log.info("startup sync skipped: another sync is running")
        except Exception:  # noqa: BLE001
            log.exception("startup sync crashed")

    thread = threading.Thread(target=_run, name="citygap-startup-sync", daemon=True)
    thread.start()
    return thread
