import pytest

from app.config import CATEGORY_KEYS
from tests.conftest import EXPECTED_COUNTS

FACILITY_REQUIRED_KEYS = {
    "id", "name", "category", "address", "phone", "district",
    "lat", "lng", "coordinate_status", "coordinate_level", "coordinate_source",
    "source", "source_id", "source_url", "source_organization", "source_download_url", "source_synced_at",
    "external_id", "external_type", "raw_updated_at", "updated_at",
}


def _assert_facility_schema(item: dict) -> None:
    assert FACILITY_REQUIRED_KEYS <= set(item), set(item) ^ FACILITY_REQUIRED_KEYS
    assert item["category"] in CATEGORY_KEYS
    assert item["name"]
    assert item["id"] == f"{item['source_id']}:{item['external_id']}"
    if item["coordinate_status"] == "ok":
        assert isinstance(item["lat"], float) and isinstance(item["lng"], float)
        assert 21.5 <= item["lat"] <= 26.5 and 118.0 <= item["lng"] <= 122.5
        assert item["coordinate_level"] in (1, 2, 3)
        assert item["coordinate_source"]
    else:
        assert item["coordinate_status"] == "missing"
        assert item["lat"] is None and item["lng"] is None
        assert item["coordinate_level"] is None
    # 來源追溯
    assert item["source"]
    assert item["source_organization"]
    assert item["source_url"].startswith("https://data.gov.tw/dataset/")
    assert item["source_download_url"].startswith("https://")
    assert item["source_synced_at"] is not None
    # 原始欄位不得外露
    for raw_key in ("機構名稱", "raw_json", "raw"):
        assert raw_key not in item


def test_list_all_facilities(synced_client):
    body = synced_client.get("/api/facilities").json()
    expected_total = sum(total for total, _ in EXPECTED_COUNTS.values())
    assert body["count"] == expected_total == len(body["items"])
    for item in body["items"]:
        _assert_facility_schema(item)


@pytest.mark.parametrize("category", list(EXPECTED_COUNTS))
def test_filter_by_category(synced_client, category):
    body = synced_client.get("/api/facilities", params={"category": category}).json()
    expected_total, expected_with_coords = EXPECTED_COUNTS[category]
    assert body["count"] == expected_total
    assert all(item["category"] == category for item in body["items"])
    assert sum(1 for item in body["items"] if item["coordinate_status"] == "ok") == expected_with_coords

    only_coords = synced_client.get("/api/facilities", params={"category": category, "with_coordinates": "true"}).json()
    assert only_coords["count"] == expected_with_coords
    assert all(item["coordinate_status"] == "ok" for item in only_coords["items"])


def test_unknown_category_is_rejected(synced_client):
    response = synced_client.get("/api/facilities", params={"category": "spaceport"})
    assert response.status_code == 400
    assert "spaceport" in response.json()["detail"]


def test_search_name_and_address(synced_client):
    by_name = synced_client.get("/api/facilities", params={"search": "松山國小"}).json()
    assert by_name["count"] == 1
    assert by_name["items"][0]["category"] == "elementary_school"

    by_address = synced_client.get("/api/facilities", params={"search": "福州街"}).json()
    assert by_address["count"] == 1
    assert by_address["items"][0]["name"] == "郵政醫院（委託中英醫療社團法人經營）"

    # 「台」「臺」視為相同
    tai = synced_client.get("/api/facilities", params={"search": "台北市中正區"}).json()
    tai_alt = synced_client.get("/api/facilities", params={"search": "臺北市中正區"}).json()
    assert tai["count"] == tai_alt["count"] >= 4

    none = synced_client.get("/api/facilities", params={"search": "不存在的機構名稱XYZ"}).json()
    assert none["count"] == 0 and none["items"] == []


def test_search_combined_with_category(synced_client):
    body = synced_client.get("/api/facilities", params={"search": "中正區", "category": "clinic"}).json()
    assert body["count"] == 2
    assert all(item["category"] == "clinic" for item in body["items"])


def test_filter_by_district(synced_client):
    body = synced_client.get("/api/facilities", params={"district": "中正區"}).json()
    assert body["count"] >= 4
    assert all(item["district"] == "中正區" for item in body["items"])
    # 沒有「區」字也接受
    assert synced_client.get("/api/facilities", params={"district": "中正"}).json()["count"] == body["count"]
    assert synced_client.get("/api/facilities", params={"district": "松山區", "category": "kindergarten"}).json()["count"] == 2


def test_get_single_facility(synced_client):
    first = synced_client.get("/api/facilities", params={"category": "hospital"}).json()["items"][0]
    response = synced_client.get(f"/api/facilities/{first['id']}")
    assert response.status_code == 200
    assert response.json() == first
    assert synced_client.get("/api/facilities/taipei_hospital:does-not-exist").status_code == 404


def test_hospital_name_is_cleaned_and_id_is_stable(synced_client):
    hospitals = synced_client.get("/api/facilities", params={"category": "hospital"}).json()["items"]
    names = {item["name"] for item in hospitals}
    assert "國立台灣大學醫學院附設醫院" in names  # 尾端 tab 已移除
    assert all("\t" not in item["name"] for item in hospitals)
    ntuh = next(item for item in hospitals if item["name"] == "國立台灣大學醫學院附設醫院")
    assert ntuh["coordinate_level"] == 1
    assert ntuh["district"] == "中正區"
    # 沒有官方代碼的來源用「名稱 + 地址」的 16 碼雜湊當 external_id，必須可重算（穩定）
    from app.services.normalizer import stable_hash

    assert ntuh["external_id"] == stable_hash("國立台灣大學醫學院附設醫院", "臺北市中正區中山南路７、８號；常德街１號")
    assert len(ntuh["external_id"]) == 16


