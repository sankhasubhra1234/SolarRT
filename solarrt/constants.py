"""SolarRT shared constants - single source of truth.

Defines values that appear in multiple files (regions.py, weather.py, api.py,
app.js, index.html) and must remain consistent. Bump via P1-11 and update
all referencing files in one change.
"""

# Aurora colour scale stops (value 0..100 -> rgba). Must match app.js STOPS.
STOPS = [
    [5, [40, 200, 110, 0.30]],    # 5% -> soft green edge
    [25, [43, 217, 138, 0.75]],   # 25% -> lime
    [50, [232, 226, 58, 0.85]],   # 50% -> yellow
    [70, [255, 138, 43, 0.90]],   # 70% -> orange
    [90, [255, 51, 85, 0.95]],    # 90% -> red
]

# Aurora probability thresholds (match app.js kpColor function)
KP_THRESHOLDS = [
    (8, "#d03cff"),     # storm
    (7, "#ff3355"),     # high
    (6, "#ff6a2b"),     # moderate
    (4.67, "#ffa020"),  # minor
    (4, "#e8e23a"),     # quiet
    (0, "#2bd98a"),     # quiet default
]

# Geographic constants
NEARBY_RADIUS_KM = 800  # aurora high in the sky can be seen low on the horizon from this far
EARTH_MEAN_RADIUS = 6371.0  # km

# TTL defaults (override via SOLARRT_* env vars if needed)
TTL_DEFAULTS = {
    "kp_1m": 60,        # Kp 1-minute estimate
    "kp_3h": 600,       # Kp 3-hour index
    "ovation": 300,     # OVATION aurora grid
    "weather": 600,     # Open-Meteo weather
    "clouds": 900,      # EUMETSAT cloud map
    "geocode": 24 * 3600,  # Nominatim place search
    "iss_tle": 6 * 3600,  # ISS TLE freshness
}

# UI strings
APP_NAME = "SolarRT"
APP_VERSION = "2.0.0"

# SGP4 tracking parameters (must match iss.py TRACK_PAST/FUTURE_MIN)
TRACK_PAST_MIN = 46   # minutes of past track to display
TRACK_FUTURE_MIN = 46 # minutes of future track to display (one full orbit)
TRACK_STEP_S = 60     # seconds between track points

# Cache TTL names (match config.py SOLARRT_* env var names)
TTL_ISS_SNAPSHOT = "SOLARRT_TTL_ISS_SNAPSHOT"  # seconds, default 10
TTL_MAX_STALE_NOAA = "SOLARRT_MAX_STALE_NOAA"    # seconds, default 6h
TTL_MAX_STALE_WEATHER = "SOLARRT_MAX_STALE_WEATHER"  # seconds, default 1h