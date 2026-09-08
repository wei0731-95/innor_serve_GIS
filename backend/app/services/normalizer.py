"""把各政府來源的原始資料列標準化成同一個 NormalizedFacility。

規則（與前端原本的 normalizeFacility 概念一致，但改在後端執行）：
- 座標只接受官方資料直接提供的合法 WGS84 數值；無效 / 缺少就標記 missing，絕不推估。
- 只保留臺北市資料。
- external_id 必須穩定：優先用官方代碼，沒有代碼的來源用「名稱 + 地址」的雜湊。
- 重複的 external_id 以第一筆為準（deterministic）。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Callable

from ..models.facility import COORDINATE_MISSING, COORDINATE_OK

# 臺北市 12 行政區與內政部行政區代碼
TAIPEI_DISTRICTS: tuple[str, ...] = (
    "松山區", "信義區", "大安區", "中山區", "中正區", "大同區",
    "萬華區", "文山區", "南港區", "內湖區", "士林區", "北投區",
)
TAIPEI_DISTRICT_CODES: dict[str, str] = {
    "63000010": "松山區",
    "63000020": "信義區",
    "63000030": "大安區",
    "63000040": "中山區",
    "63000050": "中正區",
    "63000060": "大同區",
    "63000070": "萬華區",
    "63000080": "文山區",
    "63000090": "南港區",
    "63000100": "內湖區",
    "63000110": "士林區",
    "63000120": "北投區",
}
TAIPEI_CITY_CODE = "63000"

# 臺灣及離島大致範圍：官方座標若落在此範圈之外（例如經緯度顛倒、TWD97 公尺值誤填），視為無效
TAIWAN_BBOX = {"lat_min": 21.5, "lat_max": 26.5, "lng_min": 118.0, "lng_max": 122.5}

_NUMERIC_RE = re.compile(r"^[-+]?\d+(\.\d+)?$")
_DISTRICT_RE = re.compile(r"[臺台]北市\s*(" + "|".join(TAIPEI_DISTRICTS) + ")")
_POSTAL_PREFIX_RE = re.compile(r"^\[\d+\]\s*")
_WHITESPACE_RE = re.compile(r"[\s　]+")


class NormalizeError(Exception):
    """整批資料無法標準化（例如沒有任何臺北市資料）。"""


@dataclass
class NormalizedFacility:
    external_id: str
    name: str
    category: str
    address: str | None
    phone: str | None
    district: str | None
    lat: float | None
    lng: float | None
    coordinate_status: str
    coordinate_level: int | None
    coordinate_source: str | None
    external_type: str | None
    raw_updated_at: str | None
    raw: dict
    # 給 school_geometry 做名稱對應用
    match_name: str | None = None
    is_private: bool | None = None

    @property
    def raw_json(self) -> str:
        return json.dumps(self.raw, ensure_ascii=False, sort_keys=True)


@dataclass
class NormalizeResult:
    facilities: list[NormalizedFacility]
    fetched_count: int
    filtered_out_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    skipped_reasons: Counter = field(default_factory=Counter)
    notes: dict = field(default_factory=dict)

    @property
    def missing_coordinate_count(self) -> int:
        return sum(1 for f in self.facilities if f.coordinate_status != COORDINATE_OK)


# ---------------------------------------------------------------------------
# 共用工具
# ---------------------------------------------------------------------------


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def strip_postal_prefix(address: str) -> str:
    """教育部名錄地址格式：'[105]臺北市松山區…' → 去掉郵遞區號前綴。"""
    return _POSTAL_PREFIX_RE.sub("", address).strip()


def parse_coordinate(value: str | float | int | None) -> float | None:
    """只接受純數字字串或數值；'N/A'、空白、'25.03abc' 一律 None，不用 float() 部分解析。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text or not _NUMERIC_RE.match(text):
            return None
        number = float(text)
    return number if math.isfinite(number) else None


