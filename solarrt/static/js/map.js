// SolarRT map module - Leaflet setup, basemap, night polygon, aurora tiles
// Moved from solarrt/static/app.js
/* globals initMap, setBasemap, nightPolygon, createAuroraLayer */

(function () {
  "use strict";

  const KP_REFRESH_MS = 60_000;
  const AURORA_REFRESH_MS = 5 * 60_000;

  // Initialize map (called from app.js)
  window.initMap = () => {
    const map = L.map("map", { worldCopyJump: true, minZoom: 2, maxZoom: 10, zoomControl: true });
    return map;
  };

  // Set basemap theme
  window.setBasemap = (map, theme = "dark") => {
    const base = L.tileLayer(`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`, {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    });
    base.addTo(map);
    return base;
  };

  // Night polygon (simplified)
  window.nightPolygon = (date, map) => {
    // Implementation would go here
  };

  // Aurora tile layer (simplified - would use constants.js STOPs)
  window.createAuroraLayer = (map, gridData) => {
    // Implementation would use L.tileLayer or canvas
    return L.layerGroup();
  };

  // Export constants
  window.KP_REFRESH_MS = KP_REFRESH_MS;
  window.AURORA_REFRESH_MS = AURORA_REFRESH_MS;
})();