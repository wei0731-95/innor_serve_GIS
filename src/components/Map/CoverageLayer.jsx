import { useMemo } from 'react';
import { Circle } from 'react-leaflet';
import { getCategoryConfig } from '../../config/categories.js';
import { calculateCoverage } from '../../utils/coverage.js';

/**
 * V2 Coverage 擴充接口：依分類服務半徑畫出服務範圍圓。
 *
 * - V1 預設 enabled = false，不會渲染任何東西
 * - 半徑一律來自 config/categories.js 的 coverageRadius（或 radiusByCategory 覆寫），
 *   沒有定義半徑的分類會被 calculateCoverage 略過，不會自行假設
 * - 這一層只畫「幾何範圍」，不做任何人口 / 缺口推估
 *
 * 未來使用方式：<CoverageLayer facilities={filtered} enabled={showCoverage} />
 */
export default function CoverageLayer({ facilities, enabled = false, radiusByCategory }) {
  const circles = useMemo(
    () => (enabled ? calculateCoverage(facilities, { radiusByCategory }) : []),
    [enabled, facilities, radiusByCategory],
  );

  if (!enabled || circles.length === 0) return null;

  return circles.map((circle) => (
    <Circle
      key={circle.facilityId}
      center={[circle.center.lat, circle.center.lng]}
      radius={circle.radius}
      pathOptions={{
        color: getCategoryConfig(circle.category).markerColor,
        weight: 1,
        fillOpacity: 0.08,
      }}
    />
  ));
}
