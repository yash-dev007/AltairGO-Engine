from unittest.mock import MagicMock


def test_cache_get_failure_returns_none(monkeypatch):
    from backend.services import cache_service

    client = MagicMock()
    client.get.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(cache_service, "REDIS_OK", True)
    monkeypatch.setattr(cache_service, "_r", client)

    # Redis failures should degrade to cache misses instead of bubbling exceptions.
    assert cache_service.get_cached({"city": "Jaipur", "duration": 3}) is None


def test_cache_set_failure_does_not_raise(monkeypatch):
    from backend.services import cache_service

    client = MagicMock()
    client.setex.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(cache_service, "REDIS_OK", True)
    monkeypatch.setattr(cache_service, "_r", client)

    # Redis write failures should be swallowed so request flow continues.
    assert cache_service.set_cached({"city": "Jaipur", "duration": 3}, {"ok": True}) is None
