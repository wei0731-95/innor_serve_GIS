import { CATEGORY_KEYS } from '../config/categories.js';

/**
 * 搜尋文字正規化：轉小寫、去空白、「臺」視同「台」。
 * 資料端與輸入端都用同一個函式，確保比對一致。
 */
export function normalizeSearchText(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/臺/g, '台');
}

/**
 * 建立搜尋索引：每筆資料只正規化一次（資料載入後才重算），
 * 之後每次輸入都只做字串 includes，不會重新 parse / normalize。
 */
export function buildSearchIndex(facilities) {
  return facilities.map((facility) => ({
    facility,
    text: `${normalizeSearchText(facility.name)}|${normalizeSearchText(facility.address)}`,
  }));
}

/**
 * 搜尋 + 分類篩選同時作用。
 * @param {ReturnType<typeof buildSearchIndex>} searchIndex
 * @param {Record<string, boolean>} selectedCategories 分類 key → 是否勾選
 * @param {string} query 已正規化的搜尋字串
 */
export function filterFacilities(searchIndex, selectedCategories, query) {
  const result = [];
  for (const { facility, text } of searchIndex) {
    if (!selectedCategories[facility.category]) continue;
    if (query !== '' && !text.includes(query)) continue;
    result.push(facility);
  }
  return result;
}

/** 依分類計數；所有分類都會出現，沒有資料就是 0，不會憑空產生數字 */
export function countByCategory(facilities) {
  const counts = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, 0]));
  for (const facility of facilities) {
    counts[facility.category] = (counts[facility.category] ?? 0) + 1;
  }
  return counts;
}
