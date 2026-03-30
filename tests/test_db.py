"""Unit tests for pyxelquest/db.py."""
import pytest

from pyxelquest.exceptions import DatabaseError
from pyxelquest.models import EventType, GameEvent, Hero, Item, ItemType, Monster, Room


class TestDatabaseConnection:
    def test_init_schema_is_idempotent(self, db):
        """Calling init_schema twice should not raise."""
        db.init_schema()
        db.init_schema()

    def test_close_and_reconnect(self):
        from pyxelquest.db import Database
        db2 = Database(":memory:")
        db2.connect()
        db2.close()
        # After close, accessing conn should raise
        with pytest.raises(DatabaseError):
            _ = db2.conn


class TestHeroCRUD:
    def test_save_and_load_hero(self, db, hero):
        db.save_hero(hero)
        loaded = db.load_hero("player")
        assert loaded is not None
        assert loaded.name == hero.name
        assert loaded.level == hero.level

    def test_load_nonexistent_hero_returns_none(self, db):
        assert db.load_hero("nonexistent") is None

    def test_save_hero_updates_existing(self, db, hero):
        db.save_hero(hero)
        hero.gold = 9999
        db.save_hero(hero)
        loaded = db.load_hero("player")
        assert loaded.gold == 9999

    def test_hero_inventory_persisted(self, db, hero, test_item):
        hero.inventory = [test_item]
        db.save_hero(hero)
        loaded = db.load_hero("player")
        assert len(loaded.inventory) == 1
        assert loaded.inventory[0].id == test_item.id


class TestRoomCRUD:
    def test_save_and_load_room(self, db):
        room = Room(id="test_room", name="Test", description="desc", flavor="",
                    exits={"north": "other"}, zone="village")
        db.save_room(room)
        loaded = db.load_room("test_room")
        assert loaded is not None
        assert loaded.name == "Test"
        assert loaded.exits == {"north": "other"}

    def test_load_nonexistent_room_returns_none(self, db):
        assert db.load_room("ghost_room") is None

    def test_save_rooms_batch(self, db, world_data):
        rooms, _, _, _ = world_data
        db.save_rooms(rooms)
        for room_id in rooms:
            loaded = db.load_room(room_id)
            assert loaded is not None
            assert loaded.id == room_id


class TestItemCRUD:
    def test_save_and_load_item(self, db, test_item):
        db.save_item(test_item)
        loaded = db.load_item(test_item.id)
        assert loaded is not None
        assert loaded.name == test_item.name
        assert loaded.type == ItemType.POTION

    def test_load_nonexistent_item_returns_none(self, db):
        assert db.load_item("ghost_item") is None


class TestMonsterCRUD:
    def test_save_and_load_monster(self, db, test_monster):
        db.save_monster(test_monster)
        loaded = db.load_monster(test_monster.id)
        assert loaded is not None
        assert loaded.name == test_monster.name
        assert loaded.attack == test_monster.attack


class TestEvents:
    def test_record_and_retrieve_events(self, db):
        evt = GameEvent.make(EventType.MOVE, "Hero", "Room", 0, "moved north")
        db.record_event(evt)
        events = db.get_recent_events(10)
        assert len(events) == 1
        assert events[0].message == "moved north"

    def test_get_recent_events_ordering(self, db):
        for i in range(5):
            db.record_event(GameEvent.make(EventType.MOVE, "Hero", "Room", i, f"event {i}"))
        events = db.get_recent_events(5)
        # Should be in chronological order (oldest first)
        assert events[0].value < events[-1].value

    def test_get_recent_events_limit(self, db):
        for i in range(10):
            db.record_event(GameEvent.make(EventType.MOVE, "H", "R", i, f"e{i}"))
        events = db.get_recent_events(3)
        assert len(events) == 3

    def test_event_count(self, db):
        assert db.get_event_count() == 0
        db.record_event(GameEvent.make(EventType.MOVE, "H", "R", 0, "x"))
        assert db.get_event_count() == 1


class TestMeta:
    def test_set_and_get_meta(self, db):
        db.set_meta("world_seed", "12345")
        assert db.get_meta("world_seed") == "12345"

    def test_get_missing_meta_returns_default(self, db):
        assert db.get_meta("nonexistent", "fallback") == "fallback"

    def test_set_meta_overwrites(self, db):
        db.set_meta("key", "v1")
        db.set_meta("key", "v2")
        assert db.get_meta("key") == "v2"


class TestStats:
    def test_get_stats_returns_dict(self, populated_db):
        db, *_ = populated_db
        stats = db.get_stats()
        assert "monsters_killed" in stats
        assert "rooms_explored" in stats
        assert "items_found" in stats
        assert "world_seed" in stats

    def test_stats_initial_zeros(self, populated_db):
        db, *_ = populated_db
        stats = db.get_stats()
        assert stats["monsters_killed"] == 0
        assert stats["items_found"] == 0
