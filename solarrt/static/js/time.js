// SolarRT time module - formatting + zones
// Moved from IIFE in solarrt/static/app.js
/* globals fmtTime, fmtDayTime, fmtCoord, wrapLon, zoneLabel, displayZone, browserZone */

(function () {
  "use strict";

  // Helper functions moved from app.js
  window.fmtTime = (iso, zone = displayZone()) => iso
      ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: zone }) : "–";
  window.fmtDayTime = (iso) => new Date(iso).toLocaleString([], {
    weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: displayZone()
  });
  window.fmtCoord = (lat, lon) =>
    `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? "E" : "W"}`;
  window.wrapLon = (lon) => ((((lon + 180) % 360) + 360) % 360) - 180;

  // Display zone logic
  const displayZone = () => (state.timeMode === "utc" ? "UTC" : state.tz || browserZone);
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const state = window.SOLARRT_STATE || { timeMode: "local" };
  const zoneLabel = (zone = displayZone(), when = new Date()) => {
    if (zone === "UTC") return "UTC";
    try {
      return new Intl.DateTimeFormat([], { timeZone: zone, timeZoneName: "short" })
          .formatToParts(when).find((p) => p.type === "timeZoneName")?.value || zone;
    } catch { return zone; }
  };

  // Export helpers
  window.zoneLabel = zoneLabel;
  window.displayZone = displayZone;
  window.browserZone = browserZone;
})();