def is_valid_latlng(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return False
    if lat == 0.0 and lng == 0.0:
        return False
    return (
        TAIWAN_BBOX["lat_min"] <= lat <= TAIWAN_BBOX["lat_max"]
        and TAIWAN_BBOX["lng_min"] <= lng <= TAIWAN_BBOX["lng_max"]
    )


def extract_district(address: str | None, district_code: str | None = None, district_name: str | None = None) -> str | None:
    """行政區優先取來源提供的名稱，其次從地址文字解析，最後用行政區代碼對應。"""
    if district_name:
        name = clean_text(district_name)
        if name in TAIPEI_DISTRICTS:
            return name
    if address:
        match = _DISTRICT_RE.search(address)
        if match:
            return match.group(1)
    if district_code:
        return TAIPEI_DISTRICT_CODES.get(clean_text(district_code))
    return None


def stable_hash(*parts: str) -> str:
    joined = "|".join(clean_text(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def is_taipei_address(address: str | None) -> bool:
    return bool(address) and ("臺北市" in address or "台北市" in address)


def deduplicate(facilities: list[NormalizedFacility]) -> tuple[list[NormalizedFacility], int]:
    """同一 external_id 只保留第一筆（deterministic）。"""
    unique: "OrderedDict[str, NormalizedFacility]" = OrderedDict()
    duplicates = 0
    for facility in facilities:
        if facility.external_id in unique:
            duplicates += 1
            continue
        unique[facility.external_id] = facility
    return list(unique.values()), duplicates


def _coordinate_fields(lat_raw: str | None, lng_raw: str | None, source_label: str) -> dict:
    lat = parse_coordinate(lat_raw)
    lng = parse_coordinate(lng_raw)
    if is_valid_latlng(lat, lng):
        return {
            "lat": lat,
            "lng": lng,
            "coordinate_status": COORDINATE_OK,
            "coordinate_level": 1,
            "coordinate_source": source_label,
        }
    return {
        "lat": None,
        "lng": None,
        "coordinate_status": COORDINATE_MISSING,
        "coordinate_level": None,
        "coordinate_source": None,
    }


# ---------------------------------------------------------------------------
# 臺北市政府衛生局：醫院 / 診所
# ---------------------------------------------------------------------------

_TAIPEI_HEALTH_COORD_LABEL = "臺北市政府衛生局「臺北市公私立醫療院所」提供之 WGS84 經緯度"


def _normalize_taipei_health(rows: list[dict], category: str) -> NormalizeResult:
    result = NormalizeResult(facilities=[], fetched_count=len(rows))
    for row in rows:
        name = clean_text(row.get("機構名稱"))
        address = clean_text(row.get("地址")) or None
        if not name:
            result.skipped_count += 1
            result.skipped_reasons["missing_name"] += 1
            continue
        district_code = row.get("行政區域代碼") or row.get("行政區")
        result.facilities.append(
            NormalizedFacility(
                external_id=stable_hash(name, address or ""),
                name=name,
                category=category,
                address=address,
                phone=clean_text(row.get("電話")) or None,
                district=extract_district(address, district_code),
                external_type=clean_text(row.get("分類")) or None,
                raw_updated_at=None,
                raw=row,
                **_coordinate_fields(row.get("緯度"), row.get("經度"), _TAIPEI_HEALTH_COORD_LABEL),
            )
        )
    result.facilities, result.duplicate_count = deduplicate(result.facilities)
    if not result.facilities:
        raise NormalizeError("來源沒有任何可用的資料列")
    return result


def normalize_taipei_hospital(rows: list[dict]) -> NormalizeResult:
    return _normalize_taipei_health(rows, "hospital")


def normalize_taipei_clinic(rows: list[dict]) -> NormalizeResult:
    return _normalize_taipei_health(rows, "clinic")


# ---------------------------------------------------------------------------
# 教育部統計處：幼兒園 / 國小 / 國中名錄（只有地址，沒有座標）
# ---------------------------------------------------------------------------


def latest_school_year(rows: list[dict]) -> str | None:
    years = [clean_text(r.get("學年度")) for r in rows]
    years = [y for y in years if y.isdigit()]
    return max(years, key=int) if years else None


def _normalize_moe_school(rows: list[dict], category: str) -> NormalizeResult:
    result = NormalizeResult(facilities=[], fetched_count=len(rows))
    year = latest_school_year(rows)
    if year is None:
        raise NormalizeError("教育部名錄沒有可辨識的學年度欄位")
    result.notes["school_year"] = year

    for row in rows:
        if clean_text(row.get("學年度")) != year:
            result.filtered_out_count += 1
            continue
        city = clean_text(row.get("縣市名稱"))
        if "臺北市" not in city and "台北市" not in city:
            result.filtered_out_count += 1
            continue
        code = clean_text(row.get("代碼"))
        name = clean_text(row.get("學校名稱"))
        if not code or not name:
            result.skipped_count += 1
            result.skipped_reasons["missing_code_or_name"] += 1
            continue
        address = strip_postal_prefix(clean_text(row.get("地址"))) or None
        public_private = clean_text(row.get("公/私立")) or None
        result.facilities.append(
            NormalizedFacility(
                external_id=code,
                name=name,
                category=category,
                address=address,
                phone=clean_text(row.get("電話")) or None,
                district=extract_district(address, district_name=row.get("鄉鎮市區名稱")),
                lat=None,
                lng=None,
                coordinate_status=COORDINATE_MISSING,
                coordinate_level=None,
                coordinate_source=None,
                external_type=public_private,
                raw_updated_at=f"{year}學年度",
                raw=row,
                match_name=name,
                is_private=(public_private == "私立") if public_private else None,
            )
        )
    result.facilities, result.duplicate_count = deduplicate(result.facilities)
    if not result.facilities:
        raise NormalizeError(f"教育部名錄 {year} 學年度沒有任何臺北市資料")
    return result


def normalize_moe_kindergarten(rows: list[dict]) -> NormalizeResult:
    return _normalize_moe_school(rows, "kindergarten")


def normalize_moe_elementary(rows: list[dict]) -> NormalizeResult:
    return _normalize_moe_school(rows, "elementary_school")


def normalize_moe_junior_high(rows: list[dict]) -> NormalizeResult:
    return _normalize_moe_school(rows, "junior_high_school")


# ---------------------------------------------------------------------------
# 衛生福利部：長照 ABC 據點（全國、含座標、同一機構多筆特約服務）
# ---------------------------------------------------------------------------

_MOHW_COORD_LABEL = "衛生福利部「長照ABC據點」提供之 WGS84 經緯度"


def normalize_mohw_ltc_abc(rows: list[dict]) -> NormalizeResult:
    result = NormalizeResult(facilities=[], fetched_count=len(rows))
    grouped: "OrderedDict[str, list[dict]]" = OrderedDict()

    for row in rows:
        if clean_text(row.get("縣市")) != TAIPEI_CITY_CODE:
            result.filtered_out_count += 1
            continue
        code = clean_text(row.get("機構代碼"))
        if not code:
            result.skipped_count += 1
            result.skipped_reasons["missing_code"] += 1
            continue
        grouped.setdefault(code, []).append(row)

    merged_rows = 0
    for code, group in grouped.items():
        first = group[0]
        name = clean_text(first.get("機構名稱"))
        if not name:
            result.skipped_count += 1
            result.skipped_reasons["missing_name"] += 1
            continue
        merged_rows += len(group) - 1

        # 座標：取第一筆合法座標
        coord = _coordinate_fields(None, None, _MOHW_COORD_LABEL)
        for row in group:
            candidate = _coordinate_fields(row.get("緯度"), row.get("經度"), _MOHW_COORD_LABEL)
            if candidate["coordinate_status"] == COORDINATE_OK:
                coord = candidate
                break

        abc_types = sorted({clean_text(r.get("O_ABC")) for r in group if clean_text(r.get("O_ABC"))})
        services = sorted({clean_text(r.get("特約服務項目")) for r in group if clean_text(r.get("特約服務項目"))})
        updated_values = [clean_text(r.get("最後異動時間")) for r in group if clean_text(r.get("最後異動時間"))]
        address = clean_text(first.get("地址全址")) or None

        raw = dict(first)
        raw["_merged_rows"] = len(group)
        raw["_abc_types"] = abc_types
        raw["_service_items"] = services

        result.facilities.append(
            NormalizedFacility(
                external_id=code,
                name=name,
                category="long_term_care",
                address=address,
                phone=clean_text(first.get("機構電話")) or None,
                district=extract_district(address, first.get("區")),
                external_type="/".join(abc_types) or None,
                raw_updated_at=max(updated_values) if updated_values else None,
                raw=raw,
                **coord,
            )
        )

    result.duplicate_count = merged_rows
    result.notes["unique_institutions"] = len(grouped)
    if not result.facilities:
        raise NormalizeError("長照 ABC 據點沒有任何臺北市資料")
    return result


# ---------------------------------------------------------------------------
# 註冊表：source_registry 的 normalizer 名稱 → 函式
# ---------------------------------------------------------------------------

NORMALIZERS: dict[str, Callable[[list[dict]], NormalizeResult]] = {
    "taipei_hospital": normalize_taipei_hospital,
    "taipei_clinic": normalize_taipei_clinic,
    "moe_kindergarten": normalize_moe_kindergarten,
    "moe_elementary": normalize_moe_elementary,
    "moe_junior_high": normalize_moe_junior_high,
    "mohw_ltc_abc": normalize_mohw_ltc_abc,
}


def get_normalizer(name: str) -> Callable[[list[dict]], NormalizeResult]:
    try:
        return NORMALIZERS[name]
    except KeyError as exc:
        raise NormalizeError(f"找不到 normalizer：{name}") from exc
