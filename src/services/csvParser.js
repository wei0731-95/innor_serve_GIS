import Papa from 'papaparse';

/**
 * 從 Content-Type 取出 charset，例如 "text/csv;charset=BIG-5" → "big-5"
 */
export function parseCharset(contentType) {
  if (!contentType) return null;
  const match = /charset\s*=\s*"?([^;"\s]+)"?/i.exec(contentType);
  return match ? match[1].trim().toLowerCase() : null;
}

function tryDecode(bytes, encoding, fatal) {
  try {
    return new TextDecoder(encoding, { fatal }).decode(bytes);
  } catch {
    // 不支援的 encoding label，或 fatal 模式下遇到非法位元組
    return null;
  }
}

function hasUtf8Bom(bytes) {
  return bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
}

/**
 * 把 CSV 的原始位元組解成字串。
 *
 * 為什麼不用 response.text()？
 * 因為 response.text() 一律以 UTF-8 解碼，而臺北市資料大平台的這份 CSV 實際上是 Big5
 * （回應標頭 Content-Type: text/csv;charset=BIG-5），直接用 text() 會得到亂碼。
 *
 * 解碼順序：
 * 1. UTF-8 BOM → UTF-8
 * 2. 嚴格 UTF-8（Big5 位元組幾乎不可能通過嚴格 UTF-8 驗證，所以這步能可靠區分兩者）
 * 3. Content-Type 宣告的 charset
 * 4. 資料來源設定的 fallbackEncoding（例如 'big5'）
 * 5. 寬鬆 UTF-8（最後手段，可能出現亂碼但不會拋錯）
 */
export function decodeCsvBuffer(buffer, { contentType, fallbackEncoding } = {}) {
  const bytes = new Uint8Array(buffer);

  if (hasUtf8Bom(bytes)) {
    return new TextDecoder('utf-8').decode(bytes.subarray(3));
  }

  const strictUtf8 = tryDecode(bytes, 'utf-8', true);
  if (strictUtf8 !== null) return strictUtf8;

  const candidates = [parseCharset(contentType), fallbackEncoding].filter(Boolean);
  for (const encoding of candidates) {
    const text = tryDecode(bytes, encoding, false);
    if (text !== null) return text;
  }

  return new TextDecoder('utf-8').decode(bytes);
}

/**
 * 用 Papa Parse 解析 CSV 文字。
 *
 * @param {string} text CSV 內容
 * @param {object} options
 * @param {string[]} [options.requiredFields] 必須存在的欄位名稱，缺少時視為格式錯誤
 * @returns {{ rows: object[], fields: string[], errors: object[] }}
 */
export function parseCsv(text, { requiredFields = [] } = {}) {
  const result = Papa.parse(text, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (header) => header.trim(),
    transform: (value) => (typeof value === 'string' ? value.trim() : value),
  });

  const fields = result.meta?.fields ?? [];
  if (fields.length === 0) {
    throw new Error('CSV 沒有標題列');
  }

  const missing = requiredFields.filter((field) => !fields.includes(field));
  if (missing.length > 0) {
    throw new Error(`CSV 缺少必要欄位：${missing.join('、')}（實際欄位：${fields.join('、')}）`);
  }

  if (!Array.isArray(result.data) || result.data.length === 0) {
    throw new Error('CSV 沒有任何資料列');
  }

  // Papa Parse 的 row-level errors（例如某列欄位數不符）不視為致命錯誤，
  // 交由 normalizeFacility 逐筆判斷座標是否有效。
  return { rows: result.data, fields, errors: result.errors ?? [] };
}
