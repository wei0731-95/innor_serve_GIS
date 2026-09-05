import { CATEGORY_CONFIG } from '../config/categories.js';
import { haversineDistance } from './geo.js';

/**
 * Coverage / Gap Analysis 擴充接口
 *
 * V1 只提供「純幾何」的服務範圍計算（設施座標 + 設定檔半徑），
 * 任何需要人口、需求、可及性資料的分析都尚未實作，呼叫時會拋出 NotImplementedError，
 * 絕不回傳虛構的人口數或 Gap Score。
 *
 * 規劃：
 * - V2 Coverage       : calculateCoverage() + CoverageLayer 顯示服務範圍圓
 * - V3 Gap Analysis   : calculateCoveredPopulation() / calculateGap()
 * - V4 Simulation     : simulateFacility()
 */

export class NotImplementedError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NotImplementedError';
  }
}

/**
 * 取得分類的服務半徑（公尺）。設定檔沒有明確定義時回傳 null，不自行假設。
 */
export function getCoverageRadius(category) {
  const radius = CATEGORY_CONFIG[category]?.coverageRadius;
  return Number.isFinite(radius) && radius > 0 ? radius : null;
}

/**
 * 產生每個設施的服務範圍圓（純幾何，不含任何人口 / 缺口推估）。
 *
 * @param {object[]} facilities 統一格式的設施
 * @param {object} [options]
 * @param {Record<string, number>} [options.radiusByCategory] 覆寫分類半徑（公尺）
 * @returns {Array<{ facilityId: string, category: string, center: {lat:number,lng:number}, radius: number }>}
 *          沒有半徑設定的分類會被略過
 */
export function calculateCoverage(facilities, { radiusByCategory = {} } = {}) {
  const circles = [];
  for (const facility of facilities) {
    const radius = radiusByCategory[facility.category] ?? getCoverageRadius(facility.category);
    if (radius == null) continue;
    circles.push({
      facilityId: facility.id,
      category: facility.category,
      center: { lat: facility.lat, lng: facility.lng },
      radius,
    });
  }
  return circles;
}

/**
 * 某個點是否落在任一服務範圍圓內（純幾何）。
 * @param {{lat:number,lng:number}} point
 * @param {ReturnType<typeof calculateCoverage>} coverageCircles
 */
export function isPointCovered(point, coverageCircles) {
  return coverageCircles.some((circle) => haversineDistance(point, circle.center) <= circle.radius);
}

/**
 * V3：計算被服務範圍涵蓋的人口。
 *
 * 預期輸入：
 * - coverageCircles : calculateCoverage() 的結果
 * - populationUnits : 真實人口統計單元，例如 [{ id, name, lat, lng, population }]（村里代表點）
 * 預期輸出：{ coveredPopulation, uncoveredPopulation, coveredUnitIds }
 */
export function calculateCoveredPopulation(/* coverageCircles, populationUnits */) {
  throw new NotImplementedError(
    'calculateCoveredPopulation 尚未實作：需要真實人口統計資料（例如村里人口與代表點）。V1 不產生任何人口推估。',
  );
}

/**
 * V3：計算服務缺口（Gap Score）。
 *
 * 概念：服務供給 + 人口需求 + 距離 / 可及性 → Gap Score
 * 預期輸入：{ facilities, populationUnits, category, options }
 * 預期輸出：[{ unitId, supply, demand, accessibility, gapScore }]
 */
export function calculateGap(/* { facilities, populationUnits, category, options } */) {
  throw new NotImplementedError(
    'calculateGap 尚未實作：需要服務供給、人口需求與可及性資料。V1 不產生任何 Gap Score。',
  );
}

/**
 * V4：模擬新增一間設施後的變化。
 *
 * 預期輸入：{ facilities, populationUnits, newFacility: { lat, lng, category } }
 * 預期輸出：{ before, after, deltaCoveredPopulation, deltaGapScore }
 */
export function simulateFacility(/* { facilities, populationUnits, newFacility } */) {
  throw new NotImplementedError(
    'simulateFacility 尚未實作：V4 設施模擬需先完成 Coverage 與 Gap Analysis。',
  );
}
