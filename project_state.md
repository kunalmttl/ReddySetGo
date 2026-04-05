# project_state.md — reddy_set_go

## Current State: ✅ Operational (Live Monitoring + Auto-Betting Active)

All scripts functional. Live listener (`live_monitor.py`) monitors **satta automation** channel and automatically places bets on Reddybook via Playwright. Offline analysis complete with 225 match records in `matches.csv`.

---

## File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `live_monitor.py` | 195 | Live Telegram listener + Reddybook auto-betting orchestrator | ✅ Working |
| `bet_action.py` | 408 | Playwright browser automation (login, find match, place bet, cashout, loss cut) | ✅ Working |
| `state.py` | 76 | Match state tracker + stake calculator (5% limit, 40/60 split) | ✅ Working |
| `history_replay.py` | 326 | Offline replay engine — iterates past messages, parses & tracks match lifecycle | ✅ Working |
| `tg_listener.py` | 240 | Live real-time listener — event-driven state machine, logs every message (no betting) | ✅ Working |
| `parser.py` | 271 | Message classifier — identifies 12 message types, extracts teams/odds | ✅ Working |
| `config.py` | 35 | Env-based config loader (reads `.env`, no hardcoded secrets) | ✅ Working |
| `export_history.py` | 91 | One-time exporter — dumps channel history to JSONL | ✅ Used (3055 msgs) |
| `new_test.py` | 18 | Telegram session login test | ✅ Working |
| `.env` | 16 | Secrets, channel config, site creds, risk params (gitignored) | ✅ Configured |
| `.gitignore` | 17 | Protects `.session`, `.env`, `__pycache__`, `.venv` | ✅ Active |
| `channel_history_1y.jsonl` | 3055 lines | Offline message backup (Feb 2025 – Feb 2026) | ✅ Complete |
| `matches.csv` | 225 rows | Processed match results from offline analysis | ✅ Generated |
| `anomalies.csv` | 1 line (header only) | Anomaly tracking — currently empty | ⚠️ Unused |
| `context.md` | 190 lines | Project documentation | ✅ Updated |

---

## Active Target Channel

- **Name**: satta automation
- **Channel ID**: `-1003898959289`
- **Invite link**: `https://t.me/+CK-lEZsWXOZmMjY1`
- **Previously tracked**: D COMPANY TIPS DUBAI 💰 (`-1001165742515`)

---

## Betting Site

- **URL**: `https://reddybook.live`
- **Login page**: `/home`
- **Cricket page**: `/sports/4`
- **Bet type**: Sportsbook (fixed odds, back bets)
- **Odds format**: Channel `46p` → Decimal `1.46`

---

## Message Type Distribution (3055 messages — D COMPANY channel)

| Type | Count | % |
|------|-------|---|
| EMPTY | 1143 | 37.4% |
| OTHER | 718 | 23.5% |
| MATCH_SETUP | 225 | 7.4% |
| WIN_POST | 195 | 6.4% |
| SIGNAL_CASHOUT_BOOK | 190 | 6.2% |
| SIGNAL_FIRST_ENTRY | 172 | 5.6% |
| ODDS_UPDATE | 174 | 5.7% |
| SIGNAL_WAIT | 88 | 2.9% |
| LOSS_POST | 50 | 1.6% |
| SIGNAL_LOSS_CUT | 47 | 1.5% |
| SIGNAL_JACKPOT_ENTRY | 40 | 1.3% |
| MATCH_CANCELLED | 13 | 0.4% |

---

## Match Results Summary (225 matches)

| End Type | Count | Notes |
|----------|-------|-------|
| CASHOUT | ~95 | Profit locked early |
| WIN | ~60 | Match won confirmation |
| LOSS | ~35 | Explicit loss posts |
| LOSS_CUT | ~20 | Loss cut signals |
| UNCLOSED | ~15 | No clear close before next setup |

Date range: **2025-02-16 → 2026-02-05**

---

## Code Architecture

### live_monitor.py — Orchestrator (Telegram + Playwright)
- Starts Playwright browser → logs into Reddybook
- Starts Telethon client → listens to channel
- Routes signals to `BetAction` methods:
  - `MATCH_SETUP` → fetch balance, calc stake, find match on site
  - `FIRST ENTRY` → place back bet (40% of limit)
  - `JACKPOT` → place second back bet (60% of limit)
  - `CASHOUT` → click cashout, accept pre-filled amount
  - `LOSS CUT` → click loss cut, accept pre-filled amount
  - `WIN/LOSS/CANCEL` → close match state

