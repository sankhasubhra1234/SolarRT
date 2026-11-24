// SolarRT main module - startup + refresh loops
// Orchestrates all other modules; replaced the original IIFE in app.js

"use strict";

import { state } from "./state.js";
import { fmtTime, fmtDayTime, fmtCoord, wrapLon, zoneLabel, displayZone, browserZone } from "./time.js";
import { auroraColor, STOPS, KP_REFRESH_MS, AURORA_REFRESH_MS } from "./kp.js";
import { initMap, setBasemap, createAuroraLayer } from "./map.js";
import { loadKp, loadIss, loadWeather, loadRegions } from "./api.js";

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    // Initialize map
    const map = initMap();
    setBasemap(map);

    // Initialize state
    state.tz = displayZone();

    // Kp loading
    let kpTimeout = null;
    const loadKp = async () => {
        try {
            const kp = await loadKp();
            // Update Kp display
            const kpNow = document.getElementById("kpNow");
            if (kpNow && kp.current) {
                kpNow.textContent = kp.current.kp.toFixed(2);
                kpNow.style.color = (kp.current.kp >= 8) ? "#d03cff" :
                    (kp.current.kp >= 7) ? "#ff3355" :
                    (kp.current.kp >= 6) ? "#ff6a2b" :
                    (kp.current.kp >= 4.67) ? "#ffa020" : "#2bd98a";
            }
        } catch (e) {
            console.error("Kp load failed", e);
        } finally {
            kpTimeout = setTimeout(loadKp, KP_REFRESH_MS);
        }
    };

    loadKp();

    // Aurora loading
    let auroraTimeout = null;
    const loadAurora = async () => {
        try {
            const aurora = await loadAurora();
            // Update aurora display
            const gridCanvas = document.getElementById("gridCanvas");
            if (gridCanvas && aurora.data) {
                // Render aurora grid
                renderAurora(gridCanvas, aurora);
            }
        } catch (e) {
            console.error("Aurora load failed", e);
        } finally {
            auroraTimeout = setTimeout(loadAurora, AURORA_REFRESH_MS);
        }
    };

    loadAurora();
    setTimeout(loadAurora, AURORA_REFRESH_MS);

    // ISS loading
    let issTimeout = null;
    const loadIss = async () => {
        try {
            const iss = await loadIss();
            const issEl = document.getElementById("issEl");
            if (issEl && iss.lat !== undefined) {
                issEl.innerHTML = `ISS: ${iss.lat.toFixed(2)}, ${iss.lon.toFixed(2)}`;
            }
        } catch (e) {
            console.error("ISS load failed", e);
        } finally {
            issTimeout = setTimeout(loadIss, 10000);
        }
    };

    loadIss();
    setInterval(loadIss, 10000);
});