def test_school_coordinates_come_from_geometry_source(synced_client):
    schools = synced_client.get("/api/facilities", params={"category": "elementary_school"}).json()["items"]
    by_name = {item["name"]: item for item in schools}
    assert by_name["市立松山國小"]["coordinate_status"] == "ok"
    assert by_name["市立松山國小"]["coordinate_level"] == 2
    assert "國土測繪中心" in by_name["市立松山國小"]["coordinate_source"]
    assert "松山國民小學" in by_name["市立松山國小"]["coordinate_source"]
    assert by_name["私立新民小學"]["coordinate_status"] == "ok"
    # 長安國小：NLSC 只有長安國民中學，不能誤配
    assert by_name["市立長安國小"]["coordinate_status"] == "missing"
    assert by_name["市立長安國小"]["lat"] is None
    assert by_name["市立松山國小"]["raw_updated_at"] == "114學年度"
    assert by_name["市立松山國小"]["address"] == "臺北市松山區八德路四段746號"  # 郵遞區號前綴已移除


def test_kindergartens_are_kept_without_coordinates(synced_client):
    items = synced_client.get("/api/facilities", params={"category": "kindergarten"}).json()["items"]
    assert len(items) == 2
    assert all(item["coordinate_status"] == "missing" for item in items)
    assert all(item["district"] == "松山區" for item in items)
    assert synced_client.get("/api/facilities", params={"category": "kindergarten", "with_coordinates": "true"}).json()["count"] == 0


def test_long_term_care_merges_duplicate_institution(synced_client):
    items = synced_client.get("/api/facilities", params={"category": "long_term_care"}).json()["items"]
    by_id = {item["external_id"]: item for item in items}
    assert set(by_id) == {"2S0100002", "T0100999"}
    merged = by_id["2S0100002"]
    assert merged["external_type"] == "B"
    assert merged["raw_updated_at"] == "20250301 10:00:00"
    assert merged["phone"] == "02-27609605"
    assert merged["district"] == "松山區"
    assert by_id["T0100999"]["coordinate_status"] == "missing"
    assert by_id["T0100999"]["external_type"] == "A"


def test_categories_endpoint_matches_facilities(synced_client):
    categories = synced_client.get("/api/categories").json()
    assert [entry["category"] for entry in categories] == list(CATEGORY_KEYS)
    for entry in categories:
        expected_total, expected_with_coords = EXPECTED_COUNTS[entry["category"]]
        assert entry["label"]
        assert entry["count"] == expected_total
        assert entry["with_coordinates"] == expected_with_coords
        assert entry["missing_coordinates"] == expected_total - expected_with_coords
        assert entry["count"] == entry["with_coordinates"] + entry["missing_coordinates"]
        assert entry["sources"], entry["category"]
        for source in entry["sources"]:
            assert source["status"] == "success"
            assert source["organization"]
            assert source["last_success_at"] is not None
        assert sum(source["record_count"] for source in entry["sources"]) == expected_total


def test_sources_endpoint_metadata(synced_client):
    sources = synced_client.get("/api/sources").json()
    by_id = {source["id"]: source for source in sources}
    assert {
        "taipei_hospital", "taipei_clinic", "moe_kindergarten", "moe_elementary",
        "moe_junior_high", "mohw_ltc_abc", "nlsc_school_blocks",
    } <= set(by_id)
    for source in sources:
        for key in ("name", "organization", "url", "dataset_url", "format", "enabled", "last_status", "record_count", "skipped_count", "missing_coordinate_count"):
            assert key in source
        assert source["url"].startswith("https://")
        assert source["dataset_url"].startswith("https://data.gov.tw/dataset/")
        assert source["last_status"] == "success"
        assert source["last_success_at"] is not None
    assert by_id["taipei_hospital"]["category"] == "hospital"
    assert by_id["taipei_hospital"]["record_count"] == 3
    assert by_id["taipei_hospital"]["missing_coordinate_count"] == 1
    assert by_id["mohw_ltc_abc"]["record_count"] == 2
    assert by_id["mohw_ltc_abc"]["skipped_count"] == 2  # 1 筆缺機構代碼 + 1 筆合併
    assert by_id["moe_kindergarten"]["missing_coordinate_count"] == 2
    assert by_id["nlsc_school_blocks"]["kind"] == "geometry"
    assert by_id["nlsc_school_blocks"]["category"] is None
    assert by_id["nlsc_school_blocks"]["record_count"] == 8  # 臺北市多邊形（新北市那筆不算）

    single = synced_client.get("/api/sources/taipei_hospital")
    assert single.status_code == 200 and single.json() == by_id["taipei_hospital"]
    assert synced_client.get("/api/sources/nope").status_code == 404

    logs = synced_client.get("/api/sources/taipei_hospital/logs").json()
    assert len(logs) == 1
    assert logs[0]["status"] == "success"
    assert logs[0]["fetched_count"] == 3
    assert logs[0]["inserted_count"] == 3


def test_empty_database_before_sync(client):
    assert client.get("/api/facilities").json() == {"count": 0, "items": []}
    categories = client.get("/api/categories").json()
    assert all(entry["count"] == 0 for entry in categories)
    sources = client.get("/api/sources").json()
    assert len(sources) == 7
    assert all(source["last_status"] == "never" for source in sources)