### bet_action.py — Playwright Browser Automation
- **Login**: Navigates to `/home`, fills credentials, clicks submit
- **Balance**: Reads balance from header
- **Find match**: Goes to `/sports/4`, searches for team keywords
- **Place bet**: Clicks BACK (blue) odds for predicted winner, enters stake, clicks "PLACE BET"
- **Cashout/Loss Cut**: Clicks button, accepts pre-filled stake, clicks "PLACE BET"
- **Retry logic**: Retries indefinitely on "odds changed", aborts if drift >15%
- **Anti-detection**: Disables `navigator.webdriver`, custom user agent, `--no-sandbox`

### state.py — Match State + Stake Calculator
- **Match limit**: 5% of balance
- **First entry**: 40% of limit
- **Jackpot**: 60% of limit
- **Stake rounding**: Nearest ₹100, minimum ₹100

### history_replay.py — Offline Replay Engine
- **Date range**: `START_UTC` / `END_UTC` constants
- **`ASSUME_UNCLOSED_AS_LOSS = True`**: Unclosed matches counted as losses
- **`MAX_ENTRIES_PER_MATCH = 2`**: Max 2 entry signals per match

### parser.py — Message Classifier
- **12 message types**: EMPTY, MATCH_SETUP, SIGNAL_WAIT, SIGNAL_LOSS_CUT, SIGNAL_CASHOUT_BOOK, WIN_POST, LOSS_POST, SIGNAL_FIRST_ENTRY, SIGNAL_JACKPOT_ENTRY, ODDS_UPDATE, OTHER, MATCH_CANCELLED
- **Entry detection**: Requires odds (`NNp`) + strong CTA (KARO, KARLO, PLUS, etc.)
- **Jackpot disambiguation**: Accepts "JACKPOT BANEGA/BANEGI" (future), rejects "JACKPOT BANA HAI" (recap)
- **Line-by-line regex**: Preserves newlines for accurate team/winner extraction

### tg_listener.py — Real-time Listener (No Betting)
- Event-driven: Uses `@client.on(events.NewMessage)` handler
- Logs every message: Shows msg ID, timestamp, parsed type, and action
- Deduplication: `recent_ids` deque (maxlen=500)

### config.py — Env-based Config
- Reads `.env` file at import time
- No hardcoded secrets — all values from environment
- Supports Telegram, Reddybook, and risk management settings

---

## Configuration (.env)

| Setting | Value | Notes |
|---------|-------|-------|
| `API_ID` | `33508270` | From my.telegram.org |
| `API_HASH` | `04004...` | From my.telegram.org |
| `SESSION_NAME` | `"tg2_session"` | Active session file exists |
| `TARGET_CHAT_ID` | `-1003898959289` | satta automation |
| `SITE_URL` | `https://reddybook.live/home` | Betting site login page |
| `HEADLESS` | `False` | Visible browser window |
| `MATCH_LIMIT_PCT` | `5` | 5% of balance per match |
| `FIRST_ENTRY_PCT` | `40` | 40% of limit for first entry |
| `JACKPOT_PCT` | `60` | 60% of limit for jackpot |
| `ODDS_DRIFT_ABORT` | `15` | Abort if odds drift >15% |

---

## Known Issues / TODOs

- [ ] **`anomalies.csv` is empty** — header exists but no anomaly detection logic populates it
- [ ] **`INNINGS_UPDATE` type not handled** — parser doesn't have a dedicated type for it (falls to OTHER)
- [ ] **Playwright selectors are best-guess** — may need adjustment after first live test (BACK odds buttons, stake input, etc.)
- [ ] **No error handling for network failures** — scripts will crash on disconnect
- [ ] **`.env` contains real credentials** — should use `.env.example` template for repo
- [ ] **No DRY_RUN mode** — would be useful for testing without placing real bets

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `telethon` | 1.42.0 | Telegram client library |
| `playwright` | 1.58.0 | Browser automation |

Virtual env: `.venv` (Python 3.10)

---

## How to Run

### Live monitoring + automated betting
```bash
.venv\Scripts\python.exe live_monitor.py
```

### Live Telegram listener only (no betting)
```bash
.venv\Scripts\python.exe tg_listener.py
```

### Offline history replay
```bash
.venv\Scripts\python.exe history_replay.py
```

### Test Telegram session
```bash
.venv\Scripts\python.exe new_test.py
```

### Re-export channel history (if needed)
```bash
.venv\Scripts\python.exe export_history.py
```
