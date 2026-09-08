from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..config import CATEGORY_KEYS, CATEGORY_LABELS
from ..database import get_db
from ..models import DataSource, Facility
from ..models.facility import COORDINATE_OK
from ..schemas import CategoryOut, CategorySourceStatus, FacilityListOut, FacilityOut
from ..services.source_registry import KIND_FACILITY

router = APIRouter(prefix="/api", tags=["facilities"])


def facility_to_out(facility: Facility) -> FacilityOut:
    source = facility.source
    return FacilityOut(
        id=facility.id,
        name=facility.name,
        category=facility.category,
        address=facility.address,
        phone=facility.phone,
        district=facility.district,
        lat=facility.lat,
        lng=facility.lng,
        coordinate_status=facility.coordinate_status,
        coordinate_level=facility.coordinate_level,
        coordinate_source=facility.coordinate_source,
        source=facility.source_name,
        source_id=facility.source_id,
        source_url=facility.source_url,
        source_organization=source.organization if source else None,
        source_download_url=source.url if source else None,
        source_synced_at=source.last_success_at if source else None,
        external_id=facility.external_id,
        external_type=facility.external_type,
        raw_updated_at=facility.raw_updated_at,
        updated_at=facility.updated_at,
    )


def _validate_category(category: str | None) -> str | None:
    if category is None or category == "":
        return None
    if category not in CATEGORY_KEYS:
        raise HTTPException(status_code=400, detail=f"未知的分類「{category}」，可用值：{', '.join(CATEGORY_KEYS)}")
    return category


@router.get("/facilities", response_model=FacilityListOut)
def list_facilities(
    category: str | None = Query(None, description="分類 key，例如 hospital、clinic、kindergarten"),
    search: str | None = Query(None, description="搜尋機構名稱或地址（「臺」「台」視為相同）"),
    district: str | None = Query(None, description="行政區，例如 大安區"),
    with_coordinates: bool = Query(False, description="true 時只回傳有可信座標的設施"),
    db: Session = Depends(get_db),
):
    category = _validate_category(category)

    stmt = select(Facility).options(joinedload(Facility.source)).order_by(Facility.category, Facility.name)
    if category:
        stmt = stmt.where(Facility.category == category)
    if district:
        name = district.strip()
        if name and not name.endswith("區"):
            name += "區"
        stmt = stmt.where(Facility.district == name)
    if search and search.strip():
        keyword = search.strip()
        variants = {keyword, keyword.replace("台", "臺"), keyword.replace("臺", "台")}
        conditions = []
        for variant in variants:
            pattern = f"%{variant}%"
            conditions.append(Facility.name.like(pattern))
            conditions.append(Facility.address.like(pattern))
        stmt = stmt.where(or_(*conditions))
    if with_coordinates:
        stmt = stmt.where(Facility.coordinate_status == COORDINATE_OK)

    items = db.scalars(stmt).all()
    return FacilityListOut(count=len(items), items=[facility_to_out(f) for f in items])


@router.get("/facilities/{facility_id}", response_model=FacilityOut)
def get_facility(facility_id: str, db: Session = Depends(get_db)):
    facility = db.scalars(
        select(Facility).options(joinedload(Facility.source)).where(Facility.id == facility_id)
    ).first()
    if facility is None:
        raise HTTPException(status_code=404, detail=f"找不到設施：{facility_id}")
    return facility_to_out(facility)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Facility.category, Facility.coordinate_status, func.count()).group_by(
            Facility.category, Facility.coordinate_status
        )
    ).all()
    totals: dict[str, dict[str, int]] = {key: {"total": 0, "ok": 0} for key in CATEGORY_KEYS}
    for category, status, count in rows:
        bucket = totals.setdefault(category, {"total": 0, "ok": 0})
        bucket["total"] += count
        if status == COORDINATE_OK:
            bucket["ok"] += count

    sources = db.scalars(select(DataSource).where(DataSource.kind == KIND_FACILITY).order_by(DataSource.id)).all()
    sources_by_category: dict[str, list[CategorySourceStatus]] = {}
    for source in sources:
        if not source.category:
            continue
        sources_by_category.setdefault(source.category, []).append(
            CategorySourceStatus(
                id=source.id,
                name=source.name,
                organization=source.organization,
                status=source.last_status,
                last_success_at=source.last_success_at,
                last_error=source.last_error,
                record_count=source.record_count,
            )
        )

    return [
        CategoryOut(
            category=key,
            label=CATEGORY_LABELS.get(key, key),
            count=totals[key]["total"],
            with_coordinates=totals[key]["ok"],
            missing_coordinates=totals[key]["total"] - totals[key]["ok"],
            sources=sources_by_category.get(key, []),
        )
        for key in CATEGORY_KEYS
    ]
