from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Facility
from ..schemas import HealthOut
from ..services import sync_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        facility_count = db.scalar(select(func.count()).select_from(Facility)) or 0
        database = "ok"
    except SQLAlchemyError:
        facility_count = 0
        database = "error"

    payload = HealthOut(
        status="ok" if database == "ok" else "degraded",
        database=database,
        version=settings.app_version,
        facility_count=facility_count,
        sync_running=sync_service.state.running,
    )
    if database != "ok":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
