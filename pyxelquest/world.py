"""Procedural world generator for PyxelQuest.

Every seed produces a deterministic, fully connected 12-room dungeon across
three zones: Village, Dungeon, Dragon's Lair.
"""
from __future__ import annotations

import random
import uuid
from typing import Optional

from .exceptions import WorldGenerationError
from .models import Item, ItemType, Monster, Room


# ── Zone definitions ─────────────────────────────────────────────────────────

_ZONE_ROOMS = {
    "village": [
        ("village_square",   "Village Square",        "A cobblestone plaza at the heart of the village.", "廣場上瀰漫著麵包香，村民們正在議論龍的傳說。"),
        ("blacksmith",       "Blacksmith's Forge",    "The ring of hammer on anvil fills the air.", "鐵鎚敲擊聲震耳欲聾，火花四濺。"),
        ("tavern",           "The Rusty Flagon",      "A warm tavern with flickering candles and ale.", "這裡的麥酒味道還不錯，但牆上掛著些奇怪的頭骨。"),
        ("market",           "Merchant's Market",     "Colourful stalls line this busy street.", "商人們用奇怪的口音叫賣，有些東西你最好別問從哪來的。"),
    ],
    "dungeon": [
        ("dungeon_entrance", "Dungeon Entrance",      "Cracked stone steps lead down into darkness.", "台階上刻著警告文字，但已被人刻意磨去。"),
        ("guard_room",       "Guard Room",            "Rusty weapons hang on mossy walls.", "這些武器的主人，恐怕早已不在人世。"),
        ("torture_chamber",  "Forgotten Chamber",     "Strange arcane symbols cover every surface.", "符文在黑暗中微微發光，散發令人不安的氣息。"),
        ("treasury_ante",    "Antechamber of Gold",   "Gold dust glitters in cracks between ancient stones.", "空氣中充滿金屬的味道，但大部分寶藏似乎早被人拿走了。"),
    ],
    "lair": [
        ("dragon_gate",      "The Dragon Gate",       "Massive iron doors engraved with serpentine dragons.", "鐵門上的龍紋栩栩如生，彷彿隨時會動。"),
        ("lava_bridge",      "Lava Bridge",           "A narrow bridge over a river of molten rock.", "腳下的熔岩發出嘶嘶聲，橋面因高溫而扭曲。"),
        ("dragon_hoard",     "Dragon's Hoard",        "Mountains of gold coins surround a massive nest.", "黃金多到令人目眩，但那股腥臭氣息提醒你主人就在附近。"),
        ("throne_of_ashes",  "Throne of Ashes",       "A throne carved from obsidian sits in eerie silence.", "王座上有焦痕，上一個坐在這裡的人顯然結局不太好。"),
    ],
}

_ZONE_ORDER = ["village", "dungeon", "lair"]

# Exits that connect rooms within a zone (room index → direction → room index)
_INTRA_ZONE_EXITS: list[tuple[int, str, int, str]] = [
    (0, "north", 1, "south"),
    (0, "east",  2, "west"),
    (1, "east",  3, "west"),
    (2, "north", 3, "south"),
]

# Exits connecting zones: last room of zone N → first room of zone N+1
_INTER_ZONE_DIRECTION = ("east", "west")   # forward / backward


# ── Monster tables ────────────────────────────────────────────────────────────

