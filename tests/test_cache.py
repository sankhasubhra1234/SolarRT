import asyncio

import pytest

from solarrt.cache import TTLCache


def test_stale_is_served_within_limit_then_refused(tmp_path):
    clock = [1_000.0]
    cache = TTLCache(clock=lambda: clock[0])

    async def good():
        return "value"

    async def bad():
        raise RuntimeError("upstream down")

    async def scenario():
        value, stale, age = await cache.get("k", 10, good, max_stale=60)
        assert (value, stale, age) == ("value", False, 0.0)

        clock[0] += 11  # past the TTL, so a refresh is attempted and fails
        value, stale, age = await cache.get("k", 10, bad, max_stale=60)
        assert (value, stale) == ("value", True)
        assert age == pytest.approx(11)

        clock[0] += 50  # now 61 s old, beyond max_stale
        with pytest.raises(RuntimeError):
            await cache.get("k", 10, bad, max_stale=60)

    asyncio.run(scenario())


def test_failure_with_no_cached_value_raises():
    cache = TTLCache()

    async def bad():
        raise ValueError("no data")

    async def scenario():
        with pytest.raises(ValueError):
            await cache.get("missing", 10, bad, max_stale=60)

    asyncio.run(scenario())


def test_no_max_stale_serves_old_data_indefinitely():
    clock = [0.0]
    cache = TTLCache(clock=lambda: clock[0])

    async def good():
        return 7

    async def bad():
        raise RuntimeError("down")

    async def scenario():
        await cache.get("k", 10, good)
        clock[0] += 10 * 24 * 3600
        value, stale, age = await cache.get("k", 10, bad)
        assert value == 7 and stale is True
        assert age == pytest.approx(10 * 24 * 3600)

    asyncio.run(scenario())
