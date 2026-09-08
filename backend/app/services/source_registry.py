"""官方資料來源註冊表：所有政府資料的 URL、機關、格式、編碼、對應的標準化器都集中在這裡。

新增資料來源 = 在 SOURCE_DEFINITIONS 加一筆 + 在 normalizer.py 提供對應的 normalizer。
所有 URL 皆為官方端點，實測日期：2026-09。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

KIND_FACILITY = "facility"
KIND_GEOMETRY = "geometry"

ORG_TAIPEI_HEALTH = "臺北市政府衛生局"
ORG_MOE_STATS = "教育部統計處"
ORG_MOHW = "衛生福利部"
ORG_NLSC = "內政部國土測繪中心"


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    organization: str
    category: str | None
    kind: str
    urls: tuple[str, ...]
    dataset_url: str
    format: str
    encoding: str | None
    description: str
    normalizer: str | None = None
    required_fields: tuple[str, ...] = ()
    enabled: bool = True
    # 需要另一份來源提供座標時填該來源 id（例如教育部名錄 → NLSC 學校範圍圖）
    coordinate_source_id: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def primary_url(self) -> str:
        return self.urls[0]


def moe_school_year_candidates(today: date | None = None, depth: int = 3) -> tuple[int, ...]:
    """教育部依「學年度」分檔。學年度 = 民國年，8 月起算新學年。回傳由新到舊的候選年度。"""
    today = today or date.today()
    roc_year = today.year - 1911
    current = roc_year if today.month >= 8 else roc_year - 1
    return tuple(current - offset for offset in range(depth))


def moe_elementary_urls(today: date | None = None) -> tuple[str, ...]:
    return tuple(
        f"https://stats.moe.gov.tw/files/school/{year}/e1_new.csv" for year in moe_school_year_candidates(today)
    )


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    # ---- 醫院 / 診所：臺北市公私立醫療院所（data.gov.tw 121182，實際檔案在 data.taipei）----
    SourceDefinition(
        id="taipei_hospital",
        name="臺北市公私立醫療院所－醫院",
        organization=ORG_TAIPEI_HEALTH,
        category="hospital",
        kind=KIND_FACILITY,
        urls=(
            "https://data.taipei/api/dataset/ffdd5753-30db-4c38-b65f-b77892773d60/resource/04a3d195-ee97-467a-b066-e471ff99d15d/download",
        ),
        dataset_url="https://data.gov.tw/dataset/121182",
        format="csv",
        encoding="big5",
        description="臺北市醫院名單，含 WGS84 經緯度。欄位：行政區域代碼、機構名稱、地址、經度、緯度。",
        normalizer="taipei_hospital",
        required_fields=("機構名稱", "地址", "經度", "緯度"),
    ),
    SourceDefinition(
        id="taipei_clinic",
        name="臺北市公私立醫療院所－診所",
        organization=ORG_TAIPEI_HEALTH,
        category="clinic",
        kind=KIND_FACILITY,
        urls=(
            "https://data.taipei/api/dataset/ffdd5753-30db-4c38-b65f-b77892773d60/resource/3a02af7d-8c33-46c1-8226-c12a11610f6b/download",
        ),
        dataset_url="https://data.gov.tw/dataset/121182",
        format="csv",
        encoding="big5",
        description="臺北市診所名單，含 WGS84 經緯度。欄位：縣市別代碼、分類、機構名稱、行政區、地址、經度、緯度。",
        normalizer="taipei_clinic",
        required_fields=("機構名稱", "地址", "經度", "緯度"),
    ),
    # ---- 學校座標補足用：NLSC 各級學校範圍圖（多邊形，EPSG:3826）----
    SourceDefinition(
        id="nlsc_school_blocks",
        name="各級學校範圍圖_121分帶（臺灣本島）",
        organization=ORG_NLSC,
        category=None,
        kind=KIND_GEOMETRY,
        urls=(
            "https://www.tgos.tw/tgos/VirtualDir/Product/5f346c6b-edde-4fe7-8685-5585c0fb7852/%E5%90%84%E7%B4%9A%E5%AD%B8%E6%A0%A1%E7%AF%84%E5%9C%8D%E5%9C%96_121_1150409.zip",
        ),
        dataset_url="https://data.gov.tw/dataset/174606",
        format="shapefile-zip",
        encoding="utf-8",
        description=(
            "臺灣通用電子地圖 BLOCK 圖層中 BLOCKTYPE=1（學校）的多邊形。"
            "本系統取臺北市多邊形的中心點，以學校名稱對應教育部名錄，補足國小 / 國中座標（座標可信度 Level 2）。"
        ),
    ),
    # ---- 幼兒園 / 國小 / 國中：教育部統計處各級學校名錄（只有地址，沒有座標）----
    SourceDefinition(
        id="moe_kindergarten",
        name="幼兒園名錄",
        organization=ORG_MOE_STATS,
        category="kindergarten",
        kind=KIND_FACILITY,
        urls=("https://stats.moe.gov.tw/files/opendata/k1_new.csv",),
        dataset_url="https://data.gov.tw/dataset/6086",
        format="csv",
        encoding="utf-8",
        description=(
            "全國幼兒園名錄（歷年、各縣市）。只匯入最新學年度的臺北市資料。"
            "名錄沒有座標，且目前找不到含幼兒園座標的官方資料集，因此座標狀態為 missing、不顯示在地圖上。"
        ),
        normalizer="moe_kindergarten",
        required_fields=("學年度", "代碼", "學校名稱", "縣市名稱", "地址"),
    ),
    SourceDefinition(
        id="moe_elementary",
        name="國民小學名錄",
        organization=ORG_MOE_STATS,
        category="elementary_school",
        kind=KIND_FACILITY,
        urls=moe_elementary_urls(),
        dataset_url="https://data.gov.tw/dataset/6087",
        format="csv",
        encoding="utf-8",
        description="全國國民小學名錄（依學年度分檔，自動嘗試最新學年度）。只匯入臺北市資料；座標由 NLSC 各級學校範圍圖對應補足。",
        normalizer="moe_elementary",
        required_fields=("學年度", "代碼", "學校名稱", "縣市名稱", "地址"),
        coordinate_source_id="nlsc_school_blocks",
    ),
    SourceDefinition(
        id="moe_junior_high",
        name="國民中學名錄",
        organization=ORG_MOE_STATS,
        category="junior_high_school",
        kind=KIND_FACILITY,
        urls=("https://stats.moe.gov.tw/files/opendata/j1_new.csv",),
        dataset_url="https://data.gov.tw/dataset/6088",
        format="csv",
        encoding="utf-8",
        description="全國國民中學名錄（歷年）。只匯入最新學年度的臺北市資料；座標由 NLSC 各級學校範圍圖對應補足。",
        normalizer="moe_junior_high",
        required_fields=("學年度", "代碼", "學校名稱", "縣市名稱", "地址"),
        coordinate_source_id="nlsc_school_blocks",
    ),
    # ---- 長照：衛生福利部 長照 ABC 據點（全國、每日更新、含座標）----
    SourceDefinition(
        id="mohw_ltc_abc",
        name="長照ABC據點",
        organization=ORG_MOHW,
        category="long_term_care",
        kind=KIND_FACILITY,
        urls=("https://ltcpap.mohw.gov.tw/publish/abc.csv",),
        dataset_url="https://data.gov.tw/dataset/88270",
        format="csv",
        encoding="utf-8",
        description=(
            "全國長照特約 A/B/C 單位（每日更新，含 WGS84 經緯度）。只匯入縣市代碼 63000（臺北市）；"
            "同一機構代碼的多筆特約服務合併為一筆，A/B/C 類型保留在 external_type。"
        ),
        normalizer="mohw_ltc_abc",
        required_fields=("機構名稱", "機構代碼", "縣市", "地址全址", "經度", "緯度"),
    ),
)

SOURCE_BY_ID: dict[str, SourceDefinition] = {definition.id: definition for definition in SOURCE_DEFINITIONS}


def get_source_definition(source_id: str) -> SourceDefinition | None:
    return SOURCE_BY_ID.get(source_id)


def enabled_sources(kind: str | None = None) -> list[SourceDefinition]:
    return [d for d in SOURCE_DEFINITIONS if d.enabled and (kind is None or d.kind == kind)]
