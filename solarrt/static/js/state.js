// SolarRT state module - shared state and localStorage helpers
// Moved from IIFE in solarrt/static/app.js
/* globals state */ // declared in app.js IIFE

(function () {
  "use strict";

  const STORE_KEY = "solarrt.location.v1";
  const TIME_KEY = "solarrt.timemode";

  const state = {
    grid: null,         // Uint8Array 181 x 360
    home: null,         // saved location {lat, lon, name, source}
    current: null,      // location currently shown (home or a clicked spot)
    errors: new Set(),
    stale: new Map(),   // key -> {stale, age} from the API's age_seconds
    updated: null,
    timeMode: "local",
    tz: null
  };

  // Initialize time mode from localStorage
  try {
    let timeMode = localStorage.getItem(TIME_KEY) || "local";
    state.timeMode = timeMode;
  } catch (e) { /* storage blocked */ }

  // Browser zone for display
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const displayZone = () => (state.timeMode === "utc" ? "UTC" : state.tz || browserZone);
  const zoneLabel = (zone = displayZone(), when = new Date()) => {
    if (zone === "UTC") return "UTC";
    try {
      return new Intl.DateTimeFormat([], { timeZone: zone, timeZoneName: "short" })
          .formatToParts(when).find((p) => p.type === "timeZoneName")?.value || zone;
    } catch { return zone; }
  };
  const fmtTime = (iso, zone = displayZone()) => iso
      ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: zone }) : "–";
  const fmtDayTime = (iso) => new Date(iso).toLocaleString([], {
    weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: displayZone()
  });
  const fmtCoord = (lat, lon) =>
    `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? "E" : "W"}`;
  const wrapLon = (lon) => ((((lon + 180) % 360) + 360) % 360) - 180;

  // Initialize time mode on load
  try { localStorage.setItem(TIME_KEY, "local"); } catch { /* storage blocked */ }

  // Export globals for use by app.js
  window.SOLARRT_STATE = state;
  window.SOLARRT_fmtTime = fmtTime;
  window.SOLARRT_fmtDayTime = fmtDayTime;
  window.SOLARRT_fmtCoord = fmtCoord;
  window.SOLARRT_wrapLon = wrapLon;
  window.zoneLabel = zoneLabel;
  window.displayZone = displayZone;
  window.browserZone = browserZone;

  // Initialize time mode on load
  try { localStorage.setItem(TIME_KEY, "local"); } catch { /* storage blocked */ }
})();