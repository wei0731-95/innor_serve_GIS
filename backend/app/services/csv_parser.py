"""CSV 位元組 → 文字 → 資料列。

政府資料的編碼不一致（data.taipei 醫療院所是 Big5，教育部與衛福部是 UTF-8 BOM），
所以先依內容嘗試解碼，再依標頭 / 來源設定回退。
"""

from __future__ import annotations

import csv
import io
import re

_CHARSET_RE = re.compile(r"charset\s*=\s*\"?([^;\"\s]+)\"?", re.IGNORECASE)

# Python codec 名稱對應。cp950 是微軟版 Big5，比 'big5' 涵蓋更多常用字（例如「碁」、「堃」）。
_ENCODING_ALIASES = {
    "big5": "cp950",
    "big-5": "cp950",
    "big5-hkscs": "big5hkscs",
    "utf8": "utf-8",
}


class ParseError(Exception):
    """CSV 解碼或解析失敗（編碼錯誤、缺欄位、沒有資料列）。"""


def parse_charset(content_type: str | None) -> str | None:
    if not content_type:
        return None
    match = _CHARSET_RE.search(content_type)
    return match.group(1).strip().lower() if match else None


def _canonical_encoding(name: str | None) -> str | None:
    if not name:
        return None
    lowered = name.strip().lower()
    return _ENCODING_ALIASES.get(lowered, lowered)


def decode_bytes(content: bytes, *, content_type: str | None = None, fallback_encoding: str | None = None) -> tuple[str, str]:
    """回傳 (text, 使用的編碼)。

    順序：UTF-8 BOM → 嚴格 UTF-8 → Content-Type 宣告的 charset → 來源設定的 encoding →
    以上候選的寬鬆模式（以 U+FFFD 取代非法位元組）。全部失敗才拋 ParseError。
    """
    if content.startswith(b"\xef\xbb\xbf"):
        return content[3:].decode("utf-8", errors="replace"), "utf-8-sig"

    try:
        return content.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    candidates: list[str] = []
    for raw in (parse_charset(content_type), fallback_encoding):
        encoding = _canonical_encoding(raw)
        if encoding and encoding not in candidates and encoding != "utf-8":
            candidates.append(encoding)

    for encoding in candidates:
        try:
            return content.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue

    for encoding in candidates:
        try:
            return content.decode(encoding, errors="replace"), f"{encoding}(replace)"
        except LookupError:
            continue

    raise ParseError(
        "無法解碼 CSV：不是 UTF-8，且沒有可用的 charset（Content-Type="
        f"{content_type!r}, fallback={fallback_encoding!r}）"
    )


def parse_csv(text: str, *, required_fields: tuple[str, ...] | list[str] = ()) -> tuple[list[dict[str, str]], list[str]]:
    """解析 CSV 文字，回傳 (rows, header_fields)。

    - 標題與值都去除前後空白（data.taipei 醫院名稱帶有尾端 tab）
    - 空白列略過
    - 缺少 required_fields 視為格式錯誤（避免把錯誤的檔案當成正確資料寫進 DB）
    """
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text, newline=""))

    header: list[str] | None = None
    for row in reader:
        if row and any(cell.strip() for cell in row):
            header = row
            break
    if header is None:
        raise ParseError("CSV 沒有標題列")

    fields = [cell.strip().strip('"').strip() for cell in header]
    missing = [field for field in required_fields if field not in fields]
    if missing:
        raise ParseError(f"CSV 缺少必要欄位：{'、'.join(missing)}（實際欄位：{'、'.join(fields)}）")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue
        record: dict[str, str] = {}
        for index, field in enumerate(fields):
            value = raw_row[index] if index < len(raw_row) else ""
            record[field] = value.strip()
        rows.append(record)

    if not rows:
        raise ParseError("CSV 沒有任何資料列")

    return rows, fields
