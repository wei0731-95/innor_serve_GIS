import { useEffect } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { TAIPEI_CITY_HALL } from '../../utils/geo.js';
import FacilityMarker from './FacilityMarker.jsx';
import CoverageLayer from './CoverageLayer.jsx';

const DEFAULT_CENTER = [TAIPEI_CITY_HALL.lat, TAIPEI_CITY_HALL.lng];
const DEFAULT_ZOOM = 12;

// OpenStreetMap 標準圖磚（依 OSM 使用政策，需保留 attribution）
const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

/** Sidebar 收合 / 展開時地圖容器尺寸改變，通知 Leaflet 重新計算，避免圖磚缺角 */
function MapResizeHandler() {
  const map = useMap();

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);

  return null;
}

/**
 * 主地圖。
 * - 不使用瀏覽器 geolocation，預設中心固定在臺北市政府附近
 * - 所有 marker 都放在 MarkerClusterGroup 內，zoom out 聚合、zoom in 展開
 * - CoverageLayer 為 V2 擴充接口，V1 預設不顯示
 */
export default function FacilityMap({ facilities, showCoverage = false }) {
  return (
    <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} className="facility-map" scrollWheelZoom>
      <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} maxZoom={19} />

      <MarkerClusterGroup chunkedLoading maxClusterRadius={60} spiderfyOnMaxZoom showCoverageOnHover={false}>
        {facilities.map((facility) => (
          <FacilityMarker key={facility.id} facility={facility} />
        ))}
      </MarkerClusterGroup>

      <CoverageLayer facilities={facilities} enabled={showCoverage} />
      <MapResizeHandler />
    </MapContainer>
  );
}
