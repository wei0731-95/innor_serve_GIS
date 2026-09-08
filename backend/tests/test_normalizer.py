from datetime import date

import pytest

from app.services import normalizer
from app.services.csv_parser import ParseError, decode_bytes, parse_charset, parse_csv
from app.services.normalizer import (
    NormalizeError,
    deduplicate,
    extract_district,
    is_valid_latlng,
    normalize_moe_elementary,
    normalize_mohw_ltc_abc,
    normalize_taipei_hospital,
    parse_coordinate,
    stable_hash,
    strip_postal_prefix,
)
from app.services.school_geometry import SchoolGeometryIndex, SchoolPoint, build_index_from_zip, nlsc_key, normalize_moe_school_name
from app.services.source_registry import moe_elementary_urls, moe_school_year_candidates
from tests.conftest import ELEMENTARY_CSV, HOSPITAL_CSV, LTC_CSV, NLSC_TEST_BLOCKS, build_nlsc_zip


# ---------------------------------------------------------------------------
# 座標驗證
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("25.03553921", 25.03553921),
        (" 121.5183428 ", 121.5183428),
        ("-25.5", -25.5),
        (25.0, 25.0),
        ("", None),
        (None, None),
        ("N/A", None),
        ("25.03abc", None),
        ("1e2", None),
        ("nan", None),
    ],
)
def test_parse_coordinate(value, expected):
    assert parse_coordinate(value) == expected


@pytest.mark.parametrize(
    "lat,lng,valid",
    [
        (25.0375, 121.5637, True),
        (0.0, 0.0, False),
        (None, 121.5, False),
        (25.0, None, False),
        (95.0, 121.5, False),
        (25.0, 200.0, False),
        (121.5637, 25.0375, False),  # 經緯度顛倒
        (2771000.0, 307200.0, False),  # TWD97 公尺值誤填
        (51.5, -0.12, False),  # 不在臺灣
    ],
)
def test_is_valid_latlng(lat, lng, valid):
    assert is_valid_latlng(lat, lng) is valid


def test_extract_district():
    assert extract_district("臺北市中正區福州街14號") == "中正區"
    assert extract_district("台北市大安區信義路三段1號") == "大安區"
    assert extract_district("新北市板橋區中正路437號") is None
    assert extract_district("某地址沒有區名", district_code="63000110") == "士林區"
    assert extract_district(None, district_name="松山區") == "松山區"
    assert extract_district(None, district_code="99999999") is None


def test_strip_postal_prefix_and_hash():
    assert strip_postal_prefix("[105]臺北市松山區八德路四段746號") == "臺北市松山區八德路四段746號"
    assert strip_postal_prefix("臺北市松山區八德路四段746號") == "臺北市松山區八德路四段746號"
    assert stable_hash("A醫院", "地址") == stable_hash(" A醫院 ", "地址 ")
    assert stable_hash("A醫院", "地址") != stable_hash("B醫院", "地址")
    assert len(stable_hash("x")) == 16


# ---------------------------------------------------------------------------
# 解碼 / CSV
# ---------------------------------------------------------------------------


def test_parse_charset():
    assert parse_charset("text/csv;charset=BIG-5") == "big-5"
    assert parse_charset('text/csv; charset="UTF-8"') == "utf-8"
    assert parse_charset("application/octet-stream") is None
    assert parse_charset(None) is None


def test_decode_bytes_utf8_bom_and_big5():
    text, encoding = decode_bytes("﻿學年度,代碼\n".encode("utf-8"))
    assert text.startswith("學年度") and encoding == "utf-8-sig"

    big5 = "機構名稱,地址\n郵政醫院,臺北市\n".encode("cp950")
    text, encoding = decode_bytes(big5, content_type="text/csv;charset=BIG-5")
    assert "郵政醫院" in text and encoding == "cp950"

    text, encoding = decode_bytes(big5, content_type="application/octet-stream", fallback_encoding="big5")
    assert "郵政醫院" in text and encoding == "cp950"

    with pytest.raises(ParseError):
        decode_bytes(big5, content_type="application/octet-stream")


