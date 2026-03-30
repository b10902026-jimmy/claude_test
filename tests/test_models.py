"""Unit tests for pyxelquest/models.py."""
import time

import pytest

from pyxelquest.models import (
    CombatResult,
    EventType,
    GameEvent,
    Hero,
    Item,
    ItemType,
    Monster,
    Room,
)


class TestItem:
    def test_to_dict_roundtrip(self, test_item):
        d = test_item.to_dict()
        restored = Item.from_dict(d)
        assert restored.id == test_item.id
        assert restored.name == test_item.name
        assert restored.type == test_item.type
        assert restored.power == test_item.power
        assert restored.value == test_item.value

    def test_item_type_enum(self):
        for itype in ItemType:
            item = Item(id="x", name="x", type=itype, power=0, description="", value=0)
            d = item.to_dict()
            assert d["type"] == itype.value
            restored = Item.from_dict(d)
            assert restored.type == itype


class TestMonster:
    def test_is_alive(self, test_monster):
        assert test_monster.is_alive()
        test_monster.hp = 0
        assert not test_monster.is_alive()

    def test_to_dict_roundtrip(self, test_monster):
        d = test_monster.to_dict()
        restored = Monster.from_dict(d)
        assert restored.id == test_monster.id
        assert restored.hp == test_monster.hp
        assert restored.abilities == test_monster.abilities

    def test_abilities_default_empty(self):
        m = Monster(id="m", name="m", hp=10, max_hp=10, attack=5, defense=2,
                    xp_reward=5, gold_reward=3)
        assert m.abilities == []


class TestRoom:
    def test_to_dict_roundtrip(self):
        room = Room(
            id="test_room",
            name="Test Room",
            description="A test room.",
            flavor="測試房間",
            exits={"north": "other_room"},
            monster_ids=["mon_1"],
            item_ids=["itm_1"],
            visited=True,
            zone="dungeon",
        )
        d = room.to_dict()
        restored = Room.from_dict(d)
        assert restored.id == room.id
        assert restored.exits == {"north": "other_room"}
        assert restored.visited is True
        assert restored.zone == "dungeon"

    def test_exits_direction_keys(self):
        room = Room(id="r", name="r", description="", flavor="", exits={})
        assert isinstance(room.exits, dict)


class TestHero:
    def test_is_alive(self, hero):
        assert hero.is_alive()

    def test_hp_pct(self, hero):
        hero.hp = 15
        hero.max_hp = 30
        assert abs(hero.hp_pct() - 0.5) < 1e-9

    def test_xp_pct(self, hero):
        hero.xp = 25
        hero.xp_to_next = 50
        assert abs(hero.xp_pct() - 0.5) < 1e-9

    def test_to_dict_roundtrip(self, hero, test_item):
        hero.inventory = [test_item]
        d = hero.to_dict()
        restored = Hero.from_dict(d)
        assert restored.name == hero.name
        assert len(restored.inventory) == 1
        assert restored.inventory[0].id == test_item.id

    def test_max_inventory_constant(self):
        assert Hero.MAX_INVENTORY == 10


class TestGameEvent:
    def test_make_sets_timestamp(self):
        before = time.time()
        evt = GameEvent.make(EventType.MOVE, "Hero", "Room", 0, "moved")
        after = time.time()
        assert before <= evt.timestamp <= after

    def test_to_dict_roundtrip(self):
        evt = GameEvent.make(EventType.LEVEL_UP, "Hero", "Level 2", 2, "levelled up!")
        d = evt.to_dict()
        restored = GameEvent.from_dict(d)
        assert restored.event_type == EventType.LEVEL_UP
        assert restored.actor == "Hero"
        assert restored.value == 2

    def test_all_event_types_serialise(self):
        for etype in EventType:
            evt = GameEvent.make(etype, "a", "b", 0, "test")
            d = evt.to_dict()
            restored = GameEvent.from_dict(d)
            assert restored.event_type == etype
