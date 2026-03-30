"""Shared pytest fixtures for PyxelQuest tests."""
import io
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyxelquest.db import Database
from pyxelquest.engine import GameEngine
from pyxelquest.models import Hero, Item, ItemType, Monster, Room
from pyxelquest.renderer import GameRenderer
from pyxelquest.world import WorldGenerator
from rich.console import Console


@pytest.fixture
def db():
    """In-memory SQLite database with schema initialised."""
    database = Database(":memory:")
    database.connect()
    yield database
    database.close()


@pytest.fixture
def world_data():
    """Deterministic world generated from seed=42."""
    gen = WorldGenerator(seed=42)
    rooms, monsters, items, start_room_id = gen.generate()
    return rooms, monsters, items, start_room_id


@pytest.fixture
def populated_db(db, world_data):
    """Database with a full world and hero loaded."""
    rooms, monsters, items, start_room_id = world_data
    db.save_rooms(rooms)
    db.save_monsters(monsters)
    db.save_items(items)
    db.set_meta("world_seed", "42")
    yield db, rooms, monsters, items, start_room_id


@pytest.fixture
def hero(populated_db):
    """A fresh hero saved into the populated database."""
    db, rooms, monsters, items, start_room_id = populated_db
    h = Hero(
        id="player",
        name="TestHero",
        hp=30, max_hp=30,
        mp=10, max_mp=10,
        level=1, xp=0, xp_to_next=50,
        gold=15,
        attack=6, defense=2,
        position=start_room_id,
        inventory=[],
    )
    db.save_hero(h)
    return h


@pytest.fixture
def engine(populated_db):
    """GameEngine wired to the populated in-memory database."""
    db, *_ = populated_db
    return GameEngine(db)


@pytest.fixture
def test_item():
    """A sample potion item."""
    return Item(
        id="itm_test001",
        name="Test Potion",
        type=ItemType.POTION,
        power=20,
        description="A test potion.",
        value=10,
    )


@pytest.fixture
def test_monster():
    """A weak monster for combat testing."""
    return Monster(
        id="mon_test001",
        name="Test Slime",
        hp=5,
        max_hp=5,
        attack=2,
        defense=0,
        xp_reward=10,
        gold_reward=5,
        abilities=[],
    )


@pytest.fixture
def capturing_console():
    """A Rich Console that writes to a StringIO buffer for assertion."""
    buf = io.StringIO()
    return Console(file=buf, width=120), buf
