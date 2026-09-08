import pytest

from app.database import session_scope
from app.models import Facility, SyncLog
from app.services import sync_service
from app.services.fetcher import FetchError
from app.services.sync_service import SyncAlreadyRunning
from tests.conftest import EXPECTED_COUNTS, HOSPITAL_CSV, make_fetcher


def _facility_count(client, category=None):
    params = {"category": category} if category else {}
    return client.get("/api/facilities", params=params).json()["count"]


def _source(client, source_id):
    return client.get(f"/api/sources/{source_id}").json()


def test_sync_all_creates_logs_and_metadata(client, payloads):
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    assert run.error_count == 0
    assert run.success_count == 7
    assert run.started_at is not None and run.completed_at is not None
    for result in run.results:
        assert result.status == "success"
        assert result.log is not None
        assert result.log.status == "success"
        assert result.log.completed_at is not None

    hospital = next(r for r in run.results if r.source_id == "taipei_hospital")
    assert hospital.log.fetched_count == 3
    assert hospital.log.inserted_count == 3
    assert hospital.log.updated_count == 0
    assert hospital.log.deleted_count == 0
    assert hospital.log.missing_coordinate_count == 1

    ltc = next(r for r in run.results if r.source_id == "mohw_ltc_abc")
    assert ltc.log.fetched_count == 5
    assert ltc.log.inserted_count == 2
    assert ltc.log.skipped_count == 2

    with session_scope() as session:
        assert session.query(SyncLog).count() == 7
        assert session.query(Facility).count() == sum(total for total, _ in EXPECTED_COUNTS.values())

    status = client.get("/api/sync/status").json()
    assert status["running"] is False
    assert status["last_run_success_count"] == 7
    assert status["last_run_error_count"] == 0


def test_partial_source_failure_keeps_other_sources(client, payloads):
    payloads["mohw_ltc_abc"] = FetchError("下載逾時（90 秒）：https://ltcpap.mohw.gov.tw/publish/abc.csv")
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))

    assert run.success_count == 6
    assert run.error_count == 1
    failed = next(r for r in run.results if r.source_id == "mohw_ltc_abc")
    assert failed.status == "error"
    assert "逾時" in failed.message
    assert failed.log is not None and failed.log.status == "error"
    assert "逾時" in failed.log.error_message

    # 其他來源正常入庫
    assert _facility_count(client, "hospital") == 3
    assert _facility_count(client, "clinic") == 2
    assert _facility_count(client, "long_term_care") == 0

    source = _source(client, "mohw_ltc_abc")
    assert source["last_status"] == "error"
    assert "逾時" in source["last_error"]
    assert source["last_success_at"] is None
    assert _source(client, "taipei_hospital")["last_status"] == "success"

    categories = {entry["category"]: entry for entry in client.get("/api/categories").json()}
    assert categories["long_term_care"]["count"] == 0
    assert categories["long_term_care"]["sources"][0]["status"] == "error"
    assert categories["hospital"]["sources"][0]["status"] == "success"


@pytest.mark.parametrize(
    "source_id,category,bad_payload,expected_fragment",
    [
        ("taipei_hospital", "hospital", FetchError("HTTP 500：https://data.taipei/...", status_code=500), "HTTP 500"),
        ("taipei_hospital", "hospital", FetchError("下載逾時（90 秒）", status_code=None), "逾時"),
        # 醫院來源宣告 big5，亂碼會被寬鬆解碼後卡在欄位檢查；幼兒園來源宣告 utf-8，非 UTF-8 位元組直接判定無法解碼
        ("taipei_hospital", "hospital", b"\xff\xfe\x00\x01 not csv at all \x80\x81", "缺少必要欄位"),
        ("moe_kindergarten", "kindergarten", "學年度,代碼\n114,甲\n".encode("cp950"), "無法解碼"),
        ("taipei_hospital", "hospital", "欄位A,欄位B\n1,2\n".encode("utf-8"), "缺少必要欄位"),
        ("taipei_hospital", "hospital", "行政區域代碼,機構名稱,地址,經度,緯度\n".encode("cp950"), "沒有任何資料列"),
    ],
)
def test_source_errors_are_recorded(client, payloads, source_id, category, bad_payload, expected_fragment):
    payloads[source_id] = bad_payload
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    failed = next(r for r in run.results if r.source_id == source_id)
    assert failed.status == "error"
    assert expected_fragment in failed.message
    assert _facility_count(client, category) == 0
    assert _facility_count(client, "clinic") == 2
    logs = client.get(f"/api/sources/{source_id}/logs").json()
    assert logs[0]["status"] == "error" and expected_fragment in logs[0]["error_message"]


def test_failed_resync_preserves_existing_data(client, payloads):
    sync_service.sync_all(fetcher=make_fetcher(payloads))
    assert _facility_count(client, "hospital") == 3
    before = _source(client, "taipei_hospital")

    payloads["taipei_hospital"] = FetchError("網路錯誤：ConnectError", status_code=None)
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    assert next(r for r in run.results if r.source_id == "taipei_hospital").status == "error"

    # 舊資料保留，來源狀態標記為錯誤，但 last_success_at 不變
    assert _facility_count(client, "hospital") == 3
    after = _source(client, "taipei_hospital")
    assert after["last_status"] == "error"
    assert after["last_success_at"] == before["last_success_at"]
    assert after["record_count"] == 3
    logs = client.get("/api/sources/taipei_hospital/logs").json()
    assert [entry["status"] for entry in logs] == ["error", "success"]