def test_parse_csv_validation():
    rows, fields = parse_csv(' "機構名稱" , 地址 \n 甲 , 乙 \n\n')
    assert fields == ["機構名稱", "地址"]
    assert rows == [{"機構名稱": "甲", "地址": "乙"}]

    with pytest.raises(ParseError, match="缺少必要欄位"):
        parse_csv("機構名稱,地址\n甲,乙\n", required_fields=("經度",))
    with pytest.raises(ParseError, match="沒有任何資料列"):
        parse_csv("機構名稱,地址\n")
    with pytest.raises(ParseError, match="沒有標題列"):
        parse_csv("\n\n")


# ---------------------------------------------------------------------------
# normalizers
# ---------------------------------------------------------------------------


def test_normalize_taipei_hospital():
    text, _ = decode_bytes(HOSPITAL_CSV, content_type="text/csv;charset=BIG-5")
    rows, _ = parse_csv(text)
    result = normalize_taipei_hospital(rows)
    assert result.fetched_count == 3
    assert len(result.facilities) == 3
    assert result.missing_coordinate_count == 1
    ntuh = next(f for f in result.facilities if f.name == "國立台灣大學醫學院附設醫院")
    assert ntuh.category == "hospital"
    assert ntuh.coordinate_status == "ok" and ntuh.coordinate_level == 1
    assert ntuh.lat == pytest.approx(25.03553921) and ntuh.lng == pytest.approx(121.5183428)
    assert ntuh.district == "中正區"
    assert ntuh.phone is None
    missing = next(f for f in result.facilities if "缺座標" in f.name)
    assert missing.coordinate_status == "missing" and missing.lat is None and missing.coordinate_source is None
    # 同樣輸入 → 同樣 external_id
    again = normalize_taipei_hospital(rows)
    assert [f.external_id for f in again.facilities] == [f.external_id for f in result.facilities]


def test_normalize_hospital_rejects_empty_dataset():
    with pytest.raises(NormalizeError):
        normalize_taipei_hospital([{"機構名稱": "", "地址": "", "經度": "", "緯度": ""}])


def test_normalize_moe_elementary_filters_year_and_city():
    text, _ = decode_bytes(ELEMENTARY_CSV)
    rows, _ = parse_csv(text)
    result = normalize_moe_elementary(rows)
    assert result.notes["school_year"] == "114"
    assert result.filtered_out_count == 1  # 新北市
    assert {f.name for f in result.facilities} == {"市立松山國小", "私立新民小學", "市立長安國小"}
    songshan = next(f for f in result.facilities if f.name == "市立松山國小")
    assert songshan.external_id == "313601"
    assert songshan.address == "臺北市松山區八德路四段746號"
    assert songshan.district == "松山區"
    assert songshan.is_private is False
    assert songshan.coordinate_status == "missing"  # 名錄本身沒有座標
    xinmin = next(f for f in result.facilities if f.name == "私立新民小學")
    assert xinmin.is_private is True and xinmin.external_type == "私立"

    with pytest.raises(NormalizeError, match="沒有任何臺北市資料"):
        normalize_moe_elementary([r for r in rows if "新北市" in r["縣市名稱"]])


def test_normalize_ltc_merges_and_filters():
    text, _ = decode_bytes(LTC_CSV)
    rows, _ = parse_csv(text)
    result = normalize_mohw_ltc_abc(rows)
    assert result.fetched_count == 5
    assert result.filtered_out_count == 1  # 高雄
    assert result.skipped_count == 1  # 缺機構代碼
    assert result.duplicate_count == 1  # 同機構第二筆特約服務
    assert result.notes["unique_institutions"] == 2
    merged = next(f for f in result.facilities if f.external_id == "2S0100002")
    assert merged.external_type == "B"
    assert merged.raw["_service_items"] == ["居家服務(BA)", "日間照顧服務(BB)"]
    assert merged.raw_updated_at == "20250301 10:00:00"
    assert merged.coordinate_status == "ok" and merged.coordinate_level == 1
    missing = next(f for f in result.facilities if f.external_id == "T0100999")
    assert missing.coordinate_status == "missing"


