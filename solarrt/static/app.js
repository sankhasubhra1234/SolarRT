/* SolarRT web client: aurora map, Kp panel, location & regional activity. */
(() => {
  "use strict";
  const KP_REFRESH_MS = 60_000;
  const AURORA_REFRESH_MS = 5 * 60_000;
  const STORE_KEY = "solarrt.location.v1";
  const $ = (id) => document.getElementById(id);

  const state = {
    grid: null,         // Uint8Array 181 x 360
    home: null,         // saved location {lat, lon, name, source}
    current: null,      // location currently shown (home or a clicked spot)
    errors: new Set(),
    stale: new Map(),   // key -> {stale, age} from the API's age_seconds
    updated: null,
  };

  // ------------------------------------------------------------------ platform
  // config.js sets window.SOLARRT_CONFIG. On the website and desktop app it is empty (the API
  // is on the same server); the mobile app sets apiBase to the hosted SolarRT server.
  const CONFIG = window.SOLARRT_CONFIG || {};
  const API_BASE = (CONFIG.apiBase || "").replace(/\/+$/, "");
  const Native = window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()
    ? window.Capacitor : null;
  const nativePlugin = (name) => (Native && Native.Plugins ? Native.Plugins[name] : null);
  const edition = () => (Native ? Native.getPlatform() : isDesktop() ? "desktop" : "web");

  // ------------------------------------------------------------------ helpers
  async function api(path) {
    const r = await fetch(API_BASE + path, { headers: { Accept: "application/json" } });
    if (!r.ok) {
      let msg = `${r.status}`;
      try { msg = (await r.json()).detail || msg; } catch { /* not JSON */ }
      throw new Error(msg);
    }
    return r.json();
  }

  // Times are shown either in the selected location's own time zone ("local") or in UTC,
  // the standard for space-weather data. The location's zone comes with its weather data.
  const TIME_KEY = "solarrt.timemode";
  let timeMode = "local";
  try { timeMode = localStorage.getItem(TIME_KEY) || "local"; } catch { /* storage blocked */ }
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const displayZone = () => (timeMode === "utc" ? "UTC" : state.tz || browserZone);
  function zoneLabel(zone = displayZone(), when = new Date()) {
    if (zone === "UTC") return "UTC";
    try {
      return new Intl.DateTimeFormat([], { timeZone: zone, timeZoneName: "short" })
        .formatToParts(when).find((p) => p.type === "timeZoneName")?.value || zone;
    } catch { return zone; }
  }
  const fmtTime = (iso, zone = displayZone()) => iso
    ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: zone }) : "–";
  const fmtDayTime = (iso) => new Date(iso).toLocaleString([], {
    weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: displayZone() });
  const fmtCoord = (lat, lon) =>
    `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? "E" : "W"}`;
  const wrapLon = (lon) => ((((lon + 180) % 360) + 360) % 360) - 180;

  function setStatus() {
    const el = $("status");
    if (state.errors.size) {
      el.textContent = `⚠ ${[...state.errors][0]}`;
      el.className = "status error";
      return;
    }
    // The API marks data it had to serve from an old cache after an upstream failure. Never
    // present that as "Updated": show when the data is actually from and which feed it is.
    const stale = [...state.stale.entries()].filter(([, v]) => v.stale)
      .sort((a, b) => b[1].age - a[1].age);
    if (stale.length) {
      const [key, v] = stale[0];
      const when = new Date(Date.now() - v.age * 1000);
      el.textContent = `Data from ${fmtTime(when.toISOString())} · stale (${key})`;
      el.className = "status warn";
      return;
    }
    if (state.updated) {
      el.textContent = `Updated ${fmtTime(state.updated.toISOString())}`;
      el.className = "status";
    }
  }
  function staleInfo(v) {
    // Some calls resolve an array (e.g. aurora + regions); report the first stale member.
    if (Array.isArray(v)) {
      for (const item of v) { const s = staleInfo(item); if (s) return s; }
      return null;
    }
    if (v && typeof v === "object" && "stale" in v) {
      return { stale: !!v.stale, age: Number(v.age_seconds) || 0 };
    }
    return null;
  }
  function track(key, promise) {
    return promise.then((v) => {
      state.errors.delete(key);
      const s = staleInfo(v);
      if (s) state.stale.set(key, s); else state.stale.delete(key);
      if (!s || !s.stale) state.updated = new Date();
      setStatus();
      return v;
    })
      .catch((e) => { console.error(key, e); state.errors.add(`${key}: ${e.message}`); setStatus(); });
  }

  // Aurora colour scale (value 0..100 -> rgba). Matches the CSS legend.
  const STOPS = [
    [5, [40, 200, 110, 0.30]],
    [25, [43, 217, 138, 0.75]],
    [50, [232, 226, 58, 0.85]],
    [70, [255, 138, 43, 0.90]],
    [90, [255, 51, 85, 0.95]],
  ];
  function auroraColor(v) {
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
  const cssColor = (v) => { const c = auroraColor(Math.max(v, 5)); return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},1)`; };

  function kpColor(kp) {
    if (kp >= 8) return "#d03cff";
    if (kp >= 7) return "#ff3355";
    if (kp >= 6) return "#ff6a2b";
    if (kp >= 4.67) return "#ffa020";
    if (kp >= 4) return "#e8e23a";
    return "#2bd98a";
  }

  function sampleGrid(lat, lon) {
    const g = state.grid;
    if (!g || lat < -90 || lat > 90) return 0;
    const x = ((lon % 360) + 360) % 360, y = lat + 90;
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const x1 = (x0 + 1) % 360, y1 = Math.min(y0 + 1, 180);
    const fx = x - x0, fy = y - y0;
    const v = (yy, xx) => g[yy * 360 + xx];
    return (v(y0, x0) * (1 - fx) + v(y0, x1) * fx) * (1 - fy) + (v(y1, x0) * (1 - fx) + v(y1, x1) * fx) * fy;
  }

  // ------------------------------------------------------------------ map
  const map = L.map("map", { worldCopyJump: true, minZoom: 2, maxZoom: 10, zoomControl: true })
    .setView([60, 0], 3);
  const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";
  const tileUrl = (tone, kind) => `${ESRI}/World_${tone}_Gray_${kind}/MapServer/tile/{z}/{y}/{x}`;
  const baseTiles = L.tileLayer(tileUrl("Dark", "Base"), {
    maxZoom: 16,
    attribution: "&copy; Esri &middot; OpenStreetMap &middot; NOAA SWPC &middot; CelesTrak",
  }).addTo(map);
  // Place labels sit above the aurora overlay so they stay readable.
  map.createPane("labels");
  map.getPane("labels").style.zIndex = 450;
  map.getPane("labels").style.pointerEvents = "none";
  const labelTiles = L.tileLayer(tileUrl("Dark", "Reference"), { maxZoom: 16, pane: "labels" }).addTo(map);
  function setBasemap(theme) {
    const tone = theme === "light" ? "Light" : "Dark";
    baseTiles.setUrl(tileUrl(tone, "Base"));
    labelTiles.setUrl(tileUrl(tone, "Reference"));
  }
  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const AuroraLayer = L.GridLayer.extend({
    createTile(coords) {
      const size = this.getTileSize();
      const canvas = L.DomUtil.create("canvas", "leaflet-tile");
      canvas.width = size.x; canvas.height = size.y;
      if (!state.grid) return canvas;
      const ctx = canvas.getContext("2d");
      const step = 4;
      const origin = coords.scaleBy(size);
      for (let py = 0; py < size.y; py += step) {
        const lat = map.unproject([origin.x, origin.y + py + step / 2], coords.z).lat;
        if (Math.abs(lat) < 35) continue; // aurora never reaches the tropics; skip work
        for (let px = 0; px < size.x; px += step) {
          const ll = map.unproject([origin.x + px + step / 2, origin.y + py + step / 2], coords.z);
          const c = auroraColor(sampleGrid(ll.lat, ll.lng));
          if (!c) continue;
          ctx.fillStyle = `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${c[3].toFixed(3)})`;
          ctx.fillRect(px, py, step, step);
        }
      }
      return canvas;
    },
  });
  const auroraLayer = new AuroraLayer({ opacity: 0.9, zIndex: 300 }).addTo(map);

  // Day/night shading so users can see where it is dark enough to see the aurora.
  function nightPolygon(date) {
    const d = date || new Date();
    const jd = d.getTime() / 86400000 + 2440587.5, n = jd - 2451545.0;
    const L0 = (280.46 + 0.9856474 * n) % 360, g = ((357.528 + 0.9856003 * n) % 360) * Math.PI / 180;
    const lambda = (L0 + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * Math.PI / 180;
    const eps = (23.439 - 0.0000004 * n) * Math.PI / 180;
    const decl = Math.asin(Math.sin(eps) * Math.sin(lambda));
    const ra = Math.atan2(Math.cos(eps) * Math.sin(lambda), Math.cos(lambda));
    const gmst = (18.697374558 + 24.06570982441908 * n) % 24;
    const pts = [];
    for (let lon = -180; lon <= 180; lon += 2) {
      const ha = (gmst * 15 + lon) * Math.PI / 180 - ra;
      const lat = Math.atan(-Math.cos(ha) / Math.tan(decl)) * 180 / Math.PI;
      pts.push([lat, lon]);
    }
    const pole = decl > 0 ? -90 : 90;
    return [[pole, -180], ...pts, [pole, 180]];
  }
  const night = L.polygon(nightPolygon(), {
    stroke: false, fillColor: "#000814", fillOpacity: 0.35, interactive: false,
  }).addTo(map);
  setInterval(() => night.setLatLngs(nightPolygon()), 60_000);

  L.control.layers(null, { "Aurora forecast": auroraLayer, "Night side": night },
    { position: "topright", collapsed: true }).addTo(map);

  const youIcon = L.divIcon({ className: "", html: '<div class="you-marker"></div>', iconSize: [16, 16] });
  let marker = null;

  // Choosing a spot on the map is an explicit mode ("Pick on map"), so stray clicks
  // while panning or exploring never change the user's location.
  function setPicking(on) {
    state.picking = on;
    map.getContainer().classList.toggle("picking", on);
    $("pickBanner").hidden = !on;
    $("pickBtn").setAttribute("aria-pressed", String(on));
    $("pickBtn").textContent = on ? "✕ Cancel" : "📌 Pick on map";
  }
  $("pickBtn").addEventListener("click", () => setPicking(!state.picking));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.picking) setPicking(false); });

  map.on("click", (e) => {
    if (!state.picking) return;
    setPicking(false);
    const lat = e.latlng.lat, lon = wrapLon(e.latlng.lng);
    showLocation({ lat, lon, name: "Selected spot", source: "map" }, false);
    reverseName(lat, lon).then((name) => {
      if (name && state.current && state.current.lat === lat) {
        state.current.name = name; renderLocName();
      }
    });
  });

  // ------------------------------------------------------------------ aurora + regions
  async function loadAurora() {
    const d = await api("/api/aurora");
    const bin = atob(d.data);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    state.grid = arr;
    auroraLayer.redraw();
    state.auroraTime = d.forecast_time;
    updateMapCaption();
    return d;
  }

  async function loadRegions() {
    const d = await api("/api/regions");
    const ul = $("regions");
    ul.replaceChildren();
    for (const r of d.regions) {
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.title = `Show ${r.name} on the map`;
      const name = document.createElement("div");
      name.textContent = r.name;
      const lvl = document.createElement("span");
      lvl.className = "lvl";
      lvl.textContent = `${r.level} · ${r.hemisphere === "north" ? "Northern" : "Southern"} hemisphere`;
      name.append(lvl);
      const bar = document.createElement("div");
      bar.className = "bar";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(2, r.max)}%`;
      fill.style.background = r.max >= 5 ? cssColor(r.max) : "#3a465e";
      bar.append(fill);
      const pct = document.createElement("div");
      pct.className = "pct";
      pct.textContent = `${r.max}%`;
      li.append(name, bar, pct);
      const go = () => {
        const [[s, w], [n, e]] = r.bounds;
        map.fitBounds([[Math.max(s, -80), w], [Math.min(n, 82), e < w ? e + 360 : e]], { maxZoom: 6 });
      };
      li.addEventListener("click", go);
      li.addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
      ul.append(li);
    }
    return d;
  }

  // ------------------------------------------------------------------ Kp
  async function loadKp() {
    const d = await api("/api/kp");
    const c = d.current;
    if (c) {
      $("kpNow").textContent = c.kp.toFixed(2);
      $("kpNow").style.color = kpColor(c.kp);
      $("kpNowSub").textContent = `current estimate · ${c.label} · ${fmtTime(c.time)}`;
      $("kpBadge").textContent = `${c.g_label}`;
      $("kpBadge").style.borderColor = kpColor(c.kp);
      $("kpBadge").style.color = kpColor(c.kp);
    }
    state.kp = c || null;
    checkAlerts();
    $("kp3h").textContent = d.last_3h ? `${d.last_3h.kp.toFixed(2)} (${d.last_3h.label})` : "–";
    $("kpMax").textContent = d.max_24h != null ? d.max_24h.toFixed(2) : "–";
    const p = d.forecast_peak_24h;
    $("kpPeak").textContent = p ? `${p.kp.toFixed(2)} (${p.g_label.split(" ")[0]}) ${fmtTime(p.time)}` : "–";
    if (p) $("kpPeak").style.color = kpColor(p.kp);
    drawKpChart(d.series);
    return d;
  }

  let lastSeries = null;
  function drawKpChart(series) {
    const el = $("kpChart");
    const now = Date.now();
    const pts = series.filter((p) => new Date(p.time).getTime() >= now - 3 * 86400000);
    if (!pts.length) { el.textContent = "No Kp data"; return; }
    lastSeries = series;
    const W = Math.max(240, el.clientWidth || 370), H = 150, padL = 22, padB = 18, padT = 6;
    const iw = W - padL - 4, ih = H - padB - padT;
    const bw = iw / pts.length;
    const y = (kp) => padT + ih - (kp / 9) * ih;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const add = (tag, attrs, text) => {
      const n = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      if (text != null) n.textContent = text;
      svg.append(n); return n;
    };
    const lineColor = cssVar("--line"), textColor = cssVar("--text");
    for (const k of [0, 3, 5, 7, 9]) {
      add("line", { x1: padL, x2: W - 4, y1: y(k), y2: y(k), stroke: k === 5 ? "#ffa020" : lineColor,
        "stroke-dasharray": k === 5 ? "4 3" : "", "stroke-width": 1 });
      add("text", { x: padL - 5, y: y(k) + 3, "text-anchor": "end" }, k);
    }
    add("text", { x: W - 6, y: y(5) - 3, "text-anchor": "end", fill: "#ffa020" }, "G1 storm");
    let lastDay = null;
    pts.forEach((p, i) => {
      const t = new Date(p.time);
      const x = padL + i * bw;
      const h = Math.max(1.5, (p.kp / 9) * ih);
      const color = kpColor(p.kp);
      const rect = add("rect", { x: x + 1, y: y(p.kp), width: Math.max(1, bw - 2), height: h, rx: 1.5 });
      if (p.kind === "predicted") {
        rect.setAttribute("fill", color); rect.setAttribute("fill-opacity", "0.18");
        rect.setAttribute("stroke", color); rect.setAttribute("stroke-dasharray", "2 2");
      } else {
        rect.setAttribute("fill", color);
        rect.setAttribute("fill-opacity", p.kind === "estimated" ? "0.55" : "0.95");
      }
      const tip = document.createElementNS(ns, "title");
      tip.textContent = `${t.toUTCString().slice(5, 22)} UTC — Kp ${p.kp} (${p.kind})`;
      rect.append(tip);
      const day = t.getUTCDate();
      if (day !== lastDay && t.getUTCHours() === 0) {
        add("line", { x1: x, x2: x, y1: padT, y2: H - padB, stroke: lineColor });
        add("text", { x: x + 3, y: H - 5 }, t.toLocaleDateString([], { month: "short", day: "numeric", timeZone: "UTC" }));
      }
      lastDay = day;
    });
    const t0 = new Date(pts[0].time).getTime();
    const nowX = padL + ((now - t0) / (3 * 3600000)) * bw;
    if (nowX > padL && nowX < W - 4) {
      add("line", { x1: nowX, x2: nowX, y1: padT, y2: H - padB, stroke: textColor, "stroke-width": 1.2 });
      add("text", { x: nowX + 3, y: padT + 9, fill: textColor }, "now");
    }
    el.replaceChildren(svg);
  }

  // ------------------------------------------------------------------ location
  function saveHome(loc) {
    state.home = loc;
    try { localStorage.setItem(STORE_KEY, JSON.stringify(loc)); } catch { /* storage blocked */ }
  }
  function loadHome() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "null"); } catch { return null; }
  }

  function renderLocName() {
    const c = state.current;
    $("locName").textContent = c.name || "Unknown place";
    const src = { ip: "approximate, from your IP address", gps: "from your device", search: "searched",
      map: "picked on the map", saved: "saved" }[c.source] || "";
    $("locCoords").textContent = `${fmtCoord(c.lat, c.lon)}${src ? " · " + src : ""}`;
    if (c.source === "map" && state.home) {
      const back = document.createElement("button");
      back.className = "ghost small"; back.type = "button"; back.style.marginLeft = "8px";
      back.textContent = "↺ back to my location";
      back.onclick = () => showLocation(state.home, false);
      $("locCoords").append(back);
    }
  }

  async function showLocation(loc, save = true, fly = true) {
    state.current = { ...loc };
    state.tz = null; // the new place's time zone arrives with its weather
    if (save) saveHome(loc);
    renderLocName();
    tickClock();
    const ll = [loc.lat, loc.lon];
    if (!marker) marker = L.marker(ll, { icon: youIcon, keyboard: false, title: "Your location" }).addTo(map);
    else marker.setLatLng(ll);
    if (fly) map.flyTo(ll, Math.max(map.getZoom(), 3), { duration: 0.8 });
    await track("Location", refreshLocationStats());
  }

  async function refreshLocationStats() {
    const c = state.current;
    if (!c) return;
    const q = `lat=${c.lat.toFixed(4)}&lon=${c.lon.toFixed(4)}`;
    const wx = track("Weather", api(`/api/weather?${q}`).then((w) => {
      state.wx = w; renderWeather(w); return w;
    }));
    const d = await api(`/api/location?${q}`);
    state.loc = d;
    wx.then(() => checkAlerts());
    $("locProb").textContent = `${Math.round(d.probability)}%`;
    $("locProb").style.color = d.probability >= 5 ? cssColor(d.probability) : "var(--text)";
    $("locVerdict").textContent = d.verdict;
    $("locSky").textContent = `Sky: ${d.sky} (Sun ${d.sun_elevation > 0 ? "+" : ""}${d.sun_elevation}°)`;
    $("locNearby").textContent = d.nearby.max
      ? `Strongest within ${d.nearby.radius_km} km: ${d.nearby.max}% (${d.nearby.distance_km} km away)`
      : `No aurora within ${d.nearby.radius_km} km`;
    marker.bindPopup(`<strong>${escapeHtml(c.name || "Location")}</strong><br>Aurora chance: ${Math.round(d.probability)}%<br>${escapeHtml(d.verdict)}`);
    return d;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  }

  async function reverseName(lat, lon) {
    try { return (await api(`/api/reverse?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}`)).name; }
    catch { return null; }
  }

  async function locateByIp() {
    const providers = [
      ["https://get.geojs.io/v1/ip/geo.json", (j) => ({ lat: +j.latitude, lon: +j.longitude, city: j.city, country: j.country })],
      ["https://ipapi.co/json/", (j) => ({ lat: +j.latitude, lon: +j.longitude, city: j.city, country: j.country_name })],
    ];
    for (const [url, map] of providers) {
      try {
        const r = await fetch(url);
        if (!r.ok) continue;
        const p = map(await r.json());
        if (Number.isFinite(p.lat) && Number.isFinite(p.lon)) {
          return { lat: p.lat, lon: p.lon, name: [p.city, p.country].filter(Boolean).join(", "), source: "ip" };
        }
      } catch { /* try next provider */ }
    }
    return null;
  }

  function gpsErrorText(err) {
    if (err && err.code === 1) return "Location permission was denied.";
    if (err && err.code === 3) return "Finding your location took too long.";
    return (err && err.message) || "Your location isn't available on this device.";
  }

  async function getGpsPosition() {
    const geo = nativePlugin("Geolocation");
    if (geo) {  // Android/iOS app: use the native location service and permission prompt
      let perm = await geo.checkPermissions();
      if (perm.location !== "granted" && perm.coarseLocation !== "granted") perm = await geo.requestPermissions();
      if (perm.location !== "granted" && perm.coarseLocation !== "granted") {
        throw Object.assign(new Error("Location permission was denied."), { code: 1 });
      }
      // Quick network-based fix first; if the phone can't give one (no Wi-Fi/cell location),
      // fall back to GPS, which takes longer but works anywhere with sky view.
      try {
        return await geo.getCurrentPosition({ enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
      } catch {
        return geo.getCurrentPosition({ enableHighAccuracy: true, timeout: 30000, maximumAge: 600000 });
      }
    }
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) { reject(new Error("This browser can't share your location.")); return; }
      navigator.geolocation.getCurrentPosition(resolve, reject,
        { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
    });
  }

  // Ask the device for the current position and make it the saved home location.
  async function useCurrentLocation() {
    const pos = await getGpsPosition();
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    await showLocation({ lat, lon, name: "My location", source: "gps" });
    const name = await reverseName(lat, lon);
    if (name) { state.current.name = name; saveHome(state.current); renderLocName(); }
  }

  async function locateByGps() {
    $("gpsBtn").disabled = true;
    $("gpsBtn").textContent = "Locating…";
    try {
      await useCurrentLocation();
    } catch (err) {
      toast("Couldn't get your location", `${gpsErrorText(err)} You can search for a place instead.`);
    } finally {
      $("gpsBtn").disabled = false; $("gpsBtn").textContent = "◎ Locate me";
    }
  }

  // Place search with result list (keyboard accessible).
  const input = $("searchInput"), results = $("searchResults");
  let searchSeq = 0;
  $("searchForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (q.length < 2) return;
    const seq = ++searchSeq;
    results.hidden = false;
    results.innerHTML = "<li aria-disabled='true'>Searching…</li>";
    try {
      const d = await api(`/api/geocode?q=${encodeURIComponent(q)}`);
      if (seq !== searchSeq) return;
      results.replaceChildren();
      if (!d.results.length) { results.innerHTML = "<li aria-disabled='true'>No places found</li>"; return; }
      for (const r of d.results) {
        const li = document.createElement("li");
        li.textContent = r.name;
        li.tabIndex = 0;
        const pick = () => {
          results.hidden = true; input.value = "";
          const short = r.name.split(",").map((s) => s.trim());
          showLocation({ lat: r.lat, lon: r.lon, name: [short[0], short[short.length - 1]].filter((v, i, a) => a.indexOf(v) === i).join(", "), source: "search" });
        };
        li.addEventListener("click", pick);
        li.addEventListener("keydown", (ev) => { if (ev.key === "Enter") pick(); });
        results.append(li);
      }
    } catch (err) {
      results.innerHTML = "";
      const li = document.createElement("li");
      li.textContent = `Search failed: ${err.message}`;
      results.append(li);
    }
  });
  document.addEventListener("click", (e) => { if (!$("searchForm").contains(e.target)) results.hidden = true; });
  input.addEventListener("keydown", (e) => { if (e.key === "Escape") results.hidden = true; });
  $("gpsBtn").addEventListener("click", locateByGps);

  // ------------------------------------------------------------------ theme (auto / light / dark)
  const THEME_KEY = "solarrt.theme";
  const THEME_ORDER = ["auto", "light", "dark"];
  const THEME_LABEL = { auto: "◐ Auto", light: "☀ Light", dark: "☾ Dark" };
  const darkQuery = matchMedia("(prefers-color-scheme: dark)");
  let themePref = "auto";
  try { themePref = localStorage.getItem(THEME_KEY) || "auto"; } catch { /* storage blocked */ }
  const resolvedTheme = () => themePref === "auto" ? (darkQuery.matches ? "dark" : "light") : themePref;
  function applyTheme() {
    const t = resolvedTheme();
    document.documentElement.dataset.theme = t;
    $("themeBtn").textContent = THEME_LABEL[themePref];
    $("themeBtn").title = `Theme: ${themePref} (click to change)`;
    setBasemap(t);
    night.setStyle(t === "dark" ? { fillColor: "#000814", fillOpacity: 0.35 } : { fillColor: "#0b1a3a", fillOpacity: 0.16 });
    if (lastSeries) drawKpChart(lastSeries);
  }
  $("themeBtn").addEventListener("click", () => {
    themePref = THEME_ORDER[(THEME_ORDER.indexOf(themePref) + 1) % THEME_ORDER.length];
    try { localStorage.setItem(THEME_KEY, themePref); } catch { /* storage blocked */ }
    applyTheme();
  });
  darkQuery.addEventListener("change", () => { if (themePref === "auto") applyTheme(); });
  applyTheme();

  // ------------------------------------------------------------------ ISS live tracker
  const ISS_KEY = "solarrt.iss";
  const iss = { on: false, data: null, fetchedAt: 0, poll: null, tick: null, layer: L.layerGroup() };
  const issIcon = L.divIcon({
    className: "iss-icon", iconSize: [34, 34], iconAnchor: [17, 17],
    html: `<svg viewBox="0 0 34 34" width="34" height="34"><g fill="#4da3ff" stroke="#fff" stroke-width="1">
      <rect x="1" y="12" width="10" height="10" rx="1"/><rect x="23" y="12" width="10" height="10" rx="1"/>
      <rect x="11" y="15.5" width="12" height="3" fill="#fff"/><circle cx="17" cy="17" r="5" fill="#ffd166"/></g></svg>`,
  });
  const issMarker = L.marker([0, 0], { icon: issIcon, title: "International Space Station", zIndexOffset: 1000 });
  const issFoot = L.circle([0, 0], { radius: 1, color: "#4da3ff", weight: 1, fillOpacity: 0.06, interactive: false });
  const issPast = L.polyline([], { color: "#4da3ff", weight: 2, opacity: 0.9, interactive: false });
  const issNext = L.polyline([], { color: "#4da3ff", weight: 2, opacity: 0.8, dashArray: "6 6", interactive: false });
  iss.layer.addLayer(issFoot).addLayer(issPast).addLayer(issNext).addLayer(issMarker);

  // Split a ground track wherever it crosses the 180° meridian so lines don't streak across the map.
  function splitTrack(points) {
    const segs = [[]];
    for (const p of points) {
      const seg = segs[segs.length - 1];
      if (seg.length && Math.abs(p[1] - seg[seg.length - 1][1]) > 180) segs.push([]);
      segs[segs.length - 1].push([p[0], p[1]]);
    }
    return segs;
  }

  // Position between server fetches, interpolated from the per-minute track.
  function issNow() {
    const d = iss.data;
    if (!d) return null;
    const t = (Date.now() - iss.fetchedAt) / 1000;
    const tr = d.track;
    for (let i = 0; i < tr.length - 1; i++) {
      if (tr[i][2] <= t && t < tr[i + 1][2]) {
        const f = (t - tr[i][2]) / (tr[i + 1][2] - tr[i][2]);
        let dl = tr[i + 1][1] - tr[i][1];
        if (dl > 180) dl -= 360; else if (dl < -180) dl += 360;
        return [tr[i][0] + (tr[i + 1][0] - tr[i][0]) * f, wrapLon(tr[i][1] + dl * f)];
      }
    }
    return [d.lat, d.lon];
  }

  async function fetchIss() {
    const c = state.current;
    const q = c ? `?lat=${c.lat.toFixed(3)}&lon=${c.lon.toFixed(3)}` : "";
    const d = await api(`/api/iss${q}`);
    iss.data = d; iss.fetchedAt = Date.now();
    issPast.setLatLngs(splitTrack(d.track.filter((p) => p[2] <= 0)));
    issNext.setLatLngs(splitTrack(d.track.filter((p) => p[2] >= 0)));
    issFoot.setRadius(d.footprint_km * 1000);
    $("issAlt").textContent = `${Math.round(d.altitude_km)} km`;
    $("issSpeed").textContent = `${d.speed_kmh.toLocaleString()} km/h`;
    $("issBadge").textContent = d.sunlit ? "☀ Sunlit" : "🌑 In Earth's shadow";
    if (d.observer) {
      $("issDist").textContent = `${d.observer.distance_km.toLocaleString()} km`;
      $("issView").textContent = d.observer.in_view
        ? "The ISS is above your horizon right now!"
        : "Not above your horizon right now";
    } else {
      $("issDist").textContent = "–"; $("issView").textContent = "Set your location to see distance";
    }
    issTick();
    return d;
  }

  function issTick() {
    const p = issNow();
    if (!p) return;
    issMarker.setLatLng(p);
    issFoot.setLatLng(p);
    $("issPos").textContent = fmtCoord(p[0], p[1]);
    if ($("issFollow").checked) map.panTo(p, { animate: true, duration: 0.8 });
  }

  function setIss(on) {
    iss.on = on;
    try { localStorage.setItem(ISS_KEY, on ? "1" : "0"); } catch { /* storage blocked */ }
    issBtn.classList.toggle("active", on);
    issBtn.setAttribute("aria-pressed", String(on));
    $("issCard").hidden = !on;
    clearInterval(iss.poll); clearInterval(iss.tick);
    if (on) {
      iss.layer.addTo(map);
      track("ISS", fetchIss()).then(() => { if (iss.data) map.panTo(issNow()); });
      iss.poll = setInterval(() => track("ISS", fetchIss()), 30_000);
      iss.tick = setInterval(issTick, 1000);
    } else {
      map.removeLayer(iss.layer);
      state.errors.forEach((e) => { if (e.startsWith("ISS")) state.errors.delete(e); });
      state.stale.delete("ISS");
      setStatus();
    }
  }

  let issBtn, cloudBtn;
  const IssControl = L.Control.extend({
    onAdd() {
      const bar = L.DomUtil.create("div", "leaflet-bar");
      issBtn = L.DomUtil.create("a", "iss-btn", bar);
      issBtn.href = "#"; issBtn.role = "button"; issBtn.textContent = "🛰 ISS";
      issBtn.title = "Track the International Space Station live";
      L.DomEvent.disableClickPropagation(bar);
      L.DomEvent.on(issBtn, "click", (e) => { L.DomEvent.preventDefault(e); setIss(!iss.on); });
      cloudBtn = L.DomUtil.create("a", "iss-btn", bar);
      cloudBtn.href = "#"; cloudBtn.role = "button"; cloudBtn.textContent = "☁ Clouds";
      cloudBtn.title = "Show live satellite cloud cover";
      L.DomEvent.on(cloudBtn, "click", (e) => { L.DomEvent.preventDefault(e); setClouds(!clouds.on); });
      return bar;
    },
  });
  new IssControl({ position: "topleft" }).addTo(map);
  $("issCenter").addEventListener("click", () => { const p = issNow(); if (p) map.flyTo(p, Math.max(map.getZoom(), 3)); });
  let issSaved = "0";
  try { issSaved = localStorage.getItem(ISS_KEY) || "0"; } catch { /* storage blocked */ }
  if (issSaved === "1") setIss(true);

  // ------------------------------------------------------------------ live clouds (EUMETSAT)
  const CLOUD_KEY = "solarrt.clouds";
  const clouds = { on: false, layer: null, timer: null, time: null };
  const savePref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } };
  const readPref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };

  async function refreshClouds() {
    const info = await api("/api/clouds");
    const params = { layers: info.layer, format: "image/png", transparent: true, version: "1.3.0" };
    if (info.time) params.time = info.time;
    if (!clouds.layer) {
      clouds.layer = L.tileLayer.wms(info.wms_url, {
        ...params, zIndex: 350, opacity: 0.85, className: "cloud-layer", attribution: "Clouds © EUMETSAT",
      });
    } else if (info.time !== clouds.time) {
      clouds.layer.setParams(params);
    }
    clouds.time = info.time;
    if (clouds.on && !map.hasLayer(clouds.layer)) clouds.layer.addTo(map);
    updateMapCaption();
    return info;
  }

  function setClouds(on) {
    clouds.on = on;
    savePref(CLOUD_KEY, on ? "1" : "0");
    cloudBtn.classList.toggle("active", on);
    cloudBtn.setAttribute("aria-pressed", String(on));
    clearInterval(clouds.timer);
    if (on) {
      track("Clouds", refreshClouds());
      clouds.timer = setInterval(() => track("Clouds", refreshClouds()), 15 * 60_000);
    } else if (clouds.layer) {
      map.removeLayer(clouds.layer);
    }
    if (!on) state.stale.delete("Clouds");
    updateMapCaption();
  }

  function updateMapCaption() {
    const parts = [];
    if (state.auroraTime) parts.push(`Aurora forecast for ${fmtTime(state.auroraTime)}`);
    if (clouds.on && clouds.time) parts.push(`clouds as of ${fmtTime(clouds.time)}`);
    $("forecastTime").textContent = parts.join(" · ");
  }
  if (readPref(CLOUD_KEY, "0") === "1") setClouds(true);

  // ------------------------------------------------------------------ local weather
  const WX_ICON = (c) => {
    if (!c || c.cloud == null) return "❔";
    if (/thunder/i.test(c.condition)) return "⛈";
    if (/snow/i.test(c.condition)) return "🌨";
    if (/rain|drizzle|shower/i.test(c.condition)) return "🌧";
    if (/fog/i.test(c.condition)) return "🌫";
    if (c.cloud < 20) return "✨";
    if (c.cloud < 50) return "⛅";
    return "☁";
  };

  function renderWeather(w) {
    const c = w.current;
    if (state.tz !== w.timezone) { state.tz = w.timezone; refreshTimes(); }
    $("wxIcon").textContent = WX_ICON(c);
    const viewing = w.dark_now && w.clear_now ? "Good viewing conditions"
      : !w.dark_now ? `${c.sky} — but it's not dark yet`
      : `${c.sky} — clouds may block the view`;
    $("wxSummary").textContent = viewing;
    const vis = c.visibility != null ? `${Math.round(c.visibility / 1000)} km visibility` : "";
    const layers = [c.cloud_low, c.cloud_mid, c.cloud_high].every((v) => v != null)
      ? ` (low ${c.cloud_low}% · mid ${c.cloud_mid}% · high ${c.cloud_high}%)` : "";
    const temp = c.temperature != null ? ` · ${Math.round(c.temperature)}°C` : "";
    $("wxDetail").textContent = `${c.condition} · ${c.cloud ?? "–"}% cloud${layers} · ${vis}${temp}`;

    const strip = $("wxStrip");
    strip.replaceChildren();
    for (const h of w.hourly) {
      const s = document.createElement("span");
      const cl = h.cloud ?? 0;
      // clear = accent green, cloudy = grey
      s.style.background = `color-mix(in srgb, var(--muted) ${cl}%, var(--accent))`;
      s.style.opacity = h.dark ? "1" : "0.45";
      if (h.dark) s.classList.add("night");
      s.title = `${fmtTime(h.time)} — ${h.cloud ?? "?"}% cloud${h.precip_prob != null ? `, ${h.precip_prob}% rain` : ""}${h.dark ? " (dark)" : ""}`;
      strip.append(s);
    }
    $("wxNext").textContent = w.next_dark_clear
      ? `🌙 Next dark & clear sky: ${fmtDayTime(w.next_dark_clear)} ${zoneLabel()}`
      : "🌙 No dark & clear spell in the next 24 hours";
  }

  // ------------------------------------------------------------------ aurora alerts
  const ALERT_KEY = "solarrt.alerts.v1";
  const ALERT_COOLDOWN_MS = 3 * 3600_000;
  const alertDefaults = { enabled: false, useProb: true, prob: 10, useNearby: true, useKp: true, kp: 5,
    wx: "dark", cloud: 30, vis: true, last: {} };
  let alertCfg = { ...alertDefaults };
  try { alertCfg = { ...alertDefaults, ...JSON.parse(readPref(ALERT_KEY, "{}")) }; } catch { /* bad JSON */ }
  const isDesktop = () => !!(window.pywebview && window.pywebview.api && window.pywebview.api.notify);

  function syncAlertForm() {
    $("alEnabled").checked = alertCfg.enabled;
    $("alUseProb").checked = alertCfg.useProb;
    $("alProb").value = alertCfg.prob; $("alProbOut").textContent = alertCfg.prob;
    $("alUseNearby").checked = alertCfg.useNearby;
    $("alUseKp").checked = alertCfg.useKp;
    $("alKp").value = String(alertCfg.kp);
    document.querySelectorAll('input[name="alWx"]').forEach((r) => { r.checked = r.value === alertCfg.wx; });
    $("alCloud").value = alertCfg.cloud; $("alCloudOut").textContent = alertCfg.cloud;
    $("alVis").checked = alertCfg.vis;
    $("alClearOpts").hidden = alertCfg.wx !== "clear";
    $("alertForm").classList.toggle("off", !alertCfg.enabled);
  }

  function readAlertForm() {
    alertCfg.enabled = $("alEnabled").checked;
    alertCfg.useProb = $("alUseProb").checked;
    alertCfg.prob = +$("alProb").value;
    alertCfg.useNearby = $("alUseNearby").checked;
    alertCfg.useKp = $("alUseKp").checked;
    alertCfg.kp = +$("alKp").value;
    alertCfg.wx = document.querySelector('input[name="alWx"]:checked')?.value || "dark";
    alertCfg.cloud = +$("alCloud").value;
    alertCfg.vis = $("alVis").checked;
    savePref(ALERT_KEY, JSON.stringify(alertCfg));
    syncAlertForm();
  }

  async function ensurePermission() {
    if (isDesktop()) { $("alPerm").textContent = "Desktop notifications"; return true; }
    const ln = nativePlugin("LocalNotifications");
    if (ln) {  // Android/iOS app: native notifications (Android 13+ asks the user once)
      let p = await ln.checkPermissions();
      if (p.display !== "granted") p = await ln.requestPermissions();
      const ok = p.display === "granted";
      $("alPerm").textContent = ok ? "Phone notifications on" : "Notifications blocked — in-app alerts only";
      return ok;
    }
    if (!("Notification" in window)) { $("alPerm").textContent = "In-app alerts only"; return false; }
    if (Notification.permission === "default") await Notification.requestPermission();
    $("alPerm").textContent = Notification.permission === "granted"
      ? "Browser notifications on" : "Notifications blocked — in-app alerts only";
    return Notification.permission === "granted";
  }

  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; g.gain.value = 0.06;
      o.connect(g).connect(ctx.destination); o.start();
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6); o.stop(ctx.currentTime + 0.6);
    } catch { /* audio not allowed */ }
  }

  function toast(title, body) {
    const t = document.createElement("div");
    t.className = "toast";
    const close = document.createElement("button");
    close.type = "button"; close.setAttribute("aria-label", "Dismiss"); close.textContent = "✕";
    close.onclick = () => t.remove();
    const h = document.createElement("strong"); h.textContent = title;
    const p = document.createElement("div"); p.textContent = body;
    t.append(close, h, p);
    $("toasts").append(t);
    setTimeout(() => t.remove(), 30_000);
  }

  async function notify(title, body) {
    toast(title, body);
    beep();
    try {
      if (isDesktop()) { await window.pywebview.api.notify(title, body); return; }
      const ln = nativePlugin("LocalNotifications");
      if (ln) {
        // Shown immediately, so no exact alarm is needed; without isExactNotification:false the
        // plugin sends Android 12+ users to the "Alarms & reminders" settings screen first.
        await ln.schedule({ notifications: [{
          id: Math.floor(Date.now() % 2147483647), title, body, isExactNotification: false,
        }] });
        return;
      }
      if ("Notification" in window && Notification.permission === "granted") {
        const n = new Notification(title, { body, icon: "/static/favicon.svg", tag: "solarrt-aurora" });
        n.onclick = () => { window.focus(); n.close(); };
      }
    } catch (e) { console.warn("notification failed", e); }
  }

  // Decide whether to alert. Returns {fire, reasons[], blocked} for the status line.
  function evaluateAlerts() {
    const loc = state.loc, wx = state.wx, kp = state.kp;
    const reasons = [];
    if (alertCfg.useProb && loc && loc.probability >= alertCfg.prob)
      reasons.push({ key: "prob", level: loc.probability, text: `${Math.round(loc.probability)}% aurora chance overhead` });
    if (alertCfg.useNearby && loc && loc.nearby.max >= Math.max(10, alertCfg.prob) && !(loc.probability >= alertCfg.prob))
      reasons.push({ key: "near", level: loc.nearby.max, text: `aurora ${loc.nearby.max}% within ${loc.nearby.distance_km} km — look toward the ${loc.lat >= 0 ? "north" : "south"}` });
    if (alertCfg.useKp && kp && kp.kp >= alertCfg.kp - 0.34)
      reasons.push({ key: "kp", level: kp.kp, text: `Kp ${kp.kp.toFixed(1)} (${kp.g_label})` });

    let blocked = null;
    if (alertCfg.wx !== "any") {
      const dark = wx ? wx.dark_now : loc ? loc.sun_elevation <= -12 : false;
      if (!dark) blocked = "it isn't dark yet";
      else if (alertCfg.wx === "clear") {
        const c = wx?.current;
        if (!c || c.cloud == null) blocked = "no weather data";
        else if (c.cloud > alertCfg.cloud) blocked = `${c.cloud}% cloud cover`;
        else if (alertCfg.vis && c.visibility != null && c.visibility < 10_000) blocked = `visibility ${Math.round(c.visibility / 1000)} km`;
      }
    }
    return { reasons, blocked };
  }

  function checkAlerts(force = false) {
    if (!alertCfg.enabled && !force) return;
    const { reasons, blocked } = evaluateAlerts();
    const now = Date.now();
    const st = $("alStatus");
    const when = fmtTime(new Date().toISOString());
    if (!reasons.length) {
      st.className = "alert-status small-text watching";
      st.textContent = `👀 Watching — nothing to report yet (checked ${when}).`;
      return;
    }
    if (blocked) {
      st.className = "alert-status small-text watching";
      st.textContent = `⏸ Activity detected (${reasons[0].text}) but held back: ${blocked}. Checked ${when}.`;
      return;
    }
    // Cooldown per reason, unless it got stronger than when we last alerted.
    const fresh = reasons.filter((r) => {
      const last = alertCfg.last[r.key];
      return !last || now - last.at > ALERT_COOLDOWN_MS || r.level > last.level + (r.key === "kp" ? 0.6 : 5);
    });
    if (fresh.length) {
      const place = state.current?.name || "your location";
      notify("🌌 Aurora alert — SolarRT", `${place}: ${fresh.map((r) => r.text).join("; ")}.`);
      fresh.forEach((r) => { alertCfg.last[r.key] = { at: now, level: r.level }; });
      savePref(ALERT_KEY, JSON.stringify(alertCfg));
    }
    st.className = "alert-status small-text fired";
    st.textContent = `🔔 Alerted ${when}: ${reasons.map((r) => r.text).join("; ")}.`;
  }

  syncAlertForm();
  if (alertCfg.enabled) ensurePermission();
  $("alEnabled").addEventListener("change", async () => {
    readAlertForm();
    if (alertCfg.enabled) { await ensurePermission(); checkAlerts(); }
    else { $("alStatus").className = "alert-status small-text"; $("alStatus").textContent = "Alerts are off."; }
  });
  $("alertForm").addEventListener("submit", (e) => e.preventDefault());
  $("alertForm").addEventListener("input", (e) => {
    if (e.target.id === "alEnabled") return;
    readAlertForm();
    if (alertCfg.enabled) checkAlerts();
  });
  $("alTest").addEventListener("click", async () => {
    await ensurePermission();
    notify("🌌 Test alert — SolarRT", "This is how aurora alerts will look. Clear skies!");
  });

  // ------------------------------------------------------------------ feedback
  let fbRating = 0;
  document.querySelectorAll(".smileys button").forEach((b) => {
    b.addEventListener("click", () => {
      fbRating = +b.dataset.rating;
      document.querySelectorAll(".smileys button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      $("fbMore").hidden = false;
      $("fbStatus").textContent = ""; $("fbStatus").className = "small-text";
      $("fbComment").placeholder = fbRating <= 2 ? "Sorry to hear that — what went wrong? (optional)"
        : fbRating === 3 ? "What would make it better? (optional)" : "What do you like most? Anything missing? (optional)";
    });
  });
  $("fbComment").addEventListener("input", () => { $("fbCount").textContent = `${$("fbComment").value.length} / 2000`; });
  $("fbForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fbRating) return;
    const btn = $("fbSend");
    btn.disabled = true;
    try {
      const health = await api("/api/health").catch(() => ({}));
      const r = await fetch(API_BASE + "/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: fbRating, comment: $("fbComment").value, contact: $("fbContact").value,
          edition: edition(), version: health.version || "" }),
      });
      if (!r.ok) {
        const detail = (await r.json().catch(() => ({}))).detail;
        throw new Error(typeof detail === "string" ? detail : "Please check your feedback and try again.");
      }
      $("fbStatus").className = "small-text ok";
      $("fbStatus").textContent = "Thank you! Your feedback was sent. 💚";
      $("fbComment").value = ""; $("fbContact").value = ""; $("fbCount").textContent = "0 / 2000";
      $("fbMore").hidden = true; fbRating = 0;
      document.querySelectorAll(".smileys button").forEach((x) => x.setAttribute("aria-checked", "false"));
    } catch (err) {
      $("fbStatus").className = "small-text err";
      $("fbStatus").textContent = typeof err.message === "string" ? err.message : "Couldn't send feedback.";
    } finally { btn.disabled = false; }
  });

  // ------------------------------------------------------------------ clock: location's local time / UTC
  function tickClock() {
    const now = new Date().toISOString();
    const localZone = state.tz || browserZone;
    const main = timeMode === "utc" ? "UTC" : localZone;
    const other = timeMode === "utc" ? localZone : "UTC";
    $("clockMain").textContent = `${fmtTime(now, main)} ${zoneLabel(main)}`;
    $("clockOther").textContent = main === other ? "" : `${fmtTime(now, other)} ${zoneLabel(other)}`;
    $("clockBtn").title = timeMode === "utc"
      ? "Times are shown in UTC. Click to show your location's local time."
      : `Times are shown in local time for ${state.current?.name || "your location"} (${localZone}). Click to show UTC.`;
    if (state.current) {
      $("locTime").textContent = `🕐 Local time ${fmtTime(now, localZone)} ${zoneLabel(localZone)}`
        + (localZone !== "UTC" ? ` · ${fmtTime(now, "UTC")} UTC` : "");
    }
  }

  // Re-render every visible time after the time zone or the Local/UTC choice changes.
  function refreshTimes() {
    tickClock();
    setStatus();
    updateMapCaption();
    if (state.wx) renderWeather(state.wx);
    track("Kp", loadKp());
  }

  $("clockBtn").addEventListener("click", () => {
    timeMode = timeMode === "utc" ? "local" : "utc";
    try { localStorage.setItem(TIME_KEY, timeMode); } catch { /* storage blocked */ }
    refreshTimes();
  });
  tickClock();
  setInterval(tickClock, 10_000);

  // ------------------------------------------------------------------ FAQ link & privacy link
  $("faqLink").addEventListener("click", (e) => {
    e.preventDefault();
    const faq = $("faq");
    faq.scrollIntoView({ block: "start" });
    faq.classList.remove("flash"); void faq.offsetWidth; faq.classList.add("flash");
    faq.querySelector("summary")?.focus({ preventScroll: true });
  });
  // In the phone app the page is local, so the privacy policy lives on the SolarRT server.
  if (API_BASE) $("privacyLink").href = `${API_BASE}/static/privacy.html`;

  // ------------------------------------------------------------------ about
  $("aboutBtn").addEventListener("click", () => $("about").showModal());
  api("/api/health").then((h) => {
    $("versionLine").textContent = `${h.app} ${h.version}`;
    $("creditVersion").textContent = h.version;
  }).catch(() => {});

  // ------------------------------------------------------------------ start-up & refresh
  async function init() {
    const kp = track("Kp", loadKp());
    const aurora = track("Aurora", Promise.all([loadAurora(), loadRegions()]));

    const home = loadHome();
    if (home) {
      await aurora;
      await showLocation({ ...home, source: home.source === "ip" ? "ip" : "saved" }, true);
    } else {
      showNoLocation();
      await window.solarEntranceFinished;
      openWelcome(); // first visit: ask the user how to find their location
    }
    await kp;
  }

  function showNoLocation() {
    $("locName").textContent = "No location set yet";
    $("locCoords").textContent = "Press “Locate me” or search for a place.";
    $("wxSummary").textContent = "Weather appears once your location is set.";
  }

  // ------------------------------------------------------------------ first-run welcome
  function openWelcome() {
    const dlg = $("welcome");
    const msg = $("wlMsg");
    const buttons = dlg.querySelectorAll("button");
    const busy = (on, text) => {
      buttons.forEach((b) => { b.disabled = on; });
      msg.className = "wl-msg"; msg.textContent = text || "";
    };
    $("wlGps").onclick = async () => {
      busy(true, "Waiting for your device's location… (allow it if your browser asks)");
      try {
        await useCurrentLocation();
        dlg.close("done");
      } catch (err) {
        busy(false);
        msg.className = "wl-msg err";
        msg.textContent = `${gpsErrorText(err)} Try the approximate location or search for your town instead.`;
      }
    };
    $("wlIp").onclick = async () => {
      busy(true, "Estimating your location from your internet connection…");
      const loc = await locateByIp();
      if (loc) { await showLocation(loc, true); dlg.close("done"); return; }
      busy(false);
      msg.className = "wl-msg err";
      msg.textContent = "Couldn't estimate your location. Please search for your town instead.";
    };
    $("wlSearch").onclick = () => { dlg.close("search"); input.focus(); };
    dlg.addEventListener("close", () => {
      if (dlg.returnValue !== "done" && !state.current) input.focus();
    }, { once: true });
    dlg.showModal();
    $("wlGps").focus();
  }

  init();
  setInterval(() => track("Kp", loadKp()), KP_REFRESH_MS);
  setInterval(async () => {
    await track("Aurora", Promise.all([loadAurora(), loadRegions()]));
    if (state.current) await track("Location", refreshLocationStats());
  }, AURORA_REFRESH_MS);
  let resizeTimer;
  window.addEventListener("resize", () => {
    map.invalidateSize();
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (lastSeries) drawKpChart(lastSeries); }, 150);
  });
})();
