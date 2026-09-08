"""pytest 共用設定。

- 每個測試使用獨立的暫存 SQLite 與快取目錄。
- 政府資料下載一律用 fake fetcher 注入樣本位元組，測試不連網。
- 樣本資料列沿用各官方 CSV 的真實欄位格式；標示「測試用」的列是為了驗證缺座標 / 缺代碼等
  錯誤處理而加入的測試夾具，正式程式不會使用任何樣本資料。
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 必須在 import app 之前設定：app.main 在 import 時就會讀取設定
os.environ["SYNC_ON_STARTUP"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["CACHE_DIR"] = tempfile.mkdtemp(prefix="citygap-test-cache-")
os.environ["LOG_LEVEL"] = "WARNING"

import shapefile  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import utcnow  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import sync_service  # noqa: E402
from app.services.fetcher import FetchError, FetchResult  # noqa: E402
from app.services.source_registry import SOURCE_BY_ID  # noqa: E402

# ---------------------------------------------------------------------------
# 樣本 CSV（欄位格式取自官方檔案）
# ---------------------------------------------------------------------------

HOSPITAL_CSV = (
    "行政區域代碼,機構名稱,地址,經度,緯度\n"
    '63000050,"郵政醫院（委託中英醫療社團法人經營）\t",臺北市中正區福州街14號,121.5186982,25.02874869\n'
    '63000050,"國立台灣大學醫學院附設醫院\t",臺北市中正區中山南路７、８號；常德街１號,121.5183428,25.03553921\n'
    '63000110,"測試用－缺座標醫院\t",臺北市士林區中正路1號,,\n'
).encode("cp950")

CLINIC_CSV = (
    "縣市別代碼,分類,機構名稱,行政區,地址,經度,緯度\n"
    "63000,診所,葛鎂診所,63000050,臺北市中正區館前路34號9樓,121.5149085,25.04466557\n"
    "63000,診所,永康身心診所,63000050,臺北市中正區金山南路1段127號1樓,121.527716,25.0356227\n"
).encode("cp950")

KINDERGARTEN_CSV = (
    "﻿學年度,代碼,學校名稱,公/私立,縣市名稱,鄉鎮市區名稱,地址,電話\n"
    "104,011K01,遊戲橘子數位科技股份有限公司附設新北市私立幼橘園幼兒園,私立,[01]新北市,中和區,[235]新北市中和區平河里1鄰連城路260號1樓及268號2樓,(02)82269920#5401\n"
    "114,011K02,新北市私立溫特爾幼兒園,私立,[01]新北市,三峽區,[237]新北市三峽區龍埔里5鄰三樹路336號,(02)26718181\n"
    "114,T31K01,臺北市私立育華幼兒園,私立,[31]臺北市,松山區,[105]臺北市松山區測試路1號,(02)27457737\n"
    "114,T31X01,臺北市松山區松山國民小學附設幼兒園,公立,[31]臺北市,松山區,[105]臺北市松山區八德路四段746號,(02)27672907\n"
).encode("utf-8")

ELEMENTARY_CSV = (
    '﻿"學年度","代碼","學校名稱","公/私立","縣市名稱","地址","電話","網址"\n'
    "114,011601,私立育才國小,私立,[01]新北市,[234]新北市永和區福和路125巷20號,(02)29214630,https://www.ytes.ntpc.edu.tw\n"
    "114,313601,市立松山國小,公立,[31]臺北市,[105]臺北市松山區八德路四段746號,(02)27672907,https://www.ssps.tp.edu.tw\n"
    "114,T31601,私立新民小學,私立,[31]臺北市,[106]臺北市大安區辛亥路1段113號,(02)23923191,\n"
    "114,T31602,市立長安國小,公立,[31]臺北市,[104]臺北市中山區吉林路15號,(02)25412063,\n"
).encode("utf-8")

JUNIOR_HIGH_CSV = (
    "﻿學年度,代碼,學校名稱,公/私立,縣市名稱,地址,電話,網址\n"
    "104,014501,市立板橋國中,公立,[01]新北市,[220]新北市板橋區中正路437號,(02)29666498#234,http://www.pcjh.ntpc.edu.tw\n"
    "114,313501,市立中崙國中,公立,[31]臺北市,[105]臺北市松山區八德路四段101號,(02)27674496,http://www.csjh.tp.edu.tw\n"
    "115,313501,市立中崙國中,公立,[31]臺北市,[105]臺北市松山區八德路四段101號,(02)27674496,http://www.csjh.tp.edu.tw\n"
    "115,T31501,市立懷生國中,公立,[31]臺北市,[106]臺北市大安區忠孝東路三段248巷2號,(02)27522815,\n"
).encode("utf-8")

_LTC_HEADER = (
    '"機構名稱","機構代碼","機構種類","縣市","區","地址全址",經度,緯度,"O_ABC","特約服務項目","特約縣市","特約區域",'
    '"機構電話","電子郵件","機構負責人姓名","特約起日","特約迄日","最後異動時間",開放床數,現有住民,'
    '"機構種類代碼第三階層","身障機構註記是否為住宿式機構"\n'
)
LTC_CSV = (
    "﻿"
    + _LTC_HEADER
    + '"高雄市立凱旋醫院社區式(日間照顧)服務類長期照顧服務機構","2B1500001","2","64000","64000080","高雄市苓雅區凱旋二路130號",120.3240356445,22.6251220703,"B","日間照顧服務(BB)","64000","64000080","07-7513171","","","20180305","20261231","20240701 11:38:27",0,0,,"0"\n'
    + '"臺北市私立伊甸社區長照機構(日間照顧)","2S0100002","2","63000","63000010","臺北市松山區民生東路五段163號1樓",121.5627670288,25.0590858459,"B","日間照顧服務(BB)","63000","63000010","02-27609605","","","20181025","20261231","20250204 15:02:46",0,0,,"0"\n'
    + '"臺北市私立伊甸社區長照機構(日間照顧)","2S0100002","2","63000","63000010","臺北市松山區民生東路五段163號1樓",121.5627670288,25.0590858459,"B","居家服務(BA)","63000","63000010","02-27609605","","","20181025","20261231","20250301 10:00:00",0,0,,"0"\n'
    + '"測試用－缺座標A單位","T0100999","1","63000","63000030","臺北市大安區信義路三段1號",,,"A","社區整合型服務中心(A)","63000","63000030","02-27000000","","","20200101","20261231","20250101 09:00:00",0,0,,"0"\n'
    + '"測試用－缺機構代碼","","2","63000","63000030","臺北市大安區信義路三段2號",121.54,25.03,"B","日間照顧服務(BB)","63000","63000030","","","","20200101","20261231","20250101 09:00:00",0,0,,"0"\n'
).encode("utf-8")

# 各分類預期結果：(總筆數, 有座標筆數)
EXPECTED_COUNTS = {
    "hospital": (3, 2),
    "clinic": (2, 2),
    "kindergarten": (2, 0),
    "elementary_school": (3, 2),
    "junior_high_school": (2, 2),
    "long_term_care": (2, 1),
}

# TWD97 TM2（EPSG:3826）座標，落在臺北市松山區附近
_BASE_X, _BASE_Y = 307200.0, 2770900.0
NLSC_TEST_BLOCKS = (
    "臺北市松山區松山國民小學",
    "臺北市私立新民國民小學",
    "臺北市中山區中山國民小學",
    "臺北市私立中山國民小學",
    "臺北市立中崙國民中學",
    "臺北市立懷生國民中學1",
    "臺北市立長安國民中學",
    "臺北市私立立人國際國民中小學",
    "新北市板橋區板橋國民小學",
)


def build_nlsc_zip(blocknames: tuple[str, ...] = NLSC_TEST_BLOCKS) -> bytes:
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON, encoding="utf-8")
    writer.field("OBJECTID", "N", 10)
    writer.field("ID", "N", 10)
    writer.field("BLOCKTYPE", "N", 5)
    writer.field("BLOCKNAME", "C", 120)
    writer.field("YYYYMM", "C", 6)
    writer.field("EPSGCode", "C", 12)
    for index, name in enumerate(blocknames, start=1):
        x0 = _BASE_X + index * 300
        y0 = _BASE_Y + index * 300
        size = 100 + index * 10
        writer.poly([[(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0)]])
        writer.record(index, index, 1, name, "202206", "EPSG:3826")
    writer.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("test_schools.shp", shp.getvalue())
        archive.writestr("test_schools.shx", shx.getvalue())
        archive.writestr("test_schools.dbf", dbf.getvalue())
        archive.writestr("test_schools.cpg", "UTF-8")
    return buffer.getvalue()


CONTENT_TYPES = {
    "taipei_hospital": "text/csv;charset=BIG-5",
    "taipei_clinic": "text/csv;charset=BIG-5",
    "moe_kindergarten": "application/octet-stream",
    "moe_elementary": "application/octet-stream",
    "moe_junior_high": "application/octet-stream",
    "mohw_ltc_abc": "application/octet-stream",
    "nlsc_school_blocks": "application/x-zip-compressed",
}


def default_payloads() -> dict[str, bytes]:
    return {
        "taipei_hospital": HOSPITAL_CSV,
        "taipei_clinic": CLINIC_CSV,
        "moe_kindergarten": KINDERGARTEN_CSV,
        "moe_elementary": ELEMENTARY_CSV,
        "moe_junior_high": JUNIOR_HIGH_CSV,
        "mohw_ltc_abc": LTC_CSV,
        "nlsc_school_blocks": build_nlsc_zip(),
    }


def make_fetcher(payloads: dict[str, bytes | Exception]):
    """回傳與 fetch_first_available 同簽名的假下載函式。payload 為 Exception 時直接拋出。"""

    def fetcher(urls):
        first = urls[0]
        source_id = next((sid for sid, d in SOURCE_BY_ID.items() if d.urls[0] == first), None)
        if source_id is None:
            raise FetchError(f"測試沒有對應的來源：{first}", url=first)
        payload = payloads.get(source_id)
        if payload is None:
            raise FetchError(f"測試沒有提供 {source_id} 的資料", url=first, status_code=404)
        if isinstance(payload, Exception):
            raise payload
        return FetchResult(
            url=first,
            content=payload,
            content_type=CONTENT_TYPES.get(source_id, "text/csv"),
            status_code=200,
            fetched_at=utcnow(),
        )

    return fetcher


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "cache_dir", str(tmp_path / "cache"))
    sync_service.state.last_run = None
    yield


@pytest.fixture()
def engine(tmp_path):
    database.configure_database(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    database.init_db()
    yield database.get_engine()
    database.get_engine().dispose()


@pytest.fixture()
def client(engine):
    app = create_app(get_settings())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def payloads():
    return default_payloads()


@pytest.fixture()
def synced_client(client, payloads):
    run = sync_service.sync_all(fetcher=make_fetcher(payloads))
    assert run.error_count == 0, [r.message for r in run.results if r.status != "success"]
    return client
