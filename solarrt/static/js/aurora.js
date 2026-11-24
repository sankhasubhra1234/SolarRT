// SolarRT aurora module - colour calculation and grid handling
// Moved from solarrt/static/app.js

"use strict";

import { STOPS } from "./constants.js";

/** Convert OVATION grid value (0..100) to rgba colour. */
export function auroraColor(v) {
    if (v < 1) return null; // fade in from 1%
    if (v <= STOPS[0][0]) {
        const c = STOPS[0][1];
        return [c[0], c[1], c[2], c[3] * (v / STOPS[0][0])];
    }
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

import { KP_REFRESH_MS, AURORA_REFRESH_MS } from "./main.js";
export { KP_REFRESH_MS, AURORA_REFRESH_MS };