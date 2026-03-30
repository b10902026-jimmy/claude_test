"""CLI command implementations for PyxelQuest."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from .api_server import GameAPIServer
from .db import Database
from .engine import GameEngine
from .exceptions import GameNotFoundError, InvalidMoveError, InventoryFullError, PyxelQuestError
from .models import EventType
from .renderer import GameRenderer


def _get_db(db_path: str = "pyxelquest.db") -> Database:
    db = Database(db_path)
    db.connect()
    return db


def _get_splash() -> str:
    splash_file = Path(__file__).parent.parent / "assets" / "splash.txt"
    if splash_file.exists():
        return splash_file.read_text()
    return "⚔  PIXELQUEST  ⚔"


# ── new-game ─────────────────────────────────────────────────────────────────

def cmd_new_game(args: list[str]) -> None:
    console = Console()
    seed = int(args[0]) if args else None
    hero_name = input("Enter your hero's name: ").strip() or "Hero"

    db = _get_db()
    engine = GameEngine(db)
    renderer = GameRenderer(console)

    try:
        hero, rooms = engine.start_new_game(hero_name, seed)
        actual_seed = db.get_meta("world_seed")

        renderer.render_splash(_get_splash())
        console.print(f"\n[bold green]New game created![/bold green]")
        console.print(f"  Hero:       [cyan]{hero.name}[/cyan]")
        console.print(f"  World seed: [yellow]{actual_seed}[/yellow]  (use this seed to replay the same world)")
        console.print(f"  Rooms:      [white]{len(rooms)}[/white] rooms across 3 zones")
        console.print(f"\nRun [bold]python3 game.py play[/bold] to begin your adventure!")
        console.print(f"Run [bold]python3 game.py serve[/bold] to open the browser dashboard.")
    finally:
        db.close()


# ── play ──────────────────────────────────────────────────────────────────────

def cmd_play(args: list[str]) -> None:
    """Interactive game loop."""
    console = Console()
    renderer = GameRenderer(console)
    db = _get_db()
    engine = GameEngine(db)

    try:
        hero, room = engine.load_game()
    except GameNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        db.close()
        return

    # Start API server in background
    api = GameAPIServer(engine)
    api.start()
    console.print(f"[dim]🌐 Browser dashboard: http://localhost:8765[/dim]")

    renderer.render_splash(_get_splash())

    import tty, termios  # noqa: E401

    def getch() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    direction_keys = {
        "w": "north", "a": "west", "s": "south", "d": "east",
        "\x1b[A": "north", "\x1b[B": "south", "\x1b[C": "east", "\x1b[D": "west",
    }

    while True:
        monsters = [m for mid in room.monster_ids for m in [db.load_monster(mid)] if m]
        items    = [i for iid in room.item_ids    for i in [db.load_item(iid)]    if i]
        events   = db.get_recent_events(12)

        console.clear()
        renderer.render_game_screen(hero, room, monsters, items, events)

        key = getch().lower()

        if key == "q":
            console.print("\n[dim]Farewell, brave adventurer. 再見！[/dim]")
            break

        elif key in direction_keys:
            direction = direction_keys[key]
            try:
                result = engine.move(hero, direction)
                if result.success and result.new_room:
                    room = result.new_room
            except InvalidMoveError as e:
                console.print(f"[red]{e}[/red]")
                time.sleep(0.8)

        elif key == "f":
            if not monsters:
                console.print("[dim]No enemies here.[/dim]")
                time.sleep(0.5)
            else:
                monster = monsters[0]
                log = engine.full_combat(hero, monster)
                console.clear()
                renderer.render_combat_sequence(log)
                if log.hero_survived:
                    hero, _ = engine.level_up_check(hero)
                else:
                    renderer.render_game_over(hero)
                    time.sleep(3)
                    break
                hero = db.load_hero() or hero
                room = db.load_room(hero.position) or room
                time.sleep(1.5)

        elif key == "p":
            if not items:
                console.print("[dim]Nothing to pick up.[/dim]")
                time.sleep(0.5)
            else:
                try:
                    hero = engine.pickup_item(hero, items[0])
                except InventoryFullError as e:
                    console.print(f"[red]{e}[/red]")
                    time.sleep(0.8)
                room = db.load_room(hero.position) or room

        elif key == "u":
            if not hero.inventory:
                console.print("[dim]Inventory is empty.[/dim]")
                time.sleep(0.5)
            else:
                item = hero.inventory[0]
                hero, msg = engine.use_item(hero, item.id)
                console.print(f"[cyan]{msg}[/cyan]")
                time.sleep(1.2)

        elif key == "m":
            rooms_data = engine.get_world_snapshot().get("rooms", [])
            console.clear()
            renderer.render_world_map(rooms_data, hero.position)
            console.print("\n[dim]Press any key to continue...[/dim]")
            getch()

        elif key == "i":
            console.clear()
            console.print(renderer.render_inventory_panel(hero))
            console.print("\n[dim]Press any key to continue...[/dim]")
            getch()

    api.stop()
    db.close()


# ── stats ─────────────────────────────────────────────────────────────────────

def cmd_stats(args: list[str]) -> None:
    console = Console()
    renderer = GameRenderer(console)
    db = _get_db()
    engine = GameEngine(db)

    try:
        hero, _ = engine.load_game()
        stats = db.get_stats()
        renderer.render_stats_table(stats, hero)
    except GameNotFoundError as e:
        console.print(f"[red]{e}[/red]")
    finally:
        db.close()


# ── serve ─────────────────────────────────────────────────────────────────────

def cmd_serve(args: list[str]) -> None:
    console = Console()
    db = _get_db()
    engine = GameEngine(db)

    try:
        engine.load_game()
    except GameNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        db.close()
        return

    port = int(args[0]) if args else 8765
    api = GameAPIServer(engine, port)
    api.start()
    console.print(f"[green]Browser dashboard running at http://localhost:{port}[/green]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        api.stop()
        db.close()


# ── demo ──────────────────────────────────────────────────────────────────────

def cmd_demo(args: list[str]) -> None:
    """
    Fully automated non-interactive walkthrough.
    Shows the rich TUI, combat, item pickup, level-up, and world map
    without requiring any keyboard input — perfect for demonstrations.
    """
    console = Console()
    renderer = GameRenderer(console)

    # Use an in-memory database so demo never touches disk state
    db = Database(":memory:")
    db.connect()
    engine = GameEngine(db)

    delay = float(args[0]) if args else 0.6

    def pause(msg: str = "", d: float = delay) -> None:
        if msg:
            console.print(msg)
        time.sleep(d)

    # ── 1. Splash ─────────────────────────────────────────────────────────────
    console.clear()
    renderer.render_splash(_get_splash())
    pause("[dim]Starting automated demo...[/dim]", 1.5)

    # ── 2. Create game ────────────────────────────────────────────────────────
    hero, rooms = engine.start_new_game("勇者小明", seed=42)
    room = db.load_room(hero.position)
    console.print(f"\n[bold cyan]✓ World generated:[/bold cyan] {len(rooms)} rooms, seed=42")
    pause(d=1.0)

    # ── 3. Show initial game screen ───────────────────────────────────────────
    console.clear()
    monsters_in_room = [db.load_monster(mid) for mid in room.monster_ids if db.load_monster(mid)]
    items_in_room    = [db.load_item(iid)    for iid in room.item_ids    if db.load_item(iid)]
    events           = db.get_recent_events(12)
    renderer.render_game_screen(hero, room, monsters_in_room, items_in_room, events)
    pause("[dim]↑ Full 4-panel TUI layout[/dim]", 2.0)

    # ── 4. Move around ────────────────────────────────────────────────────────
    for direction in ["north", "east", "south"]:
        try:
            result = engine.move(hero, direction)
            if result.success and result.new_room:
                room = result.new_room
                hero = db.load_hero() or hero
                console.print(f"[cyan]🚶 Moved {direction} → {room.name}[/cyan]")
                pause(d=0.6)
        except Exception:
            pass

    # ── 5. Pick up first item found ───────────────────────────────────────────
    item = next((db.load_item(iid) for iid in room.item_ids if db.load_item(iid)), None)
    if item:
        hero = engine.pickup_item(hero, item)
        console.print(f"[magenta]📦 Picked up: {item.name} ({item.type.value}, power={item.power})[/magenta]")
        pause(d=0.8)

    # ── 6. Use the item ───────────────────────────────────────────────────────
    if hero.inventory:
        hero, msg = engine.use_item(hero, hero.inventory[0].id)
        console.print(f"[blue]🧪 Used item: {msg}[/blue]")
        pause(d=0.8)

    # ── 7. Combat ─────────────────────────────────────────────────────────────
    # Find a room with a monster
    monster = None
    for r in rooms.values():
        for mid in r.monster_ids:
            m = db.load_monster(mid)
            if m:
                monster = m
                # Teleport hero to that room for demo purposes
                hero.position = r.id
                db.save_hero(hero)
                room = r
                break
        if monster:
            break

    if monster:
        console.clear()
        console.print(f"[bold red]⚔  Initiating combat: {hero.name} vs {monster.name}[/bold red]\n")
        pause(d=0.8)
        log = engine.full_combat(hero, monster)
        renderer.render_combat_sequence(log, delay=0.25)
        hero = db.load_hero() or hero
        pause(d=1.5)

    # ── 8. Force a level-up to show celebration ───────────────────────────────
    hero.xp = hero.xp_to_next
    db.save_hero(hero)
    hero, leveled = engine.level_up_check(hero)
    if leveled:
        console.clear()
        renderer.render_level_up(hero)
        pause(d=1.5)

    # ── 9. World map ──────────────────────────────────────────────────────────
    rooms_data = engine.get_world_snapshot().get("rooms", [])
    console.clear()
    renderer.render_world_map(rooms_data, hero.position)
    pause("[dim]↑ World map with explored/unexplored rooms[/dim]", 2.0)

    # ── 10. Stats ─────────────────────────────────────────────────────────────
    stats = db.get_stats()
    console.clear()
    renderer.render_stats_table(stats, hero)
    pause(d=1.5)

    # ── 11. Final summary ─────────────────────────────────────────────────────
    from rich.panel import Panel
    from rich.align import Align
    from rich.text import Text
    from rich import box as rbox
    summary = Text()
    summary.append("Demo complete!\n\n", style="bold green")
    summary.append("What you just saw:\n", style="bold white")
    summary.append("  ✓ Procedural world generation (seed-based, deterministic)\n", style="cyan")
    summary.append("  ✓ SQLite persistence with full event audit trail\n", style="cyan")
    summary.append("  ✓ Rich 4-panel TUI with HP/XP bars, tables, panels\n", style="cyan")
    summary.append("  ✓ Turn-based combat with critical hits & abilities\n", style="cyan")
    summary.append("  ✓ Inventory system with typed items & effects\n", style="cyan")
    summary.append("  ✓ XP & levelling system with stat progression\n", style="cyan")
    summary.append("  ✓ World map with explored/unexplored tracking\n", style="cyan")
    summary.append("  ✓ Live browser dashboard at localhost:8765\n", style="cyan")
    summary.append("  ✓ Full pytest test suite (30+ tests)\n\n", style="cyan")
    summary.append("Clone the repo and run:\n", style="bold white")
    summary.append("  python3 game.py new-game   # start your adventure\n", style="yellow")
    summary.append("  python3 game.py play       # interactive game\n", style="yellow")
    summary.append("  pytest tests/ -v           # run all tests\n", style="yellow")

    console.print(Panel(
        Align.center(summary),
        title="[bold green]⚔  PIXELQUEST Demo Complete  ⚔[/bold green]",
        border_style="green",
        box=rbox.DOUBLE_EDGE,
    ))

    db.close()
