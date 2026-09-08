"""內政部國土測繪中心「各級學校範圍圖_121分帶」→ 臺北市學校中心點索引。

教育部的國小 / 國中名錄只有地址沒有座標。這個模組把官方學校範圍多邊形（EPSG:3826, TWD97 TM2）
轉成 WGS84 中心點，並用學校名稱對應名錄，作為座標可信度 Level 2 的來源。

對應不到的學校維持 coordinate_status = missing，不會用地址猜座標。
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass

import shapefile
from pyproj import Transformer

from .normalizer import clean_text

log = logging.getLogger(__name__)

COORDINATE_LEVEL_GEOMETRY = 2
GEOMETRY_SOURCE_LABEL = "內政部國土測繪中心「各級學校範圍圖_121分帶」多邊形中心點（依學校名稱對應）"

SOURCE_CRS = "EPSG:3826"
TARGET_CRS = "EPSG:4326"


class GeometryError(Exception):
    """學校範圍圖無法讀取或沒有臺北市資料。"""


@dataclass(frozen=True)
class SchoolPoint:
    name: str        # NLSC BLOCKNAME，例如「臺北市松山區松山國民小學」
    key: str         # 去掉前綴與尾碼數字後的比對鍵，例如「松山國民小學」
    is_private: bool
    lat: float
    lng: float
    area: float      # 平方公尺，同一校多個多邊形時取最大者
    yyyymm: str      # 圖資年月


_MOE_PREFIX_RE = re.compile(r"^(?:臺北市立|臺北市私立|臺北市|台北市|市立|國立|私立|縣立|公立)+")
_PAREN_RE = re.compile(r"[()（）]")
_NLSC_PREFIX_RE = re.compile(r"^臺北市(?:天主教)?(?:私立|立)?(?:[一-鿿]{1,3}區)?")
_TRAILING_DIGITS_RE = re.compile(r"\d+$")
_CORE_SUFFIX_RE = re.compile(r"(附設)?(實驗)?(國民|國際)?(中小學|小學|中學|國小|國中)$")


def normalize_moe_school_name(name: str) -> str:
    """教育部名錄名稱 → NLSC 命名慣例。

    市立松山國小 → 松山國民小學；市立國語實小 → 國語實驗國民小學；
    臺北市立大學附小 → 大學附設實驗國民小學；私立新民小學 → 新民國民小學；
    私立立人國(中)小 → 立人國民中小學；市立長安國中 → 長安國民中學。
    """
    n = _PAREN_RE.sub("", clean_text(name))
    n = _MOE_PREFIX_RE.sub("", n)
    if n.endswith("國民中小學"):
        return n
    if n.endswith("國中小") or n.endswith("中小學"):
        return n[:-3] + "國民中小學"
    if n.endswith("實小"):
        return n[:-2] + "實驗國民小學"
    if n.endswith("附小"):
        return n[:-2] + "附設實驗國民小學"
    if n.endswith("國小"):
        return n[:-2] + "國民小學"
    if n.endswith("小學") and not n.endswith("國民小學"):
        return n[:-2] + "國民小學"
    if n.endswith("國中"):
        return n[:-2] + "國民中學"
    if n.endswith("中學") and not n.endswith(("國民中學", "高級中學")):
        return n[:-2] + "國民中學"
    return n


def nlsc_key(blockname: str) -> str:
    key = _NLSC_PREFIX_RE.sub("", clean_text(blockname))
    return _TRAILING_DIGITS_RE.sub("", key)


def polygon_centroid(ring: list[tuple[float, float]]) -> tuple[float, float, float]:
    """回傳 (x, y, area)。退化多邊形改用頂點平均。"""
    if len(ring) < 3:
        x = sum(p[0] for p in ring) / len(ring)
        y = sum(p[1] for p in ring) / len(ring)
        return x, y, 0.0
    twice_area = cx = cy = 0.0
    for index in range(len(ring) - 1):
        x0, y0 = ring[index]
        x1, y1 = ring[index + 1]
        cross = x0 * y1 - x1 * y0
        twice_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(twice_area) < 1e-9:
        x = sum(p[0] for p in ring) / len(ring)
        y = sum(p[1] for p in ring) / len(ring)
        return x, y, 0.0
    return cx / (3 * twice_area), cy / (3 * twice_area), abs(twice_area) / 2


class SchoolGeometryIndex:
    def __init__(self, points: list[SchoolPoint]):
        self.points = list(points)
        self._by_key: dict[str, list[SchoolPoint]] = defaultdict(list)
        for point in self.points:
            self._by_key[point.key].append(point)

    def __len__(self) -> int:
        return len(self.points)

    def match(self, school_name: str, is_private: bool | None = None) -> SchoolPoint | None:
        """名稱對應：完全相同 → 包含 → 核心名稱唯一對應。都失敗回傳 None。"""
        key = normalize_moe_school_name(school_name)
        if not key:
            return None

        def accept(point: SchoolPoint) -> bool:
            return is_private is None or point.is_private == is_private

        candidates = [p for p in self._by_key.get(key, []) if accept(p)]

        if not candidates:
            candidates = [p for p in self.points if key in p.name and accept(p)]

        if not candidates:
            level = "小學" if "小學" in key else ("中學" if "中學" in key else None)
            core = _CORE_SUFFIX_RE.sub("", key)
            core_alt = core.replace("高中", "高級中學")
            # 附小屬於母校校區，不要求 NLSC 名稱含「小學」
            require_level = "附設" not in key
            if level and len(core) >= 2:
                candidates = [
                    p
                    for p in self.points
                    if (core in p.name or core_alt in p.name)
                    and (not require_level or level in p.name)
                    and accept(p)
                ]
                if len({p.key for p in candidates}) != 1:
                    candidates = []

        if not candidates:
            return None
        return max(candidates, key=lambda p: p.area)


def _read_member(archive: zipfile.ZipFile, suffix: str) -> io.BytesIO | None:
    for member in archive.namelist():
        if member.lower().endswith(suffix):
            return io.BytesIO(archive.read(member))
    return None


def build_index_from_zip(content: bytes, city_prefix: str = "臺北市") -> SchoolGeometryIndex:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise GeometryError(f"學校範圍圖不是有效的 zip：{exc}") from exc

    with archive:
        shp = _read_member(archive, ".shp")
        shx = _read_member(archive, ".shx")
        dbf = _read_member(archive, ".dbf")
        cpg = _read_member(archive, ".cpg")
    if shp is None or dbf is None:
        raise GeometryError("zip 內缺少 .shp / .dbf")

    declared = cpg.getvalue().decode("ascii", errors="ignore").strip().lower() if cpg else ""
    encodings = [declared] if declared else []
    encodings += [enc for enc in ("utf-8", "cp950") if enc not in encodings]

    reader = None
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            shp.seek(0)
            dbf.seek(0)
            if shx is not None:
                shx.seek(0)
            reader = shapefile.Reader(shp=shp, shx=shx, dbf=dbf, encoding=encoding)
            reader.record(0)  # 觸發解碼，確認編碑正確
            break
        except Exception as exc:  # noqa: BLE001 - 換下一個編碼
            last_error = exc
            reader = None
    if reader is None:
        raise GeometryError(f"無法讀取 shapefile：{last_error}")

    transformer = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)
    points: list[SchoolPoint] = []
    with reader:
        for shape_record in reader.iterShapeRecords():
            name = clean_text(shape_record.record["BLOCKNAME"])
            if not name.startswith(city_prefix):
                continue
            shape = shape_record.shape
            if not shape.points:
                continue
            parts = list(shape.parts) + [len(shape.points)]
            ring = shape.points[parts[0] : parts[1]]
            x, y, area = polygon_centroid(ring)
            lng, lat = transformer.transform(x, y)
            points.append(
                SchoolPoint(
                    name=name,
                    key=nlsc_key(name),
                    is_private="私立" in name,
                    lat=round(lat, 7),
                    lng=round(lng, 7),
                    area=area,
                    yyyymm=str(shape_record.record["YYYYMM"]),
                )
            )

    if not points:
        raise GeometryError(f"學校範圍圖內沒有任何「{city_prefix}」多邊形")
    log.info("school geometry index built: %d polygons for %s", len(points), city_prefix)
    return SchoolGeometryIndex(points)
