#!/usr/bin/env python3
"""
PixelQuest — Terminal RPG powered by Claude Code.

Usage:
    python3 game.py                  # show help
    python3 game.py new-game [seed]  # create a new world
    python3 game.py play             # interactive adventure
    python3 game.py demo [speed]     # automated showcase (no keyboard needed)
    python3 game.py stats            # display game statistics
    python3 game.py serve [port]     # start browser dashboard only
"""
import sys
from pathlib import Path

# Ensure the project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from pyxelquest.commands import cmd_demo, cmd_new_game, cmd_play, cmd_serve, cmd_stats


def _print_help(console: Console) -> None:
    help_text = Text()
    help_text.append("⚔  PIXELQUEST 像素冒險  ⚔\n\n", style="bold yellow")
    help_text.append("A terminal RPG demonstrating Claude Code's capabilities.\n\n", style="dim")

    commands = [
        ("new-game [seed]", "建立新遊戲 / Create a new world (optional seed for reproducibility)"),
        ("play",            "開始冒險 / Start the interactive adventure"),
        ("demo [speed]",    "自動展示 / Automated showcase (no keyboard needed, speed=0.1–2.0)"),
        ("stats",           "遊戲統計 / Display current game statistics"),
        ("serve [port]",    "瀏覽器介面 / Start browser dashboard only (default port 8765)"),
    ]

    for cmd, desc in commands:
        help_text.append(f"  python3 game.py ", style="dim")
        help_text.append(f"{cmd:<22}", style="bold cyan")
        help_text.append(f"  {desc}\n", style="white")

    help_text.append("\nBrowser dashboard: ", style="dim")
    help_text.append("http://localhost:8765", style="bold underline cyan")
    help_text.append("  (auto-starts with 'play')\n", style="dim")
    help_text.append("\nRun tests: ", style="dim")
    help_text.append("pytest tests/ -v\n", style="bold yellow")

    console.print(Panel(
        help_text,
        title="[bold yellow]⚔  PIXELQUEST  ⚔[/bold yellow]",
        border_style="yellow",
        box=box.DOUBLE_EDGE,
        padding=(1, 3),
    ))


_COMMANDS = {
    "new-game": cmd_new_game,
    "play":     cmd_play,
    "demo":     cmd_demo,
    "stats":    cmd_stats,
    "serve":    cmd_serve,
}


def main() -> int:
    console = Console()
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help(console)
        return 0

    cmd_name = argv[0]
    cmd_args = argv[1:]

    if cmd_name not in _COMMANDS:
        console.print(f"[red]Unknown command: {cmd_name!r}[/red]")
        console.print("[dim]Run 'python3 game.py' to see available commands.[/dim]")
        return 1

    try:
        _COMMANDS[cmd_name](cmd_args)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        return 0
    except Exception as exc:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
