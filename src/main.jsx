import React from 'react';
import ReactDOM from 'react-dom/client';

// Leaflet 與 MarkerCluster 的 CSS 一定要載入，否則地圖 tile 會錯位、cluster 沒有樣式
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import './index.css';

import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
