import { memo } from 'react';
import { Marker, Popup } from 'react-leaflet';
import { getCategoryIcon } from '../../utils/leafletIcon.js';
import { getDisplayName } from '../../utils/normalizeFacility.js';
import FacilityPopup from '../Facility/FacilityPopup.jsx';

/**
 * 單一設施 marker。
 * 用 memo 包住：只要 facility 物件沒變（資料只 normalize 一次，物件是穩定的），
 * 搜尋 / 篩選造成的父層 re-render 就不會重建 marker。
 */
function FacilityMarker({ facility }) {
  return (
    <Marker
      position={[facility.lat, facility.lng]}
      icon={getCategoryIcon(facility.category)}
      title={getDisplayName(facility)}
    >
      <Popup>
        <FacilityPopup facility={facility} />
      </Popup>
    </Marker>
  );
}

export default memo(FacilityMarker);
