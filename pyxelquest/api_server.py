"""Lightweight HTTP JSON API + browser dashboard running in a daemon thread."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .engine import GameEngine


# ── HTML dashboard (self-contained, no external deps) ────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PixelQuest Live Dashboard</title>
<style>
  :root {
    --bg: #0d0d0d; --card: #1a1a2e; --accent: #e94560;
    --gold: #f5a623; --green: #4caf50; --cyan: #00bcd4;
    --red: #f44336; --dim: #666; --text: #e0e0e0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; padding: 16px; }
  h1 { color: var(--gold); text-align: center; font-size: 1.8em; letter-spacing: 4px; margin-bottom: 4px; }
  .subtitle { text-align: center; color: var(--dim); margin-bottom: 20px; font-size: 0.85em; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-width: 1100px; margin: 0 auto; }
  .card { background: var(--card); border: 1px solid #333; border-radius: 8px; padding: 16px; }
  .card h2 { color: var(--cyan); border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 12px; font-size: 1em; letter-spacing: 2px; }
  .stat-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #111; }
  .stat-label { color: var(--dim); }
  .stat-val { color: var(--gold); font-weight: bold; }
  .bar-wrap { background: #111; border-radius: 4px; height: 10px; overflow: hidden; margin-top: 2px; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
  .hp-fill { background: var(--red); }
  .xp-fill { background: var(--cyan); }
  .event { padding: 4px 0; border-bottom: 1px solid #111; font-size: 0.82em; }
  .event-move { color: var(--cyan); }
  .event-combat_win { color: var(--green); font-weight: bold; }
  .event-combat_lose { color: var(--red); font-weight: bold; }
  .event-combat_hit { color: #ff8a65; }
  .event-combat_miss { color: var(--dim); }
  .event-item_pickup { color: #ce93d8; }
  .event-item_use { color: #90caf9; }
  .event-level_up { color: var(--gold); font-weight: bold; }
  .event-game_start { color: var(--cyan); }
  .map-zone { margin-bottom: 12px; }
  .map-zone h3 { font-size: 0.85em; margin-bottom: 6px; }
  .room-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 0.82em; }
  .room-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .dot-current { background: var(--gold); box-shadow: 0 0 6px var(--gold); }
  .dot-visited { background: var(--green); }
  .dot-unvisited { background: #333; }
  .room-name { color: var(--text); }
  .room-exits { color: var(--dim); font-size: 0.75em; }
  .status-bar { text-align: center; color: var(--dim); font-size: 0.75em; margin-top: 16px; }
  .full-width { grid-column: 1 / -1; }
  #error { color: var(--red); text-align: center; padding: 20px; display: none; }
</style>
</head>
<body>
<h1>⚔  PIXELQUEST  ⚔</h1>
<p class="subtitle">Live Game Dashboard — Powered by Claude Code</p>
<p id="error">⚠ Could not connect to game. Is it running?</p>
<div class="grid" id="dashboard">
  <div class="card" id="hero-card"><h2>🧙 英雄狀態 HERO</h2><div id="hero-content">Loading...</div></div>
  <div class="card" id="stats-card"><h2>📊 統計 STATS</h2><div id="stats-content">Loading...</div></div>
  <div class="card full-width" id="map-card"><h2>🗺 世界地圖 WORLD MAP</h2><div id="map-content">Loading...</div></div>
  <div class="card full-width" id="events-card"><h2>📜 事件記錄 EVENTS</h2><div id="events-content">Loading...</div></div>
</div>
<p class="status-bar" id="status-bar">Connecting...</p>
<script>
async function refresh() {
  try {
    const [status, events, world, stats] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/events').then(r => r.json()),
      fetch('/api/world').then(r => r.json()),
      fetch('/api/stats').then(r => r.json()),
    ]);
    document.getElementById('error').style.display = 'none';
    document.getElementById('dashboard').style.opacity = '1';
    if (status.hero && status.hero.name) renderHero(status.hero);
    renderStats(stats);
    renderMap(world.rooms || [], (status.hero || {}).position);
    renderEvents(events);
    document.getElementById('status-bar').textContent =
      'Last updated: ' + new Date().toLocaleTimeString() + ' · Auto-refresh every 2s';
  } catch(e) {
    document.getElementById('error').style.display = 'block';
    document.getElementById('dashboard').style.opacity = '0.3';
  }
}

function bar(pct, cls) {
  return `<div class="bar-wrap"><div class="bar-fill ${cls}" style="width:${Math.round(pct*100)}%"></div></div>`;
}

function renderHero(h) {
  const hpPct = h.hp / h.max_hp;
  const xpPct = h.xp / h.xp_to_next;
  document.getElementById('hero-content').innerHTML = `
    <div class="stat-row"><span class="stat-label">名稱 Name</span><span class="stat-val">${h.name}</span></div>
    <div class="stat-row"><span class="stat-label">等級 Level</span><span class="stat-val">${h.level}</span></div>
    <div class="stat-row"><span class="stat-label">HP</span><span class="stat-val">${h.hp}/${h.max_hp}</span></div>
    ${bar(hpPct, 'hp-fill')}
    <div class="stat-row"><span class="stat-label">XP</span><span class="stat-val">${h.xp}/${h.xp_to_next}</span></div>
    ${bar(xpPct, 'xp-fill')}
    <div class="stat-row"><span class="stat-label">攻擊 ATK</span><span class="stat-val">${h.attack}</span></div>
    <div class="stat-row"><span class="stat-label">防禦 DEF</span><span class="stat-val">${h.defense}</span></div>
    <div class="stat-row"><span class="stat-label">金幣 Gold</span><span class="stat-val">${h.gold} gp</span></div>
    <div class="stat-row"><span class="stat-label">位置 Pos</span><span class="stat-val">${h.position}</span></div>
    <div class="stat-row"><span class="stat-label">物品 Items</span><span class="stat-val">${(h.inventory||[]).length}/10</span></div>
  `;
}

function renderStats(s) {
  document.getElementById('stats-content').innerHTML = `
    <div class="stat-row"><span class="stat-label">擊殺 Kills</span><span class="stat-val">${s.monsters_killed}</span></div>
    <div class="stat-row"><span class="stat-label">探索 Rooms</span><span class="stat-val">${s.rooms_explored}</span></div>
    <div class="stat-row"><span class="stat-label">拾取 Items</span><span class="stat-val">${s.items_found}</span></div>
    <div class="stat-row"><span class="stat-label">升等 LvUp</span><span class="stat-val">${s.level_ups}</span></div>
    <div class="stat-row"><span class="stat-label">世界種子 Seed</span><span class="stat-val">${s.world_seed}</span></div>
    <div class="stat-row"><span class="stat-label">事件 Events</span><span class="stat-val">${s.total_events}</span></div>
  `;
}

function renderMap(rooms, heroPos) {
  const zones = {village:[], dungeon:[], lair:[]};
  rooms.forEach(r => { if(zones[r.zone]) zones[r.zone].push(r); });
  const zoneColors = {village:'#4caf50', dungeon:'#f5a623', lair:'#f44336'};
  let html = '';
  for(const [zone, rs] of Object.entries(zones)) {
    if(!rs.length) continue;
    html += `<div class="map-zone"><h3 style="color:${zoneColors[zone]}">${zone.charAt(0).toUpperCase()+zone.slice(1)} Zone</h3>`;
    rs.forEach(r => {
      const isCurrent = r.id === heroPos;
      const dotCls = isCurrent ? 'dot-current' : r.visited ? 'dot-visited' : 'dot-unvisited';
      const exits = Object.keys(r.exits||{}).join(' ').toUpperCase();
      const prefix = isCurrent ? '▶ ' : '';
      html += `<div class="room-row">
        <div class="room-dot ${dotCls}"></div>
        <span class="room-name">${prefix}${r.name}</span>
        <span class="room-exits">[${exits}]</span>
      </div>`;
    });
    html += '</div>';
  }
  document.getElementById('map-content').innerHTML = html;
}

function renderEvents(events) {
  const html = events.slice().reverse().map(e => {
    const cls = 'event event-' + e.event_type;
    const ts = new Date(e.timestamp * 1000).toLocaleTimeString();
    return `<div class="${cls}">[${ts}] ${e.message}</div>`;
  }).join('');
  document.getElementById('events-content').innerHTML = html || '<div class="event" style="color:#666">No events yet.</div>';
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


class _RequestHandler(BaseHTTPRequestHandler):
    engine: "GameEngine"  # set by GameAPIServer before starting

    def log_message(self, format: str, *args) -> None:
        pass  # suppress access log noise

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/" or path == "/index.html":
                self._send_html(_HTML_TEMPLATE)

            elif path == "/api/status":
                snapshot = self.server.engine.get_world_snapshot()  # type: ignore[attr-defined]
                hero_dict = snapshot.get("hero", {})
                self._send_json({"hero": hero_dict, "turn": snapshot.get("stats", {}).get("total_events", 0)})

            elif path == "/api/events":
                snapshot = self.server.engine.get_world_snapshot()  # type: ignore[attr-defined]
                self._send_json(snapshot.get("events", []))

            elif path == "/api/world":
                snapshot = self.server.engine.get_world_snapshot()  # type: ignore[attr-defined]
                self._send_json({"rooms": snapshot.get("rooms", [])})

            elif path == "/api/stats":
                snapshot = self.server.engine.get_world_snapshot()  # type: ignore[attr-defined]
                self._send_json(snapshot.get("stats", {}))

            else:
                self._send_json({"error": "Not found"}, 404)

        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)


class GameAPIServer:
    """HTTP server running in a background daemon thread."""

    def __init__(self, engine: "GameEngine", port: int = 8765):
        self.engine = engine
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        _RequestHandler.engine = self.engine  # type: ignore[attr-defined]
        self._server = HTTPServer(("", self.port), _RequestHandler)
        self._server.engine = self.engine  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
