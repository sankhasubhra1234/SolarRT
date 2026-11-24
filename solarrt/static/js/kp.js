// SolarRT Kp module - Kp card + chart functionality
// Moved from solarrt/static/app.js
/* globals STOPS, auroraColor, KP_REFRESH_MS, AURORA_REFRESH_MS */

(function () {
  "use strict";

  const KP_REFRESH_MS = 60_000;
  const AURORA_REFRESH_MS = 5 * 60_000;

  // Aurora colour scale stops (value 0..100 -> rgba). Must match app.js STOPS.
  window.STOPS = [
    [5, [40, 200, 110, 0.30]],    // 5% -> soft green edge
    [25, [43, 217, 138, 0.75]],   // 25% -> lime
    [50, [232, 226, 58, 0.85]],   // 50% -> yellow
    [70, [255, 138, 43, 0.90]],   // 70% -> orange
    [90, [255, 51, 85, 0.95]],    // 90% -> red
  ];

  // Kp colour scale (value -> rgba)
  window.auroraColor = (v) => {
    if (v < 1) return null; // fade in from 1% so the oval has soft edges
    if (v <= STOPS[0][0]) { const c = STOPS[0][1]; return [c[0], c[1], c[2], c[3] * (v / STOPS[0][0])]; }
    for (let i = 1; i < STOPS.length; i++) {
      const [v1, c1] = STOPS[i];
      if (v <= v1) {
        const [v0, c0] = STOPS[i - 1];
        const t = (v - v0) / (v1 - v0);
        return c0.map((x, k) => x + (c1[k] - x) * t);
      }
    }
    return STOPS[STOPS.length - 1][1];
  }

  // Export constants
  window.KP_REFRESH_MS = KP_REFRESH_MS;
  window.AURORA_REFRESH_MS = AURORA_REFRESH_MS;
})();