def test_empty_taipei_dataset_is_an_error_not_a_wipe(client, payloads):
    sync_service.sync_all(fetcher=make_fetcher(payloads))
    assert _facility_count(client, "elementary_school") == 3

    payloads["moe_elementary"] = (
        '﻿"學年度","代碼","學校名稱","公/私立","縣市名稱","地址","電話","網址"\n'
        "114,011601,私立育才國小,私立,[01]新北市,[234]新北市永和區福和路125巷20號,(02)29214630,\n"
    ).encode("utf-8")
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    failed = next(r for r in run.results if r.source_id == "moe_elementary")
    assert failed.status == "error"
    assert "沒有任何臺北市資料" in failed.message
    assert _facility_count(client, "elementary_school") == 3


def test_resync_is_idempotent_and_removes_stale_records(client, payloads):
    sync_service.sync_all(fetcher=make_fetcher(payloads))

    second = sync_service.sync_all(fetcher=make_fetcher(payloads))
    for result in second.results:
        if result.source_id == "nlsc_school_blocks":
            continue
        assert result.log.inserted_count == 0, result.source_id
        assert result.log.updated_count == 0, result.source_id
        assert result.log.deleted_count == 0, result.source_id

    # 來源少了一筆 → 該筆從 DB 移除；名稱變更 → updated
    trimmed = HOSPITAL_CSV.decode("cp950").splitlines()
    trimmed_csv = "\n".join(trimmed[:2]).replace("郵政醫院（委託中英醫療社團法人經營）", "郵政醫院（委託中英醫療社團法人經營）") + "\n"
    payloads["taipei_hospital"] = trimmed_csv.encode("cp950")
    third = sync_service.sync_all(fetcher=make_fetcher(payloads))
    hospital = next(r for r in third.results if r.source_id == "taipei_hospital")
    assert hospital.log.deleted_count == 2
    assert hospital.log.inserted_count == 0
    assert _facility_count(client, "hospital") == 1
    assert _source(client, "taipei_hospital")["record_count"] == 1


def test_facility_ids_are_stable_across_syncs(client, payloads):
    sync_service.sync_all(fetcher=make_fetcher(payloads))
    first_ids = {item["id"] for item in client.get("/api/facilities").json()["items"]}
    sync_service.sync_all(fetcher=make_fetcher(payloads))
    second_ids = {item["id"] for item in client.get("/api/facilities").json()["items"]}
    assert first_ids == second_ids
    assert all(":" in facility_id for facility_id in first_ids)


def test_geometry_source_failure_leaves_schools_without_coordinates(client, payloads):
    payloads["nlsc_school_blocks"] = FetchError("HTTP 503：https://www.tgos.tw/...", status_code=503)
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    geometry = next(r for r in run.results if r.source_id == "nlsc_school_blocks")
    assert geometry.status == "error"
    # 學校名錄仍匯入，但沒有座標（不猜座標）
    schools = client.get("/api/facilities", params={"category": "elementary_school"}).json()["items"]
    assert len(schools) == 3
    assert all(item["coordinate_status"] == "missing" for item in schools)
    assert _source(client, "moe_elementary")["missing_coordinate_count"] == 3


def test_geometry_source_uses_cached_official_file_when_download_fails(client, payloads):
    sync_service.sync_all(fetcher=make_fetcher(payloads))  # 第一次成功 → 寫入快取

    payloads["nlsc_school_blocks"] = FetchError("HTTP 503：https://www.tgos.tw/...", status_code=503)
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    geometry = next(r for r in run.results if r.source_id == "nlsc_school_blocks")
    assert geometry.status == "success"
    source = _source(client, "nlsc_school_blocks")
    assert source["last_status"] == "success"
    assert "沿用" in source["last_error"]  # 明確記錄使用了快取
    schools = client.get("/api/facilities", params={"category": "elementary_school"}).json()["items"]
    assert sum(1 for item in schools if item["coordinate_status"] == "ok") == 2


def test_sync_lock_rejects_concurrent_runs(client, payloads):
    assert sync_service.state.lock.acquire(blocking=False)
    try:
        with pytest.raises(SyncAlreadyRunning):
            sync_service.sync_all(fetcher=make_fetcher(payloads))
        response = client.post("/api/sync")
        assert response.status_code == 409
        assert client.get("/api/sync/status").json()["running"] is True
    finally:
        sync_service.state.lock.release()


def test_sync_endpoints(client, payloads, monkeypatch):
    monkeypatch.setattr(sync_service, "fetch_first_available", make_fetcher(payloads))

    response = client.post("/api/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 7 and body["error_count"] == 0
    assert len(body["results"]) == 7
    assert _facility_count(client) == sum(total for total, _ in EXPECTED_COUNTS.values())

    single = client.post("/api/sync/taipei_hospital")
    assert single.status_code == 200
    assert [r["source_id"] for r in single.json()["results"]] == ["taipei_hospital"]

    # 學校名錄會連同座標來源一起同步
    school = client.post("/api/sync/moe_elementary")
    assert [r["source_id"] for r in school.json()["results"]] == ["nlsc_school_blocks", "moe_elementary"]

    assert client.post("/api/sync/not-a-source").status_code == 404


def test_sync_one_unknown_source(client):
    with pytest.raises(KeyError):
        sync_service.sync_one("not-a-source")
