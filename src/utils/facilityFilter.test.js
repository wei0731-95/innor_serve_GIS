import { describe, expect, it } from 'vitest';
import { CATEGORY_KEYS } from '../config/categories.js';
import { buildSearchIndex, countByCategory, filterFacilities, normalizeSearchText } from './facilityFilter.js';

const facilities = [
  { id: 'taipei_hospital:a', name: '國立台灣大學醫學院附設醫院', address: '臺北市中正區中山南路7號', category: 'hospital' },
  { id: 'taipei_clinic:b', name: '永康身心診所', address: '臺北市中正區金山南路1段127號1樓', category: 'clinic' },
  { id: 'moe_elementary:c', name: '市立松山國小', address: '臺北市松山區八德路四段746號', category: 'elementary_school' },
  { id: 'moe_kindergarten:d', name: '臺北市私立育華幼兒園', address: '', category: 'kindergarten' },
];

const allSelected = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, true]));

describe('normalizeSearchText', () => {
  it('轉小寫、去空白、臺 → 台', () => {
    expect(normalizeSearchText(' 臺北 市 ABC ')).toBe('台北市abc');
    expect(normalizeSearchText(null)).toBe('');
    expect(normalizeSearchText(undefined)).toBe('');
  });
});

describe('filterFacilities', () => {
  const index = buildSearchIndex(facilities);

  it('沒有搜尋字串時回傳所有勾選分類', () => {
    expect(filterFacilities(index, allSelected, '')).toHaveLength(4);
  });

  it('依分類 checkbox 篩選', () => {
    const onlyClinic = { ...allSelected, hospital: false, elementary_school: false, kindergarten: false };
    const result = filterFacilities(index, onlyClinic, '');
    expect(result.map((f) => f.id)).toEqual(['taipei_clinic:b']);
  });

  it('搜尋名稱與地址，臺 / 台 視為相同', () => {
    expect(filterFacilities(index, allSelected, normalizeSearchText('台大')).map((f) => f.id)).toEqual([]);
    expect(filterFacilities(index, allSelected, normalizeSearchText('台灣大學')).map((f) => f.id)).toEqual(['taipei_hospital:a']);
    expect(filterFacilities(index, allSelected, normalizeSearchText('台北市中正區'))).toHaveLength(2);
    expect(filterFacilities(index, allSelected, normalizeSearchText('八德路')).map((f) => f.id)).toEqual(['moe_elementary:c']);
  });

  it('搜尋與分類同時作用', () => {
    const onlyHospital = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, key === 'hospital']));
    expect(filterFacilities(index, onlyHospital, normalizeSearchText('中正區')).map((f) => f.id)).toEqual(['taipei_hospital:a']);
    const none = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, false]));
    expect(filterFacilities(index, none, '')).toEqual([]);
  });

  it('空資料', () => {
    expect(filterFacilities(buildSearchIndex([]), allSelected, '')).toEqual([]);
  });
});

describe('countByCategory', () => {
  it('所有分類都會出現，沒有資料就是 0', () => {
    const counts = countByCategory(facilities);
    expect(Object.keys(counts)).toEqual(CATEGORY_KEYS);
    expect(counts.hospital).toBe(1);
    expect(counts.clinic).toBe(1);
    expect(counts.elementary_school).toBe(1);
    expect(counts.kindergarten).toBe(1);
    expect(counts.pharmacy).toBe(0);
    expect(counts.long_term_care).toBe(0);
  });

  it('空資料全部為 0', () => {
    expect(Object.values(countByCategory([])).every((value) => value === 0)).toBe(true);
  });
});
