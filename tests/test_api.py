"""Unit tests for pyxelquest/api_server.py."""
import json
import time
import urllib.request
import pytest

from pyxelquest.api_server import GameAPIServer
from pyxelquest.db import Database
from pyxelquest.engine import GameEngine


@pytest.fixture(scope="module")
def live_server():
    """Start a real HTTP server for the duration of this module's tests."""
    db = Database(":memory:")
    db.connect()
    engine = GameEngine(db)
    engine.start_new_game("APITestHero", seed=77)

    server = GameAPIServer(engine, port=18765)
    server.start()
    time.sleep(0.15)  # Give the daemon thread a moment to bind

    yield server, "http://localhost:18765"

    server.stop()
    db.close()


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class TestAPIServer:
    def test_root_returns_html(self, live_server):
        _, base_url = live_server
        status, body = _get(f"{base_url}/")
        assert status == 200
        assert "<!DOCTYPE html>" in body
        assert "PIXELQUEST" in body

    def test_api_status_returns_json(self, live_server):
        _, base_url = live_server
        status, body = _get(f"{base_url}/api/status")
        assert status == 200
        data = json.loads(body)
        assert "hero" in data
        assert "turn" in data

    def test_api_status_hero_has_required_fields(self, live_server):
        _, base_url = live_server
        _, body = _get(f"{base_url}/api/status")
        data = json.loads(body)
        hero = data["hero"]
        for field in ["name", "level", "hp", "max_hp", "attack", "defense", "gold", "position"]:
            assert field in hero, f"Missing field: {field}"

    def test_api_events_returns_list(self, live_server):
        _, base_url = live_server
        status, body = _get(f"{base_url}/api/events")
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)

    def test_api_events_have_required_fields(self, live_server):
        _, base_url = live_server
        _, body = _get(f"{base_url}/api/events")
        events = json.loads(body)
        if events:
            evt = events[0]
            for field in ["event_type", "actor", "message", "timestamp"]:
                assert field in evt

    def test_api_world_returns_rooms(self, live_server):
        _, base_url = live_server
        status, body = _get(f"{base_url}/api/world")
        assert status == 200
        data = json.loads(body)
        assert "rooms" in data
        assert len(data["rooms"]) == 12

    def test_api_world_rooms_have_zone(self, live_server):
        _, base_url = live_server
        _, body = _get(f"{base_url}/api/world")
        rooms = json.loads(body)["rooms"]
        zones = {r["zone"] for r in rooms}
        assert zones == {"village", "dungeon", "lair"}

    def test_api_stats_returns_dict(self, live_server):
        _, base_url = live_server
        status, body = _get(f"{base_url}/api/stats")
        assert status == 200
        data = json.loads(body)
        assert "monsters_killed" in data
        assert "rooms_explored" in data
        assert "world_seed" in data

    def test_unknown_route_returns_404(self, live_server):
        _, base_url = live_server
        status, _ = _get(f"{base_url}/api/nonexistent")
        assert status == 404

    def test_server_start_and_stop(self):
        """Verify GameAPIServer lifecycle is clean."""
        db = Database(":memory:")
        db.connect()
        engine = GameEngine(db)
        engine.start_new_game("LifecycleHero", seed=1)
        srv = GameAPIServer(engine, port=18766)
        srv.start()
        time.sleep(0.1)
        status, _ = _get("http://localhost:18766/api/stats")
        assert status == 200
        srv.stop()
        db.close()
