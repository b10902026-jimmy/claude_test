"""PyxelQuest — A terminal RPG engine demonstrating Claude Code's capabilities."""

__version__ = "1.0.0"
__author__ = "Claude Code"

from .db import Database
from .engine import GameEngine
from .exceptions import (
    CombatError,
    DatabaseError,
    GameNotFoundError,
    InvalidMoveError,
    InventoryFullError,
    ItemNotFoundError,
    PyxelQuestError,
    WorldGenerationError,
)
from .models import EventType, Hero, Item, ItemType, Monster, Room
from .renderer import GameRenderer
from .world import WorldGenerator

__all__ = [
    "Database",
    "GameEngine",
    "GameRenderer",
    "WorldGenerator",
    "Hero",
    "Monster",
    "Item",
    "Room",
    "ItemType",
    "EventType",
    "PyxelQuestError",
    "DatabaseError",
    "WorldGenerationError",
    "InvalidMoveError",
    "CombatError",
    "InventoryFullError",
    "ItemNotFoundError",
    "GameNotFoundError",
]
