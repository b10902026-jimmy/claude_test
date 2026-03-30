"""Pure data models for PyxelQuest — no I/O, no side effects."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    POTION = "potion"
    KEY = "key"
    TREASURE = "treasure"


class EventType(Enum):
    MOVE = "move"
    COMBAT_HIT = "combat_hit"
    COMBAT_MISS = "combat_miss"
    COMBAT_WIN = "combat_win"
    COMBAT_LOSE = "combat_lose"
    ITEM_PICKUP = "item_pickup"
    ITEM_USE = "item_use"
    LEVEL_UP = "level_up"
    GAME_START = "game_start"
    GAME_OVER = "game_over"


RoomId = str
MonsterId = str
ItemId = str


@dataclass
class Item:
    id: ItemId
    name: str
    type: ItemType
    power: int          # healing amount / attack bonus / armor bonus
    description: str
    value: int          # gold value

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "power": self.power,
            "description": self.description,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            id=d["id"],
            name=d["name"],
            type=ItemType(d["type"]),
            power=d["power"],
            description=d["description"],
            value=d["value"],
        )


@dataclass
class Monster:
    id: MonsterId
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    xp_reward: int
    gold_reward: int
    abilities: list[str] = field(default_factory=list)

    def is_alive(self) -> bool:
        return self.hp > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "xp_reward": self.xp_reward,
            "gold_reward": self.gold_reward,
            "abilities": self.abilities,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Monster":
        return cls(
            id=d["id"],
            name=d["name"],
            hp=d["hp"],
            max_hp=d["max_hp"],
            attack=d["attack"],
            defense=d["defense"],
            xp_reward=d["xp_reward"],
            gold_reward=d["gold_reward"],
            abilities=d.get("abilities", []),
        )


@dataclass
class Room:
    id: RoomId
    name: str
    description: str
    flavor: str                         # Chinese flavor text
    exits: dict[str, RoomId]           # direction -> room_id
    monster_ids: list[MonsterId] = field(default_factory=list)
    item_ids: list[ItemId] = field(default_factory=list)
    visited: bool = False
    zone: str = "village"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "flavor": self.flavor,
            "exits": self.exits,
            "monster_ids": self.monster_ids,
            "item_ids": self.item_ids,
            "visited": self.visited,
            "zone": self.zone,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        return cls(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            flavor=d.get("flavor", ""),
            exits=d["exits"],
            monster_ids=d.get("monster_ids", []),
            item_ids=d.get("item_ids", []),
            visited=d.get("visited", False),
            zone=d.get("zone", "village"),
        )


@dataclass
class Hero:
    id: str
    name: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    level: int
    xp: int
    xp_to_next: int
    gold: int
    attack: int
    defense: int
    position: RoomId
    inventory: list[Item] = field(default_factory=list)

    MAX_INVENTORY = 10

    def is_alive(self) -> bool:
        return self.hp > 0

    def hp_pct(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

    def xp_pct(self) -> float:
        return self.xp / self.xp_to_next if self.xp_to_next > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "level": self.level,
            "xp": self.xp,
            "xp_to_next": self.xp_to_next,
            "gold": self.gold,
            "attack": self.attack,
            "defense": self.defense,
            "position": self.position,
            "inventory": [item.to_dict() for item in self.inventory],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Hero":
        return cls(
            id=d["id"],
            name=d["name"],
            hp=d["hp"],
            max_hp=d["max_hp"],
            mp=d["mp"],
            max_mp=d["max_mp"],
            level=d["level"],
            xp=d["xp"],
            xp_to_next=d["xp_to_next"],
            gold=d["gold"],
            attack=d["attack"],
            defense=d["defense"],
            position=d["position"],
            inventory=[Item.from_dict(i) for i in d.get("inventory", [])],
        )


@dataclass
class GameEvent:
    timestamp: float
    event_type: EventType
    actor: str
    target: str
    value: int
    message: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "target": self.target,
            "value": self.value,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameEvent":
        return cls(
            timestamp=d["timestamp"],
            event_type=EventType(d["event_type"]),
            actor=d["actor"],
            target=d["target"],
            value=d["value"],
            message=d["message"],
        )

    @classmethod
    def make(cls, event_type: EventType, actor: str, target: str, value: int, message: str) -> "GameEvent":
        return cls(
            timestamp=time.time(),
            event_type=event_type,
            actor=actor,
            target=target,
            value=value,
            message=message,
        )


@dataclass
class CombatResult:
    attacker: str
    defender: str
    damage: int
    is_critical: bool
    is_miss: bool
    defender_hp_after: int
    message: str


@dataclass
class CombatLog:
    hero_name: str
    monster_name: str
    rounds: list[CombatResult]
    hero_survived: bool
    xp_gained: int
    gold_gained: int
    summary: str


@dataclass
class MoveResult:
    success: bool
    new_room: Optional[Room]
    message: str
