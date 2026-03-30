"""Unit tests for pyxelquest/world.py."""
import pytest

from pyxelquest.world import WorldGenerator
from pyxelquest.models import ItemType


class TestWorldGenerator:
    def test_generates_12_rooms(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        assert len(rooms) == 12

    def test_deterministic_output(self):
        gen1 = WorldGenerator(seed=42)
        rooms1, monsters1, items1, start1 = gen1.generate()

        gen2 = WorldGenerator(seed=42)
        rooms2, monsters2, items2, start2 = gen2.generate()

        assert start1 == start2
        assert set(rooms1.keys()) == set(rooms2.keys())

    def test_different_seeds_produce_different_worlds(self):
        gen_a = WorldGenerator(seed=1)
        _, monsters_a, _, _ = gen_a.generate()

        gen_b = WorldGenerator(seed=2)
        _, monsters_b, _, _ = gen_b.generate()

        # Monster stats should differ (highly likely with different seeds)
        atks_a = sorted(m.attack for m in monsters_a.values())
        atks_b = sorted(m.attack for m in monsters_b.values())
        assert atks_a != atks_b

    def test_all_rooms_reachable(self):
        """BFS from start room must reach all 12 rooms."""
        gen = WorldGenerator(seed=42)
        rooms, _, _, start_id = gen.generate()

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

        assert visited == set(rooms.keys()), f"Unreachable: {set(rooms.keys()) - visited}"

    def test_three_zones_present(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        zones = {r.zone for r in rooms.values()}
        assert zones == {"village", "dungeon", "lair"}

    def test_each_zone_has_4_rooms(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        from collections import Counter
        counts = Counter(r.zone for r in rooms.values())
        assert counts["village"] == 4
        assert counts["dungeon"] == 4
        assert counts["lair"] == 4

    def test_rooms_have_exits(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        for room in rooms.values():
            assert len(room.exits) >= 1, f"Room {room.id} has no exits"

    def test_exit_targets_are_valid_room_ids(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        for room in rooms.values():
            for direction, target_id in room.exits.items():
                assert target_id in rooms, f"Exit {direction} from {room.id} → invalid {target_id}"

    def test_exits_are_bidirectional(self):
        """If room A has exit north→B, then B should have exit south→A."""
        opposites = {"north": "south", "south": "north", "east": "west", "west": "east"}
        gen = WorldGenerator(seed=42)
        rooms, _, _, _ = gen.generate()
        for room in rooms.values():
            for direction, target_id in room.exits.items():
                opp = opposites.get(direction)
                if opp:
                    target_room = rooms[target_id]
                    assert opp in target_room.exits, (
                        f"Exit {direction} from {room.id}→{target_id} has no reverse exit"
                    )

    def test_monsters_have_valid_stats(self):
        gen = WorldGenerator(seed=42)
        _, monsters, _, _ = gen.generate()
        for m in monsters.values():
            assert m.hp > 0
            assert m.max_hp >= m.hp
            assert m.attack > 0
            assert m.defense >= 0
            assert m.xp_reward > 0
            assert m.gold_reward >= 0

    def test_items_have_valid_types(self):
        gen = WorldGenerator(seed=42)
        _, _, items, _ = gen.generate()
        for item in items.values():
            assert isinstance(item.type, ItemType)
            assert item.power >= 0
            assert item.value >= 0

    def test_start_room_is_village(self):
        gen = WorldGenerator(seed=42)
        rooms, _, _, start_id = gen.generate()
        assert rooms[start_id].zone == "village"

    def test_first_village_room_has_no_monster(self):
        """The starting room should be safe (no monsters)."""
        gen = WorldGenerator(seed=42)
        rooms, _, _, start_id = gen.generate()
        assert len(rooms[start_id].monster_ids) == 0