def test_deduplicate_keeps_first():
    text, _ = decode_bytes(HOSPITAL_CSV, content_type="text/csv;charset=BIG-5")
    rows, _ = parse_csv(text)
    facilities = normalize_taipei_hospital(rows + rows).facilities
    assert len(facilities) == 3
    unique, duplicates = deduplicate(facilities + facilities)
    assert len(unique) == 3 and duplicates == 3


# ---------------------------------------------------------------------------
# 學校名稱對應（NLSC）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "moe_name,expected",
    [
        ("市立松山國小", "松山國民小學"),
        ("市立國語實小", "國語實驗國民小學"),
        ("臺北市立大學附小", "大學附設實驗國民小學"),
        ("私立新民小學", "新民國民小學"),
        ("私立立人國(中)小", "立人國民中小學"),
        ("私立立人國中(小)", "立人國民中小學"),
        ("市立長安國中", "長安國民中學"),
        ("國立政大實小", "政大實驗國民小學"),
    ],
)
def test_normalize_moe_school_name(moe_name, expected):
    assert normalize_moe_school_name(moe_name) == expected


def test_nlsc_key():
    assert nlsc_key("臺北市松山區松山國民小學") == "松山國民小學"
    assert nlsc_key("臺北市立懷生國民中學1") == "懷生國民中學"
    assert nlsc_key("臺北市私立新民國民小學") == "新民國民小學"
    assert nlsc_key("臺北市天主教私立光仁國民小學1") == "光仁國民小學"
    assert nlsc_key("臺北市立大學附設實驗國民小學") == "大學附設實驗國民小學"


def _point(name: str, area: float = 1000.0) -> SchoolPoint:
    return SchoolPoint(name=name, key=nlsc_key(name), is_private="私立" in name, lat=25.05, lng=121.56, area=area, yyyymm="202206")


def test_geometry_index_matching_rules():
    index = SchoolGeometryIndex([_point(name) for name in NLSC_TEST_BLOCKS] + [_point("臺北市立懷生國民中學", area=5000.0)])
    assert index.match("市立松山國小", False).name == "臺北市松山區松山國民小學"
    # 公私立分流：同名的中山國小
    assert index.match("市立中山國小", False).name == "臺北市中山區中山國民小學"
    assert index.match("私立中山小學", True).name == "臺北市私立中山國民小學"
    # 包含比對（NLSC 名稱尾碼數字），同校多個多邊形取面積最大者
    assert index.match("市立懷生國中", False).name == "臺北市立懷生國民中學"
    # 核心名稱唯一對應
    assert index.match("私立立人國(中)小", True).name == "臺北市私立立人國際國民中小學"
    # 不能誤配：長安只有國中
    assert index.match("市立長安國小", False) is None
    assert index.match("市立不存在國小", False) is None
    assert index.match("臺北市私立育華幼兒園", True) is None


def test_build_index_from_zip_transforms_to_wgs84():
    index = build_index_from_zip(build_nlsc_zip())
    assert len(index) == 8  # 只保留臺北市
    point = index.match("市立松山國小", False)
    assert point is not None
    assert 24.9 < point.lat < 25.3
    assert 121.4 < point.lng < 121.7
    assert point.area > 0


# ---------------------------------------------------------------------------
# 教育部依學年度分檔的 URL
# ---------------------------------------------------------------------------


def test_moe_school_year_candidates():
    assert moe_school_year_candidates(date(2026, 9, 5)) == (115, 114, 113)
    assert moe_school_year_candidates(date(2026, 3, 1)) == (114, 113, 112)
    urls = moe_elementary_urls(date(2026, 9, 5))
    assert urls[0] == "https://stats.moe.gov.tw/files/school/115/e1_new.csv"
    assert urls[-1].endswith("/113/e1_new.csv")


def test_taipei_district_code_map_is_complete():
    assert len(normalizer.TAIPEI_DISTRICT_CODES) == 12
    assert set(normalizer.TAIPEI_DISTRICT_CODES.values()) == set(normalizer.TAIPEI_DISTRICTS)
