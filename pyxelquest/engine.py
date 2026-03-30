"""Core game engine — pure logic, no I/O."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, replace
from typing import Optional

from .db import Database
from .exceptions import (
    CombatError,
    GameNotFoundError,
    InvalidMoveError,
    InventoryFullError,
    ItemNotFoundError,
)
from .models import (
    CombatLog,
    CombatResult,
    EventType,
    GameEvent,
    Hero,
    Item,
    ItemType,
    Monster,
    MoveResult,
    Room,
)
from .world import WorldGenerator


# XP required to reach each level (index = level, so level 1 → 2 needs xp_table[1])
_XP_TABLE = [0, 0, 50, 120, 250, 450, 700, 1000, 1400, 1900, 2500]


def _xp_to_next(level: int) -> int:
    if level >= len(_XP_TABLE) - 1:
        return 9999  # max level cap
    return _XP_TABLE[level + 1]


def _make_hero(name: str, start_room: str) -> Hero:
    return Hero(
        id="player",
        name=name,
        hp=30,
        max_hp=30,
        mp=10,
        max_mp=10,
        level=1,
        xp=0,
        xp_to_next=_XP_TABLE[2],
        gold=15,
        attack=6,
        defense=2,
        position=start_room,
        inventory=[],
    )


class GameEngine:
    """Orchestrates game state; all mutations are persisted via the Database."""

    def __init__(self, db: Database):
        self.db = db
        self._rng = random.Random()

    # ── Setup ────────────────────────────────────────────────────────────────

    def start_new_game(self, hero_name: str, seed: Optional[int] = None) -> tuple[Hero, dict[str, Room]]:
        if seed is None:
            seed = self._rng.randint(1, 999_999)

        generator = WorldGenerator(seed)
        rooms, monsters, items, start_room_id = generator.generate()

        self.db.save_rooms(rooms)
        self.db.save_monsters(monsters)
        self.db.save_items(items)
        self.db.set_meta("world_seed", str(seed))

        hero = _make_hero(hero_name, start_room_id)
        self.db.save_hero(hero)

        start_room = rooms[start_room_id]
        start_room.visited = True
        self.db.save_room(start_room)

        self.db.record_event(
            GameEvent.make(EventType.GAME_START, hero.name, start_room.name, 0,
                           f"⚔️  {hero.name} begins their adventure in {start_room.name}!")
        )
        return hero, rooms

    def load_game(self) -> tuple[Hero, Room]:
        hero = self.db.load_hero()
        if hero is None:
            raise GameNotFoundError("No saved game found. Run 'new-game' first.")
        room = self.db.load_room(hero.position)
        if room is None:
            raise GameNotFoundError(f"Room '{hero.position}' not found in database.")
        return hero, room

    # ── Movement ─────────────────────────────────────────────────────────────

    def move(self, hero: Hero, direction: str) -> MoveResult:
        current_room = self.db.load_room(hero.position)
        if current_room is None:
            return MoveResult(False, None, "Current room not found.")

        direction = direction.lower()
        if direction not in current_room.exits:
            available = ", ".join(current_room.exits.keys()) or "none"
            raise InvalidMoveError(
                f"Can't go {direction} from here. Available exits: {available}"
            )

        new_room_id = current_room.exits[direction]
        new_room = self.db.load_room(new_room_id)
        if new_room is None:
            return MoveResult(False, None, "That passage leads nowhere (broken world).")

        hero.position = new_room_id
        if not new_room.visited:
            new_room.visited = True
            self.db.save_room(new_room)

        self.db.save_hero(hero)
        self.db.record_event(
            GameEvent.make(EventType.MOVE, hero.name, new_room.name, 0,
                           f"🚶 {hero.name} moves {direction} → {new_room.name}")
        )
        return MoveResult(True, new_room, f"You move {direction} into {new_room.name}.")

    # ── Combat ───────────────────────────────────────────────────────────────

    def combat_round(self, attacker_name: str, attacker_atk: int,
                     defender_name: str, defender_def: int,
                     defender_hp: int) -> CombatResult:
        """Single combat round. Returns result (does not persist)."""
        miss_chance = max(5, 15 - attacker_atk + defender_def)
        is_miss = self._rng.randint(1, 100) <= miss_chance

        if is_miss:
            return CombatResult(
                attacker=attacker_name, defender=defender_name,
                damage=0, is_critical=False, is_miss=True,
                defender_hp_after=defender_hp,
                message=f"{attacker_name} swings and misses!"
            )

        crit_chance = 10
        is_critical = self._rng.randint(1, 100) <= crit_chance
        base_dmg = max(1, attacker_atk - defender_def // 2)
        variance = max(1, base_dmg // 3)
        damage = self._rng.randint(max(1, base_dmg - variance), base_dmg + variance)
        if is_critical:
            damage = int(damage * 1.8)

        new_hp = max(0, defender_hp - damage)
        crit_txt = " CRITICAL HIT!" if is_critical else ""
        return CombatResult(
            attacker=attacker_name, defender=defender_name,
            damage=damage, is_critical=is_critical, is_miss=False,
            defender_hp_after=new_hp,
            message=f"{attacker_name} hits {defender_name} for {damage} damage!{crit_txt}"
        )

    def full_combat(self, hero: Hero, monster: Monster) -> CombatLog:
        """Run combat to completion. Updates hero and monster in DB."""
        if not monster.is_alive():
            raise CombatError(f"{monster.name} is already defeated.")

        rounds: list[CombatResult] = []
        hero_hp = hero.hp
        mon_hp = monster.hp
        max_rounds = 30  # safety cap

        for _ in range(max_rounds):
            # Hero attacks monster
            r = self.combat_round(hero.name, hero.attack, monster.name, monster.defense, mon_hp)
            mon_hp = r.defender_hp_after
            rounds.append(r)
            self.db.record_event(
                GameEvent.make(
                    EventType.COMBAT_HIT if not r.is_miss else EventType.COMBAT_MISS,
                    hero.name, monster.name, r.damage, r.message
                )
            )
            if mon_hp <= 0:
                break

            # Monster attacks hero
            ability = self._rng.choice(monster.abilities) if monster.abilities else None
            atk = monster.attack
            if ability == "fire_breath":
                atk = int(atk * 1.5)
            r = self.combat_round(monster.name, atk, hero.name, hero.defense, hero_hp)
            hero_hp = r.defender_hp_after
            rounds.append(r)
            self.db.record_event(
                GameEvent.make(
                    EventType.COMBAT_HIT if not r.is_miss else EventType.COMBAT_MISS,
                    monster.name, hero.name, r.damage, r.message
                )
            )
            if hero_hp <= 0:
                break

        hero_survived = hero_hp > 0

        if hero_survived:
            hero.hp = hero_hp
            hero.xp += monster.xp_reward
            hero.gold += monster.gold_reward
            # Remove monster from its room
            room = self.db.load_room(hero.position)
            if room and monster.id in room.monster_ids:
                room.monster_ids.remove(monster.id)
                self.db.save_room(room)
            hero, leveled_up = self.level_up_check(hero)
            self.db.save_hero(hero)
            summary = (f"Victory! {hero.name} defeats {monster.name}, "
                       f"gains {monster.xp_reward} XP and {monster.gold_reward} gold.")
            self.db.record_event(
                GameEvent.make(EventType.COMBAT_WIN, hero.name, monster.name,
                               monster.gold_reward, summary)
            )
        else:
            hero.hp = 0
            self.db.save_hero(hero)
            summary = f"{hero.name} was slain by {monster.name}. Game over."
            self.db.record_event(
                GameEvent.make(EventType.COMBAT_LOSE, monster.name, hero.name, 0, summary)
            )

        return CombatLog(
            hero_name=hero.name,
            monster_name=monster.name,
            rounds=rounds,
            hero_survived=hero_survived,
            xp_gained=monster.xp_reward if hero_survived else 0,
            gold_gained=monster.gold_reward if hero_survived else 0,
            summary=summary,
        )

    # ── Items ────────────────────────────────────────────────────────────────

    def pickup_item(self, hero: Hero, item: Item) -> Hero:
        if len(hero.inventory) >= Hero.MAX_INVENTORY:
            raise InventoryFullError(
                f"Inventory full ({Hero.MAX_INVENTORY} items max). Drop something first."
            )

        hero.inventory.append(item)
        room = self.db.load_room(hero.position)
        if room and item.id in room.item_ids:
            room.item_ids.remove(item.id)
            self.db.save_room(room)

        self.db.save_hero(hero)
        self.db.record_event(
            GameEvent.make(EventType.ITEM_PICKUP, hero.name, item.name, item.value,
                           f"📦 {hero.name} picks up {item.name}.")
        )
        return hero

    def use_item(self, hero: Hero, item_id: str) -> tuple[Hero, str]:
        item = next((i for i in hero.inventory if i.id == item_id), None)
        if item is None:
            raise ItemNotFoundError(f"Item '{item_id}' not found in inventory.")

        msg = ""
        if item.type == ItemType.POTION:
            healed = min(item.power, hero.max_hp - hero.hp)
            hero.hp = min(hero.hp + item.power, hero.max_hp)
            msg = f"🧪 {hero.name} drinks {item.name}, restoring {healed} HP. (HP: {hero.hp}/{hero.max_hp})"

        elif item.type == ItemType.WEAPON:
            hero.attack += item.power
            msg = f"⚔️  {hero.name} equips {item.name}. Attack +{item.power}! (ATK: {hero.attack})"

        elif item.type == ItemType.ARMOR:
            hero.defense += item.power
            msg = f"🛡️  {hero.name} equips {item.name}. Defense +{item.power}! (DEF: {hero.defense})"

        elif item.type == ItemType.TREASURE:
            hero.gold += item.value
            msg = f"💰 {hero.name} opens {item.name} and finds {item.value} gold!"

        elif item.type == ItemType.KEY:
            msg = f"🗝️  {hero.name} uses {item.name}. The way forward is open!"

        else:
            msg = f"{hero.name} examines {item.name} but doesn't know how to use it."

        # Remove from inventory after use
        hero.inventory = [i for i in hero.inventory if i.id != item_id]
        self.db.save_hero(hero)
        self.db.record_event(
            GameEvent.make(EventType.ITEM_USE, hero.name, item.name, item.power, msg)
        )
        return hero, msg

    # ── Progression ──────────────────────────────────────────────────────────

    def level_up_check(self, hero: Hero) -> tuple[Hero, bool]:
        if hero.xp < hero.xp_to_next:
            return hero, False

        hero.level += 1
        hero.max_hp += 8
        hero.hp = hero.max_hp        # full heal on level-up
        hero.max_mp += 3
        hero.mp = hero.max_mp
        hero.attack += 2
        hero.defense += 1
        hero.xp_to_next = _xp_to_next(hero.level)

        self.db.record_event(
            GameEvent.make(
                EventType.LEVEL_UP, hero.name, f"Level {hero.level}", hero.level,
                f"✨ {hero.name} reaches Level {hero.level}! "
                f"HP+8, ATK+2, DEF+1. HP fully restored!"
            )
        )
        return hero, True

    # ── World snapshot (for API) ──────────────────────────────────────────────

    def get_world_snapshot(self) -> dict:
        hero = self.db.load_hero()
        if hero is None:
            return {"error": "No active game"}

        rooms_raw = self.db.conn.execute("SELECT data FROM rooms").fetchall()
        rooms = []
        for row in rooms_raw:
            import json
            d = json.loads(row["data"])
            rooms.append({
                "id": d["id"],
                "name": d["name"],
                "zone": d.get("zone", "?"),
                "visited": d.get("visited", False),
                "exits": d.get("exits", {}),
                "monster_count": len(d.get("monster_ids", [])),
                "item_count": len(d.get("item_ids", [])),
            })

        events = [e.to_dict() for e in self.db.get_recent_events(20)]
        stats = self.db.get_stats()

        return {
            "hero": hero.to_dict(),
            "rooms": rooms,
            "events": events,
            "stats": stats,
        }
