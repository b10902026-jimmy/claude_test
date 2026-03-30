"""Unit tests for pyxelquest/engine.py."""
import pytest

from pyxelquest.engine import GameEngine, _xp_to_next
from pyxelquest.exceptions import (
    CombatError,
    InvalidMoveError,
    InventoryFullError,
    ItemNotFoundError,
)
from pyxelquest.models import EventType, Hero, Item, ItemType, Monster


class TestXpTable:
    def test_level_1_to_2_xp(self):
        assert _xp_to_next(1) == 50

    def test_xp_increases_with_level(self):
        prev = _xp_to_next(1)
        for level in range(2, 8):
            current = _xp_to_next(level)
            assert current > prev
            prev = current

    def test_max_level_cap(self):
        assert _xp_to_next(10) == 9999


class TestStartNewGame:
    def test_creates_hero(self, engine, populated_db):
        db, rooms, *_ = populated_db
        # Engine has its own fresh db — start game directly
        db2 = populated_db[0]
        eng = GameEngine(db2)
        hero, world_rooms = eng.start_new_game("Tester", seed=99)
        assert hero.name == "Tester"
        assert hero.level == 1
        assert hero.hp == hero.max_hp

    def test_creates_world_rooms(self, engine, populated_db):
        db2 = populated_db[0]
        eng = GameEngine(db2)
        hero, world_rooms = eng.start_new_game("Tester", seed=99)
        assert len(world_rooms) == 12

    def test_seed_stored_in_meta(self, populated_db):
        db2 = populated_db[0]
        eng = GameEngine(db2)
        eng.start_new_game("Tester", seed=12345)
        assert db2.get_meta("world_seed") == "12345"

    def test_start_room_is_visited(self, populated_db):
        db2 = populated_db[0]
        eng = GameEngine(db2)
        hero, _ = eng.start_new_game("Tester", seed=42)
        start_room = db2.load_room(hero.position)
        assert start_room.visited is True


class TestMovement:
    def test_valid_move(self, engine, hero, populated_db):
        db = populated_db[0]
        current_room = db.load_room(hero.position)
        if not current_room.exits:
            pytest.skip("Start room has no exits (unexpected)")
        direction = next(iter(current_room.exits))
        result = engine.move(hero, direction)
        assert result.success
        assert result.new_room is not None

    def test_invalid_move_raises(self, engine, hero):
        with pytest.raises(InvalidMoveError):
            engine.move(hero, "up")  # 'up' is never a valid direction

    def test_move_updates_hero_position(self, engine, hero, populated_db):
        db = populated_db[0]
        original_pos = hero.position
        current_room = db.load_room(hero.position)
        if not current_room.exits:
            pytest.skip("No exits")
        direction = next(iter(current_room.exits))
        engine.move(hero, direction)
        loaded_hero = db.load_hero()
        assert loaded_hero.position != original_pos

    def test_move_marks_room_visited(self, engine, hero, populated_db):
        db = populated_db[0]
        current_room = db.load_room(hero.position)
        if not current_room.exits:
            pytest.skip("No exits")
        direction = next(iter(current_room.exits))
        result = engine.move(hero, direction)
        if result.success and result.new_room:
            loaded_room = db.load_room(result.new_room.id)
            assert loaded_room.visited is True

    def test_move_records_event(self, engine, hero, populated_db):
        db = populated_db[0]
        initial_count = db.get_event_count()
        current_room = db.load_room(hero.position)
        if not current_room.exits:
            pytest.skip("No exits")
        direction = next(iter(current_room.exits))
        engine.move(hero, direction)
        assert db.get_event_count() > initial_count


class TestCombatRound:
    def test_damage_is_positive(self, engine):
        result = engine.combat_round("Hero", 10, "Slime", 2, 50)
        if not result.is_miss:
            assert result.damage > 0

    def test_hp_decreases_on_hit(self, engine):
        # Run many rounds to get at least one hit
        for _ in range(30):
            result = engine.combat_round("Hero", 20, "Slime", 0, 50)
            if not result.is_miss:
                assert result.defender_hp_after < 50
                break

    def test_critical_hit_bonus(self, engine):
        """Critical hits should deal more than base damage consistently."""
        # By inspecting code logic: critical = 1.8x damage, which should exceed non-crit max
        crits = []
        normals = []
        for _ in range(200):
            result = engine.combat_round("Hero", 15, "Slime", 0, 1000)
            if not result.is_miss:
                if result.is_critical:
                    crits.append(result.damage)
                else:
                    normals.append(result.damage)
        if crits and normals:
            assert max(crits) >= max(normals)

    def test_hp_cannot_go_below_zero(self, engine):
        result = engine.combat_round("Hero", 100, "Slime", 0, 1)
        assert result.defender_hp_after >= 0


