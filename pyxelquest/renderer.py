"""Rich TUI renderer for PyxelQuest."""
from __future__ import annotations

import time
from typing import Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskID, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .models import CombatLog, CombatResult, EventType, GameEvent, Hero, Item, Monster, Room


# ── Zone colour map ──────────────────────────────────────────────────────────
_ZONE_COLOURS = {
    "village": "green",
    "dungeon": "yellow",
    "lair":    "red",
}

_EVENT_COLOURS = {
    EventType.MOVE:        "cyan",
    EventType.COMBAT_HIT:  "red",
    EventType.COMBAT_MISS: "dim white",
    EventType.COMBAT_WIN:  "bold green",
    EventType.COMBAT_LOSE: "bold red",
    EventType.ITEM_PICKUP: "magenta",
    EventType.ITEM_USE:    "blue",
    EventType.LEVEL_UP:    "bold yellow",
    EventType.GAME_START:  "bold cyan",
    EventType.GAME_OVER:   "bold red",
}


class GameRenderer:
    """All Rich rendering lives here — engine/commands never import Rich directly."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    # ── Splash ───────────────────────────────────────────────────────────────

    def render_splash(self, splash_text: str) -> None:
        panel = Panel(
            Align.center(Text(splash_text, style="bold red")),
            title="[bold yellow]⚔  PIXELQUEST  ⚔[/bold yellow]",
            subtitle="[dim]A terminal RPG powered by Claude Code[/dim]",
            border_style="yellow",
            box=box.DOUBLE_EDGE,
            padding=(1, 4),
        )
        self.console.print(panel)

    # ── Hero stats ────────────────────────────────────────────────────────────

    def render_hero_panel(self, hero: Hero) -> Panel:
        zone_colour = "white"  # default when not in a room context

        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(style="dim", width=10)
        tbl.add_column()

        # HP bar
        hp_bar = self._make_bar(hero.hp_pct(), "red", 12)
        tbl.add_row("生命值 HP", f"{hp_bar} {hero.hp}/{hero.max_hp}")

        # XP bar
        xp_bar = self._make_bar(hero.xp_pct(), "cyan", 12)
        tbl.add_row("經驗 XP", f"{xp_bar} {hero.xp}/{hero.xp_to_next}")

        tbl.add_row("等級 LV",  f"[bold yellow]{hero.level}[/]")
        tbl.add_row("攻擊 ATK", f"[bold red]{hero.attack}[/]")
        tbl.add_row("防禦 DEF", f"[bold blue]{hero.defense}[/]")
        tbl.add_row("金幣 GP",  f"[bold yellow]{hero.gold}[/]")
        tbl.add_row("物品 INV", f"{len(hero.inventory)}/{Hero.MAX_INVENTORY}")

        return Panel(
            tbl,
            title=f"[bold cyan]{hero.name}[/]",
            border_style="cyan",
            box=box.ROUNDED,
        )

    def _make_bar(self, pct: float, colour: str, width: int) -> Text:
        filled = int(pct * width)
        bar = Text()
        bar.append("█" * filled, style=f"bold {colour}")
        bar.append("░" * (width - filled), style="dim")
        return bar

    # ── Room ──────────────────────────────────────────────────────────────────

    def render_room_panel(self, room: Room, monsters: list[Monster], items: list[Item]) -> Panel:
        zone_colour = _ZONE_COLOURS.get(room.zone, "white")

        content = Text()
        content.append(f"{room.description}\n", style="white")
        content.append(f"「{room.flavor}」\n\n", style="italic dim")

        # Exits
        exits_txt = "  ".join(
            f"[bold]{d.upper()}[/bold]→{room.exits[d]}" for d in sorted(room.exits)
        )
        content.append(f"出口 Exits: {exits_txt}\n", style="cyan")

        # Monsters
        if monsters:
            content.append("\n⚔  敵人 Enemies:\n", style="bold red")
            for m in monsters:
                hp_bar = self._make_bar(m.hp / m.max_hp, "red", 8)
                content.append(f"  • {m.name} ")
                content.append_text(hp_bar)
                content.append(f" {m.hp}/{m.max_hp} HP\n")
        else:
            content.append("\n✓  Area is safe.\n", style="dim green")

        # Items on ground
        if items:
            content.append("\n📦 物品 Items on ground:\n", style="magenta")
            for it in items:
                content.append(f"  • {it.name} — {it.description}\n", style="dim")

        return Panel(
            content,
            title=f"[bold {zone_colour}]📍 {room.name}[/]",
            subtitle=f"[dim]Zone: {room.zone.title()}[/]",
            border_style=zone_colour,
            box=box.ROUNDED,
        )

    # ── Inventory ─────────────────────────────────────────────────────────────

    def render_inventory_panel(self, hero: Hero) -> Panel:
        if not hero.inventory:
            content = Text("（空的 Empty）", style="dim italic")
        else:
            tbl = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
            tbl.add_column("#",    style="dim",         width=3)
            tbl.add_column("名稱 Name",  style="white",       width=16)
            tbl.add_column("類型 Type",  style="cyan",        width=8)
            tbl.add_column("效果 Power", style="yellow",      width=7)
            for i, item in enumerate(hero.inventory, 1):
                tbl.add_row(
                    str(i),
                    item.name,
                    item.type.value,
                    str(item.power) if item.power else "—",
                )
            content = tbl

        return Panel(
            content,
            title="[magenta]🎒 物品欄 Inventory[/]",
            border_style="magenta",
            box=box.ROUNDED,
        )

    # ── Event log ─────────────────────────────────────────────────────────────

    def render_event_log(self, events: list[GameEvent], max_lines: int = 12) -> Panel:
        content = Text()
        for event in events[-max_lines:]:
            colour = _EVENT_COLOURS.get(event.event_type, "white")
            content.append(f"  {event.message}\n", style=colour)
        if not content._spans:
            content.append("  （無記錄 No events yet）", style="dim italic")

        return Panel(
            content,
            title="[bold white]📜 事件記錄 Event Log[/]",
            border_style="white",
            box=box.ROUNDED,
        )

    # ── Commands help ─────────────────────────────────────────────────────────

    def render_commands_panel(self) -> Panel:
        tbl = Table.grid(padding=(0, 2))
        tbl.add_column(style="bold yellow", width=4)
        tbl.add_column(style="dim white")

        commands = [
            ("W/↑", "向北走 Move North"),
            ("S/↓", "向南走 Move South"),
            ("A/←", "向西走 Move West"),
            ("D/→", "向東走 Move East"),
            ("F",   "戰鬥 Fight"),
            ("I",   "物品欄 Inventory"),
            ("U",   "使用物品 Use Item"),
            ("P",   "撿起物品 Pickup"),
            ("M",   "顯示地圖 Map"),
            ("Q",   "離開遊戲 Quit"),
        ]
        for key, desc in commands:
            tbl.add_row(f"[{key}]", desc)

        return Panel(
            tbl,
            title="[dim]⌨  Controls[/]",
            border_style="dim",
            box=box.ROUNDED,
        )

    # ── World map ─────────────────────────────────────────────────────────────

    def render_world_map(self, rooms: list[dict], hero_pos: str) -> Panel:
        """ASCII grid map coloured by zone/visit status."""
        zone_order = ["village", "dungeon", "lair"]
        by_zone: dict[str, list[dict]] = {z: [] for z in zone_order}
        for room in rooms:
            zone = room.get("zone", "village")
            if zone in by_zone:
                by_zone[zone].append(room)

        content = Text()
        for zone in zone_order:
            zone_rooms = by_zone[zone]
            colour = _ZONE_COLOURS.get(zone, "white")
            content.append(f"\n  {zone.title()} Zone\n", style=f"bold {colour}")
            for room in zone_rooms:
                if room["id"] == hero_pos:
                    marker = "[bold yellow]▶ [/]"
                    name_style = "bold yellow"
                elif room.get("visited"):
                    marker = "  ✓ "
                    name_style = colour
                else:
                    marker = "  ░ "
                    name_style = "dim"

                exits = "  ".join(room.get("exits", {}).keys()).upper()
                content.append(marker)
                content.append(f"{room['name']}", style=name_style)
                content.append(f"  [{exits}]\n", style="dim")

        return Panel(
            content,
            title="[bold white]🗺  世界地圖 World Map[/]",
            border_style="white",
            box=box.ROUNDED,
        )

    # ── Full game screen ──────────────────────────────────────────────────────

    def render_game_screen(
        self,
        hero: Hero,
        room: Room,
        monsters: list[Monster],
        items: list[Item],
        events: list[GameEvent],
    ) -> None:
        layout = Layout()
        layout.split_column(
            Layout(name="top", size=3),
            Layout(name="main"),
            Layout(name="bottom", size=3),
        )
        layout["main"].split_row(
            Layout(name="left",   ratio=1),
            Layout(name="center", ratio=2),
            Layout(name="right",  ratio=1),
        )

        layout["top"].update(
            Panel(
                Align.center(
                    Text(
                        f"⚔  PIXELQUEST  ⚔   |   {hero.name}   |   "
                        f"Level {hero.level}   |   {room.name}   |   "
                        f"HP {hero.hp}/{hero.max_hp}   |   Gold {hero.gold}",
                        style="bold yellow",
                    )
                ),
                box=box.HORIZONTALS,
                border_style="yellow",
            )
        )
        layout["left"].update(self.render_hero_panel(hero))
        layout["center"].update(self.render_room_panel(room, monsters, items))
        layout["right"].update(self.render_inventory_panel(hero))
        layout["bottom"].update(self.render_event_log(events, max_lines=2))

        self.console.print(layout)

    # ── Combat animation ──────────────────────────────────────────────────────

    def render_combat_sequence(self, log: CombatLog, delay: float = 0.3) -> None:
        title_colour = "green" if log.hero_survived else "red"
        self.console.print(Rule(
            f"[bold]⚔  COMBAT: {log.hero_name}  vs  {log.monster_name}[/]",
            style="bold yellow",
        ))

        for i, result in enumerate(log.rounds):
            colour = _EVENT_COLOURS.get(
                EventType.COMBAT_MISS if result.is_miss else EventType.COMBAT_HIT, "white"
            )
            prefix = "💥" if result.is_critical else ("✗" if result.is_miss else "▸")
            self.console.print(f"  {prefix}  {result.message}", style=colour)
            time.sleep(delay)

        outcome_style = f"bold {title_colour}"
        self.console.print(Rule(style=title_colour))
        self.console.print(
            Panel(
                Align.center(Text(log.summary, style=outcome_style)),
                border_style=title_colour,
                box=box.DOUBLE_EDGE,
            )
        )

    # ── Stats table ───────────────────────────────────────────────────────────

    def render_stats_table(self, stats: dict, hero: Hero) -> None:
        tbl = Table(
            title="📊 遊戲統計 Game Statistics",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            show_header=True,
        )
        tbl.add_column("指標 Metric",  style="dim white",   width=25)
        tbl.add_column("數值 Value",   style="bold yellow",  width=20)

        rows = [
            ("英雄名稱 Hero",          hero.name),
            ("等級 Level",             str(hero.level)),
            ("生命值 HP",              f"{hero.hp}/{hero.max_hp}"),
            ("攻擊力 Attack",          str(hero.attack)),
            ("防禦力 Defense",         str(hero.defense)),
            ("金幣 Gold",              str(hero.gold)),
            ("─────────────", "────────────────"),
            ("擊殺數 Kills",           str(stats.get("monsters_killed", 0))),
            ("探索房間 Rooms",         str(stats.get("rooms_explored", 0))),
            ("拾取物品 Items",         str(stats.get("items_found", 0))),
            ("升等次數 Level-ups",     str(stats.get("level_ups", 0))),
            ("世界種子 World Seed",    stats.get("world_seed", "?")),
            ("事件總數 Total Events",  str(stats.get("total_events", 0))),
        ]
        for metric, value in rows:
            tbl.add_row(metric, value)

        self.console.print(tbl)

    # ── Level-up celebration ──────────────────────────────────────────────────

    def render_level_up(self, hero: Hero) -> None:
        msg = (
            f"✨  LEVEL UP!  ✨\n\n"
            f"{hero.name} is now Level [bold]{hero.level}[/bold]!\n"
            f"HP +8  ·  ATK +2  ·  DEF +1\n"
            f"HP fully restored!"
        )
        self.console.print(
            Panel(
                Align.center(Text.from_markup(msg)),
                border_style="bold yellow",
                box=box.DOUBLE_EDGE,
                title="[bold yellow]⭐  LEVEL UP  ⭐[/]",
            )
        )

    # ── Game over ─────────────────────────────────────────────────────────────

    def render_game_over(self, hero: Hero) -> None:
        msg = (
            f"💀  GAME OVER  💀\n\n"
            f"{hero.name} has fallen.\n"
            f"Reached Level {hero.level} with {hero.gold} gold.\n\n"
            f"[dim]Run 'python3 game.py new-game' to try again.[/dim]"
        )
        self.console.print(
            Panel(
                Align.center(Text.from_markup(msg)),
                border_style="bold red",
                box=box.DOUBLE_EDGE,
                title="[bold red]☠  DEFEAT  ☠[/]",
            )
        )
