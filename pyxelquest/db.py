"""SQLite persistence layer for PyxelQuest."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from .exceptions import DatabaseError
from .models import GameEvent, EventType, Hero, Item, Monster, Room


class Database:
    """Thin SQLite wrapper with schema management and domain-level helpers."""

    def __init__(self, path: str = "pyxelquest.db"):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL mode allows concurrent reads from the API server thread
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("Database is not connected. Call connect() first.")
        return self._conn

    @contextmanager
    def transaction(self) -> Generator:
        try:
            yield self.conn
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            raise DatabaseError(f"Transaction failed: {exc}") from exc

    def init_schema(self) -> None:
        """Create tables if they don't exist (idempotent)."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS heroes (
                id      TEXT PRIMARY KEY,
                data    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id      TEXT PRIMARY KEY,
                data    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monsters (
                id      TEXT PRIMARY KEY,
                data    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS items (
                id      TEXT PRIMARY KEY,
                data    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL NOT NULL,
                event_type  TEXT NOT NULL,
                actor       TEXT NOT NULL,
                target      TEXT NOT NULL,
                value       INTEGER NOT NULL,
                message     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_meta (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ── Hero ────────────────────────────────────────────────────────────────

    def save_hero(self, hero: Hero) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO heroes (id, data) VALUES (?, ?)",
                (hero.id, json.dumps(hero.to_dict())),
            )

    def load_hero(self, hero_id: str = "player") -> Optional[Hero]:
        row = self.conn.execute(
            "SELECT data FROM heroes WHERE id = ?", (hero_id,)
        ).fetchone()
        if row is None:
            return None
        return Hero.from_dict(json.loads(row["data"]))

    # ── Room ────────────────────────────────────────────────────────────────

    def save_room(self, room: Room) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO rooms (id, data) VALUES (?, ?)",
                (room.id, json.dumps(room.to_dict())),
            )

    def save_rooms(self, rooms: dict[str, Room]) -> None:
        with self.transaction():
            for room in rooms.values():
                self.conn.execute(
                    "INSERT OR REPLACE INTO rooms (id, data) VALUES (?, ?)",
                    (room.id, json.dumps(room.to_dict())),
                )

    def load_room(self, room_id: str) -> Optional[Room]:
        row = self.conn.execute(
            "SELECT data FROM rooms WHERE id = ?", (room_id,)
        ).fetchone()
        if row is None:
            return None
        return Room.from_dict(json.loads(row["data"]))

    def load_all_rooms(self) -> dict[str, Room]:
        rows = self.conn.execute("SELECT data FROM rooms").fetchall()
        return {
            r["id"]: Room.from_dict(d)
            for row in rows
            for d in [json.loads(row["data"])]
            for r in [d]  # trick: d is the dict, r aliases it for id extraction
        }

    def _load_all_rooms_impl(self) -> dict[str, Room]:
        rows = self.conn.execute("SELECT data FROM rooms").fetchall()
        result = {}
        for row in rows:
            d = json.loads(row["data"])
            room = Room.from_dict(d)
            result[room.id] = room
        return result

    # ── Monster ─────────────────────────────────────────────────────────────

    def save_monster(self, monster: Monster) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO monsters (id, data) VALUES (?, ?)",
                (monster.id, json.dumps(monster.to_dict())),
            )

    def save_monsters(self, monsters: dict[str, Monster]) -> None:
        with self.transaction():
            for monster in monsters.values():
                self.conn.execute(
                    "INSERT OR REPLACE INTO monsters (id, data) VALUES (?, ?)",
                    (monster.id, json.dumps(monster.to_dict())),
                )

    def load_monster(self, monster_id: str) -> Optional[Monster]:
        row = self.conn.execute(
            "SELECT data FROM monsters WHERE id = ?", (monster_id,)
        ).fetchone()
        if row is None:
            return None
        return Monster.from_dict(json.loads(row["data"]))

    # ── Item ────────────────────────────────────────────────────────────────

    def save_item(self, item: Item) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO items (id, data) VALUES (?, ?)",
                (item.id, json.dumps(item.to_dict())),
            )

    def save_items(self, items: dict[str, Item]) -> None:
        with self.transaction():
            for item in items.values():
                self.conn.execute(
                    "INSERT OR REPLACE INTO items (id, data) VALUES (?, ?)",
                    (item.id, json.dumps(item.to_dict())),
                )

    def load_item(self, item_id: str) -> Optional[Item]:
        row = self.conn.execute(
            "SELECT data FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return None
        return Item.from_dict(json.loads(row["data"]))

    # ── Events ──────────────────────────────────────────────────────────────

    def record_event(self, event: GameEvent) -> None:
        try:
            self.conn.execute(
                """INSERT INTO game_events
                   (timestamp, event_type, actor, target, value, message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    event.timestamp,
                    event.event_type.value,
                    event.actor,
                    event.target,
                    event.value,
                    event.message,
                ),
            )
            self.conn.commit()
        except Exception as exc:
            raise DatabaseError(f"Failed to record event: {exc}") from exc

    def get_recent_events(self, n: int = 20) -> list[GameEvent]:
        rows = self.conn.execute(
            "SELECT * FROM game_events ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        events = []
        for row in reversed(rows):
            events.append(
                GameEvent(
                    timestamp=row["timestamp"],
                    event_type=EventType(row["event_type"]),
                    actor=row["actor"],
                    target=row["target"],
                    value=row["value"],
                    message=row["message"],
                )
            )
        return events

    def get_event_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM game_events").fetchone()
        return row["cnt"]

    # ── Meta / Stats ────────────────────────────────────────────────────────

    def set_meta(self, key: str, value: str) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO game_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM game_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def get_stats(self) -> dict:
        """Return aggregate game statistics."""
        total_events = self.get_event_count()

        kills = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM game_events WHERE event_type = ?",
            (EventType.COMBAT_WIN.value,),
        ).fetchone()["cnt"]

        rooms_explored = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM rooms WHERE json_extract(data, '$.visited') = 1"
        ).fetchone()["cnt"]

        items_found = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM game_events WHERE event_type = ?",
            (EventType.ITEM_PICKUP.value,),
        ).fetchone()["cnt"]

        level_ups = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM game_events WHERE event_type = ?",
            (EventType.LEVEL_UP.value,),
        ).fetchone()["cnt"]

        total_gold = self.conn.execute(
            "SELECT COALESCE(SUM(value), 0) as total FROM game_events WHERE event_type = ?",
            (EventType.COMBAT_WIN.value,),
        ).fetchone()["total"]

        return {
            "total_events": total_events,
            "monsters_killed": kills,
            "rooms_explored": rooms_explored,
            "items_found": items_found,
            "level_ups": level_ups,
            "gold_earned": total_gold,
            "world_seed": self.get_meta("world_seed", "unknown"),
        }
