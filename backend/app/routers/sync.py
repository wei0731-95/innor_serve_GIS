from fastapi import APIRouter, HTTPException

from ..schemas import SyncRunOut, SyncStatusOut
from ..services import sync_service
from ..services.sync_service import SyncAlreadyRunning

router = APIRouter(prefix="/api", tags=["sync"])


@router.get("/sync/status", response_model=SyncStatusOut)
def sync_status():
    last = sync_service.state.last_run
    return SyncStatusOut(
        running=sync_service.state.running,
        last_run_started_at=last.started_at if last else sync_service.state.current_started_at,
        last_run_completed_at=last.completed_at if last else None,
        last_run_success_count=last.success_count if last else None,
        last_run_error_count=last.error_count if last else None,
    )


@router.post("/sync", response_model=SyncRunOut)
def sync_all_sources():
    """手動重新同步所有啟用的政府資料來源（同步執行，回傳每個來源的結果）。"""
    try:
        return sync_service.sync_all()
    except SyncAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sync/{source_id}", response_model=SyncRunOut)
def sync_single_source(source_id: str):
    """重新同步單一資料來源。教育部學校名錄會連同 NLSC 座標來源一起同步。"""
    try:
        return sync_service.sync_one(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到資料來源：{source_id}")
    except SyncAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