def _monster_table(zone: str, rng: random.Random) -> list[tuple[str, dict]]:
    tables = {
        "village": [
            ("Stray Goblin",    dict(hp_range=(8, 14),  atk_range=(3, 5),  def_range=(1, 2),  xp=12, gold_range=(2, 8))),
            ("Plague Rat",      dict(hp_range=(5, 9),   atk_range=(2, 4),  def_range=(0, 1),  xp=8,  gold_range=(1, 4))),
            ("Angry Villager",  dict(hp_range=(10, 16), atk_range=(4, 6),  def_range=(2, 3),  xp=15, gold_range=(3, 10))),
        ],
        "dungeon": [
            ("Skeleton Warrior",dict(hp_range=(18, 26), atk_range=(7, 10), def_range=(3, 5),  xp=30, gold_range=(8, 20))),
            ("Cave Troll",      dict(hp_range=(28, 40), atk_range=(9, 14), def_range=(5, 8),  xp=45, gold_range=(12, 30))),
            ("Dark Sorcerer",   dict(hp_range=(15, 22), atk_range=(12,17), def_range=(2, 4),  xp=55, gold_range=(15, 35))),
        ],
        "lair": [
            ("Dragon Whelp",    dict(hp_range=(35, 50), atk_range=(15,20), def_range=(8, 12), xp=80, gold_range=(25, 60))),
            ("Lava Elemental",  dict(hp_range=(45, 65), atk_range=(18,25), def_range=(10,15), xp=100,gold_range=(30, 70))),
            ("Ancient Dragon",  dict(hp_range=(80,120), atk_range=(25,35), def_range=(15,22), xp=200,gold_range=(80,200), abilities=["fire_breath","tail_swipe"])),
        ],
    }
    return tables[zone]


def _make_monster(name: str, params: dict, zone: str, rng: random.Random) -> Monster:
    hp = rng.randint(*params["hp_range"])
    abilities = params.get("abilities", [])
    return Monster(
        id=f"mon_{uuid.uuid4().hex[:8]}",
        name=name,
        hp=hp,
        max_hp=hp,
        attack=rng.randint(*params["atk_range"]),
        defense=rng.randint(*params["def_range"]),
        xp_reward=params["xp"],
        gold_reward=rng.randint(*params["gold_range"]),
        abilities=abilities,
    )


# ── Item tables ───────────────────────────────────────────────────────────────

def _item_table(zone: str) -> list[tuple[str, ItemType, tuple[int, int], str, tuple[int, int]]]:
    """Returns list of (name, type, power_range, description, value_range)."""
    tables = {
        "village": [
            ("Health Potion",   ItemType.POTION,  (15, 25), "Restores a modest amount of HP.",       (10, 20)),
            ("Rusty Dagger",    ItemType.WEAPON,  (2, 4),   "Better than bare hands, barely.",       (5, 12)),
            ("Leather Vest",    ItemType.ARMOR,   (2, 3),   "Smells like a farm. Offers some protection.", (8, 15)),
            ("Traveller's Key", ItemType.KEY,     (0, 0),   "Opens the dungeon entrance gate.",       (0, 0)),
        ],
        "dungeon": [
            ("Greater Potion",  ItemType.POTION,  (35, 50), "A glowing red elixir. Heals significantly.", (30, 50)),
            ("Iron Sword",      ItemType.WEAPON,  (7, 10),  "A well-balanced blade, slightly enchanted.",  (40, 65)),
            ("Chain Mail",      ItemType.ARMOR,   (6, 9),   "Heavy but protective metal links.",      (45, 70)),
            ("Treasure Chest",  ItemType.TREASURE,(0, 0),   "A locked chest full of ancient gold.",   (60, 100)),
        ],
        "lair": [
            ("Dragon's Blood",  ItemType.POTION,  (70, 100),"Scalding hot. Restores massive HP.",     (80, 120)),
            ("Flame Sword",     ItemType.WEAPON,  (18, 25), "Burns with eternal dragon-fire.",        (150, 200)),
            ("Dragon Scale",    ItemType.ARMOR,   (15, 20), "Near-impenetrable scale from a drake.",  (130, 180)),
            ("Legendary Gem",   ItemType.TREASURE,(0, 0),   "Worth a kingdom's ransom.",              (300, 500)),
        ],
    }
    return tables[zone]


