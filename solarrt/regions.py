"""Aurora-viewing regions and their activity summary from the OVATION grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .noaa import AuroraGrid


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    hemisphere: str  # north | south
    south: int
    north: int
    west: int  # degrees, -180..180; west > east means the box crosses the antimeridian
    east: int

    def cells(self):
        lons = (range(self.west, self.east + 1) if self.west <= self.east
                else list(range(self.west, 181)) + list(range(-180, self.east + 1)))
        for lat in range(self.south, self.north + 1):
            for lon in lons:
                yield lat, lon


REGIONS: list[Region] = [
    Region("alaska", "Alaska", "north", 54, 71, -168, -130),
    Region("canada", "Northern Canada", "north", 55, 75, -140, -60),
    Region("usa-north", "Northern USA", "north", 41, 49, -124, -67),
    Region("greenland", "Greenland", "north", 60, 83, -73, -12),
    Region("iceland", "Iceland", "north", 63, 67, -25, -13),
    Region("uk-ireland", "UK & Ireland", "north", 50, 61, -11, 2),
    Region("scandinavia", "Scandinavia & Finland", "north", 55, 71, 4, 32),
    Region("central-europe", "Central Europe", "north", 45, 55, -5, 25),
    Region("russia", "Northern Russia & Siberia", "north", 58, 78, 32, 180),
    Region("tasmania", "Tasmania", "south", -44, -40, 144, 149),
    Region("south-australia", "Southern Australia", "south", -39, -31, 114, 154),
    Region("new-zealand", "New Zealand", "south", -47, -34, 166, 179),
    Region("patagonia", "Patagonia (Argentina & Chile)", "south", -56, -40, -76, -62),
    Region("antarctica", "Antarctica", "south", -90, -60, -180, 180),
]


def activity_level(prob: float) -> str:
    if prob >= 50:
        return "Very high"
    if prob >= 30:
        return "High"
    if prob >= 15:
        return "Moderate"
    if prob >= 5:
        return "Low"
    return "None"


def summarize_regions(grid: AuroraGrid) -> list[dict[str, Any]]:
    out = []
    for r in REGIONS:
        best, best_at, active, total = 0, None, 0, 0
        for lat, lon in r.cells():
            v = grid.at_cell(lat + 90, lon)
            total += 1
            if v >= 5:
                active += 1
            if v > best:
                best, best_at = v, (lat, lon)
        out.append({
            "id": r.id, "name": r.name, "hemisphere": r.hemisphere,
            "bounds": [[r.south, r.west], [r.north, r.east]],
            "max": best, "peak_at": best_at,
            "coverage": round(100 * active / total, 1) if total else 0.0,
            "level": activity_level(best),
        })
    out.sort(key=lambda d: (-d["max"], -d["coverage"]))
    return out
