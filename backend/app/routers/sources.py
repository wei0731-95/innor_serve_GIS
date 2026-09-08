from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataSource, SyncLog
from ..schemas import SourceOut, SyncLogOut

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    """所有資料來源：機關、URL、啟用狀態、最近同步時間 / 狀態、筆數與略過筆數。"""
    sources = db.scalars(select(DataSource).order_by(DataSource.kind.desc(), DataSource.id)).all()
    return [SourceOut.model_validate(source) for source in sources]


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: str, db: Session = Depends(get_db)):
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"找不到資料來源：{source_id}")
    return SourceOut.model_validate(source)


@router.get("/sources/{source_id}/logs", response_model=list[SyncLogOut])
def list_source_logs(source_id: str, limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    if db.get(DataSource, source_id) is None:
        raise HTTPException(status_code=404, detail=f"找不到資料來源：{source_id}")
    logs = db.scalars(
        select(SyncLog).where(SyncLog.source_id == source_id).order_by(SyncLog.id.desc()).limit(limit)
    ).all()
    return [SyncLogOut.model_validate(entry) for entry in logs]
