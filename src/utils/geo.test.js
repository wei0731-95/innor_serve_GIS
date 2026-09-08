import { describe, expect, it } from 'vitest';
import { haversineDistance, isValidLatLng, isWithinRadius, TAIPEI_CITY_HALL, toCoordinate } from './geo.js';

describe('toCoordinate', () => {
  it('接受純數字字串與數值', () => {
    expect(toCoordinate('25.03553921')).toBe(25.03553921);
    expect(toCoordinate(' 121.5183428 ')).toBe(121.5183428);
    expect(toCoordinate(121.5)).toBe(121.5);
    expect(toCoordinate('-25.5')).toBe(-25.5);
  });

  it('拒絕空值、非數字、部分數字（不會用 parseFloat 部分解析）', () => {
    for (const value of ['', '   ', null, undefined, 'N/A', '25.03abc', 'abc', '1e2', NaN, Infinity]) {
      expect(Number.isNaN(toCoordinate(value))).toBe(true);
    }
  });
});

describe('isValidLatLng', () => {
  it('合法座標', () => {
    expect(isValidLatLng(25.0375, 121.5637)).toBe(true);
  });

  it('無效座標：NaN、超出範圍、(0, 0)', () => {
    expect(isValidLatLng(NaN, 121.5)).toBe(false);
    expect(isValidLatLng(25.0, NaN)).toBe(false);
    expect(isValidLatLng(95, 121.5)).toBe(false);
    expect(isValidLatLng(25, 190)).toBe(false);
    expect(isValidLatLng(0, 0)).toBe(false);
    expect(isValidLatLng(null, null)).toBe(false);
  });
});

describe('haversineDistance', () => {
  it('臺北市政府到臺北車站約 4.5 到 5.2 公里', () => {
    const taipeiMainStation = { lat: 25.0478, lng: 121.517 };
    const distance = haversineDistance(TAIPEI_CITY_HALL, taipeiMainStation);
    expect(distance).toBeGreaterThan(4500);
    expect(distance).toBeLessThan(5200);
  });

  it('同一點距離為 0，且對稱', () => {
    expect(haversineDistance(TAIPEI_CITY_HALL, TAIPEI_CITY_HALL)).toBe(0);
    const other = { lat: 25.1, lng: 121.5 };
    expect(haversineDistance(TAIPEI_CITY_HALL, other)).toBeCloseTo(haversineDistance(other, TAIPEI_CITY_HALL), 6);
  });

  it('isWithinRadius', () => {
    const nearby = { lat: 25.038, lng: 121.564 };
    expect(isWithinRadius(TAIPEI_CITY_HALL, nearby, 500)).toBe(true);
    expect(isWithinRadius(TAIPEI_CITY_HALL, { lat: 25.1, lng: 121.5 }, 500)).toBe(false);
  });
});
