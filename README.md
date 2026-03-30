# PixelQuest 像素冒險

> 一個展示 **Claude Code** 能力的終端機 RPG 遊戲引擎
> A terminal RPG engine built entirely by Claude Code to demonstrate its capabilities

```
    /\      /\
   /  \    /  \       ____  _          _  ___                  _
  / /\ \  / /\ \     |  _ \(_)_  _____| |/ _ \ _   _  ___  ___| |_
 / /  \ \/ /  \ \    | |_) | \ \/ / _ \ | | | | | | |/ _ \/ __| __|
/ /    \  /    \ \   |  __/| |>  <  __/ | |_| | |_| |  __/\__ \ |_
\/      \/      \/   |_|   |_/_/\_\___|_|\__\_\\__,_|\___||___/\__|

          ⚔  像素冒險 · PixelQuest · Powered by Claude Code  ⚔
```

## 快速開始 / Quick Start

```bash
# 安裝依賴 Install dependencies
pip install rich pytest

# 建立新遊戲 Create a new world
python3 game.py new-game

# 開始冒險 Play the game
python3 game.py play

# 全自動展示（不需要鍵盤）Automated demo (no keyboard needed)
python3 game.py demo

# 執行測試 Run tests
pytest tests/ -v
```

## 功能特色 / Features

| 功能 | 說明 |
|------|------|
| 🌍 程序化世界生成 | 種子隨機算法，相同種子產生相同世界 |
| ⚔ 回合制戰鬥 | 暴擊、閃避、特殊技能、完整日誌 |
| 🎒 物品系統 | 藥水、武器、護甲、鑰匙、寶藏 |
| 📈 升等系統 | XP 門檻、屬性提升、HP 完全恢復 |
| 🗺 地圖追蹤 | 已探索/未探索房間的視覺化地圖 |
| 🌐 瀏覽器儀表板 | 即時 JSON API + CSS Grid 動態介面 |
| 📊 遊戲統計 | 擊殺數、探索房間、拾取物品等統計 |
| 🧪 完整測試 | 30+ pytest 測試覆蓋所有核心邏輯 |
| 🎨 Rich TUI | 4 面板佈局、進度條、彩色表格 |

## 指令說明 / Commands

```bash
python3 game.py new-game [seed]  # 建立新世界（可選：指定種子）
python3 game.py play             # 互動遊戲（WASD 移動）
python3 game.py demo [speed]     # 自動展示（speed=0.1~2.0 秒/步）
python3 game.py stats            # 顯示統計資料
python3 game.py serve [port]     # 只啟動瀏覽器儀表板
```

## 遊戲按鍵 / Controls

| 按鍵 | 功能 |
|------|------|
| W/A/S/D | 移動（北/西/南/東）|
| F | 戰鬥 |
| P | 撿起物品 |
| U | 使用物品（第一個）|
| I | 查看物品欄 |
| M | 顯示世界地圖 |
| Q | 離開遊戲 |

## 瀏覽器儀表板 / Browser Dashboard

執行 `python3 game.py play` 後，在瀏覽器開啟：

```
http://localhost:8765
```

儀表板功能：
- 即時英雄狀態（HP/XP 進度條）
- CSS Grid 世界地圖（綠=已探索，灰=未知，金=當前位置）
- 滾動事件記錄（每 2 秒自動更新）
- 遊戲統計彙總

## 架構 / Architecture

```
game.py (CLI 入口)
    └── pyxelquest/commands.py (命令層)
         ├── renderer.py     (Rich TUI 終端機介面)
         ├── api_server.py   (HTTP API + 瀏覽器儀表板, daemon thread)
         └── engine.py       (領域邏輯：戰鬥、移動、物品、升等)
              ├── world.py   (程序化世界生成)
              ├── db.py      (SQLite 持久化)
              └── models.py  (純資料層：Hero, Monster, Item, Room, GameEvent)
```

## 測試 / Testing

```bash
pytest tests/ -v
```

測試涵蓋：
- `test_models.py` — 資料模型序列化/反序列化
- `test_db.py` — 資料庫 CRUD 與事件記錄
- `test_world.py` — 世界生成確定性、連通性、區域分佈
- `test_engine.py` — 戰鬥、移動、物品、升等邏輯
- `test_api.py` — HTTP API 端點與回應格式

## 技術細節 / Tech Details

- **Python 3.10+**，僅使用標準庫 + `rich`
- **SQLite WAL 模式** — 允許 HTTP 伺服器執行緒並發讀取
- **Daemon thread** — HTTP API 伺服器在背景執行，不阻塞遊戲迴圈
- **種子隨機** — 相同種子保證相同世界（測試友善）
- **純函式領域邏輯** — `engine.py` 不含 I/O，易於單元測試

---

*Built by [Claude Code](https://claude.ai/code) — Anthropic's official CLI for Claude*