class TestFullCombat:
    def test_combat_always_terminates(self, engine, hero, test_monster, populated_db):
        db = populated_db[0]
        # Save monster to DB so engine can find it
        db.save_monster(test_monster)
        # Put monster in hero's room
        room = db.load_room(hero.position)
        room.monster_ids.append(test_monster.id)
        db.save_room(room)
        log = engine.full_combat(hero, test_monster)
        assert log is not None
        assert len(log.rounds) > 0

    def test_hero_wins_against_weak_monster(self, engine, hero, test_monster, populated_db):
        """Hero (ATK=6) vs Slime (HP=5, DEF=0) should win."""
        db = populated_db[0]
        db.save_monster(test_monster)
        room = db.load_room(hero.position)
        room.monster_ids.append(test_monster.id)
        db.save_room(room)
        log = engine.full_combat(hero, test_monster)
        assert log.hero_survived

    def test_combat_win_grants_xp_and_gold(self, engine, hero, test_monster, populated_db):
        db = populated_db[0]
        db.save_monster(test_monster)
        room = db.load_room(hero.position)
        room.monster_ids.append(test_monster.id)
        db.save_room(room)
        initial_xp = hero.xp
        log = engine.full_combat(hero, test_monster)
        if log.hero_survived:
            assert log.xp_gained == test_monster.xp_reward
            assert log.gold_gained == test_monster.gold_reward

    def test_dead_monster_raises(self, engine, hero, test_monster, populated_db):
        test_monster.hp = 0
        with pytest.raises(CombatError):
            engine.full_combat(hero, test_monster)


class TestInventory:
    def test_pickup_item(self, engine, hero, test_item, populated_db):
        db = populated_db[0]
        db.save_item(test_item)
        room = db.load_room(hero.position)
        room.item_ids.append(test_item.id)
        db.save_room(room)
        hero = engine.pickup_item(hero, test_item)
        assert any(i.id == test_item.id for i in hero.inventory)

    def test_pickup_removes_from_room(self, engine, hero, test_item, populated_db):
        db = populated_db[0]
        db.save_item(test_item)
        room = db.load_room(hero.position)
        room.item_ids.append(test_item.id)
        db.save_room(room)
        engine.pickup_item(hero, test_item)
        updated_room = db.load_room(hero.position)
        assert test_item.id not in updated_room.item_ids

    def test_inventory_full_raises(self, engine, hero):
        hero.inventory = [
            Item(id=f"i{n}", name=f"i{n}", type=ItemType.POTION, power=1, description="", value=0)
            for n in range(Hero.MAX_INVENTORY)
        ]
        extra = Item(id="extra", name="extra", type=ItemType.POTION, power=1, description="", value=0)
        with pytest.raises(InventoryFullError):
            engine.pickup_item(hero, extra)

    def test_use_potion_restores_hp(self, engine, hero, test_item, populated_db):
        db = populated_db[0]
        hero.hp = 10
        hero.inventory = [test_item]
        db.save_hero(hero)
        updated_hero, msg = engine.use_item(hero, test_item.id)
        assert updated_hero.hp > 10

    def test_use_item_removes_from_inventory(self, engine, hero, test_item, populated_db):
        db = populated_db[0]
        hero.inventory = [test_item]
        db.save_hero(hero)
        updated_hero, _ = engine.use_item(hero, test_item.id)
        assert not any(i.id == test_item.id for i in updated_hero.inventory)

    def test_use_nonexistent_item_raises(self, engine, hero):
        with pytest.raises(ItemNotFoundError):
            engine.use_item(hero, "ghost_item_id")


class TestLevelUp:
    def test_level_up_triggers_at_threshold(self, engine, hero):
        hero.xp = hero.xp_to_next
        updated_hero, leveled = engine.level_up_check(hero)
        assert leveled is True
        assert updated_hero.level == 2

    def test_no_level_up_below_threshold(self, engine, hero):
        hero.xp = hero.xp_to_next - 1
        _, leveled = engine.level_up_check(hero)
        assert leveled is False

    def test_level_up_increases_stats(self, engine, hero):
        old_max_hp = hero.max_hp
        old_attack = hero.attack
        hero.xp = hero.xp_to_next
        updated_hero, _ = engine.level_up_check(hero)
        assert updated_hero.max_hp > old_max_hp
        assert updated_hero.attack > old_attack

    def test_level_up_restores_hp(self, engine, hero):
        hero.hp = 1
        hero.xp = hero.xp_to_next
        updated_hero, leveled = engine.level_up_check(hero)
        if leveled:
            assert updated_hero.hp == updated_hero.max_hp
