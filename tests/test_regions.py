
from solarrt.regions import REGIONS, summarize_regions


def test_regions_have_valid_structure():
    """Verify all regions have the expected fields."""
    for r in REGIONS:
        assert hasattr(r, "id")
        assert hasattr(r, "name")
        assert hasattr(r, "hemisphere")
        assert hasattr(r, "south")
        assert hasattr(r, "north")
        assert hasattr(r, "west")
        assert hasattr(r, "east")


def test_summarize_regions_returns_max():
    """verify summarize_regions produces entries with max and coverage."""
    from solarrt.noaa import parse_ovation
    from tests.conftest import load

    grid = parse_ovation(load("ovation.json"))
    summarized = summarize_regions(grid)
    assert len(summarized) == len(REGIONS)
    for entry in summarized:
        assert "max" in entry
        assert "coverage" in entry
        assert "name" in entry
        assert isinstance(entry["max"], int)
        assert isinstance(entry["coverage"], float)


def test_max_within_near_poles():
    """Test that max_within works correctly near the poles where geometry is tricky."""
    from solarrt.noaa import parse_ovation
    from tests.conftest import load

    grid = parse_ovation(load("ovation.json"))
    # Test a point near the north pole
    val, lat, lon = grid.max_within(85, 0, 1000)
    assert isinstance(val, int)
    assert isinstance(lat, float)
    assert isinstance(lon, float)


def test_max_within_across_antimeridian():
    """Test max_within crosses the antimeridian correctly."""
    from solarrt.noaa import parse_ovation
    from tests.conftest import load

    grid = parse_ovation(load("ovation.json"))
    # Test a point that would cross antimeridian
    val, _lat, lon = grid.max_within(0, 175, 1000)
    assert isinstance(val, int)
    # lon should be wrapped back into -180..180 range
    assert -180 <= lon <= 180


def test_region_cells_coverage():
    """Test that region cells generate valid lat/lon pairs."""
    for r in REGIONS:
        cells = list(r.cells())
        for lat, lon in cells:
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180