def _make_item(name: str, itype: ItemType, power_range: tuple, desc: str, val_range: tuple, rng: random.Random) -> Item:
    return Item(
        id=f"itm_{uuid.uuid4().hex[:8]}",
        name=name,
        type=itype,
        power=rng.randint(*power_range) if power_range[0] != power_range[1] else power_range[0],
        description=desc,
        value=rng.randint(*val_range) if val_range[0] != val_range[1] else val_range[0],
    )


# ── WorldGenerator ────────────────────────────────────────────────────────────

class WorldGenerator:
    """Generates a deterministic game world from a seed."""

    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)

    def generate(self) -> tuple[dict[str, Room], dict[str, Monster], dict[str, Item], str]:
        """Return (rooms, monsters, items, start_room_id)."""
        rooms: dict[str, Room] = {}
        monsters: dict[str, Monster] = {}
        items: dict[str, Item] = {}

        zone_room_ids: dict[str, list[str]] = {}

        # Build rooms zone by zone
        for zone in _ZONE_ORDER:
            room_defs = _ZONE_ROOMS[zone]
            zone_ids: list[str] = []

            for room_id_key, name, description, flavor in room_defs:
                room = Room(
                    id=room_id_key,
                    name=name,
                    description=description,
                    flavor=flavor,
                    exits={},
                    zone=zone,
                )
                rooms[room_id_key] = room
                zone_ids.append(room_id_key)

            zone_room_ids[zone] = zone_ids

        # Connect rooms within each zone
        for zone in _ZONE_ORDER:
            ids = zone_room_ids[zone]
            for src_idx, fwd_dir, dst_idx, bck_dir in _INTRA_ZONE_EXITS:
                src_id = ids[src_idx]
                dst_id = ids[dst_idx]
                rooms[src_id].exits[fwd_dir] = dst_id
                rooms[dst_id].exits[bck_dir] = src_id

        # Connect zones: last room of zone[n] → first room of zone[n+1]
        fwd_dir, bck_dir = _INTER_ZONE_DIRECTION
        for i in range(len(_ZONE_ORDER) - 1):
            zone_a = _ZONE_ORDER[i]
            zone_b = _ZONE_ORDER[i + 1]
            last_id  = zone_room_ids[zone_a][-1]   # room index 3
            first_id = zone_room_ids[zone_b][0]     # room index 0
            rooms[last_id].exits[fwd_dir]  = first_id
            rooms[first_id].exits[bck_dir] = last_id

        # Populate monsters and items
        for zone in _ZONE_ORDER:
            mon_table = _monster_table(zone, self._rng)
            itm_table = _item_table(zone)
            ids = zone_room_ids[zone]

            for i, room_id in enumerate(ids):
                room = rooms[room_id]

                # First room of each zone has no monster (safe room)
                if i > 0:
                    name, params = self._rng.choice(mon_table)
                    monster = _make_monster(name, params, zone, self._rng)
                    monsters[monster.id] = monster
                    room.monster_ids.append(monster.id)

                # Each room has 1–2 items
                n_items = self._rng.choice([1, 1, 2])
                chosen = self._rng.sample(itm_table, min(n_items, len(itm_table)))
                for name, itype, prange, desc, vrange in chosen:
                    item = _make_item(name, itype, prange, desc, vrange, self._rng)
                    items[item.id] = item
                    room.item_ids.append(item.id)

        self._verify_connectivity(rooms, zone_room_ids["village"][0])

        start_room_id = zone_room_ids["village"][0]
        return rooms, monsters, items, start_room_id

    def _verify_connectivity(self, rooms: dict[str, Room], start_id: str) -> None:
        """BFS to ensure all rooms are reachable from start."""
        visited = set()
        queue = [start_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbour_id in rooms[current].exits.values():
                if neighbour_id not in visited:
                    queue.append(neighbour_id)

        unreachable = set(rooms.keys()) - visited
        if unreachable:
            raise WorldGenerationError(
                f"World connectivity check failed. Unreachable rooms: {unreachable}"
            )
