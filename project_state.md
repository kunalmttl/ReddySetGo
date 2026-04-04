# project_state.md — reddy_set_go

## Current State: ✅ Operational (Live Monitoring Active)

All scripts functional. Live listener (`tg_listener.py`) actively monitors **satta automation** channel. Offline analysis complete with 225 match records in `matches.csv`.

---

## File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `history_replay.py` | 326 | Offline replay engine — iterates past messages, parses & tracks match lifecycle | ✅ Working |
| `tg_listener.py` | 240 | Live real-time listener — event-driven state machine, logs every message | ✅ Working |
| `parser.py` | 271 | Message classifier — identifies 12 message types, extracts teams/odds | ✅ Working |
| `config.py` | 21 | Env-based config loader (reads `.env`, no hardcoded secrets) | ✅ Working |
| `export_history.py` | 91 | One-time exporter — dumps channel history to JSONL | ✅ Used (3055 msgs) |
| `new_test.py` | 18 | Telegram session login test | ✅ Working |
| `.env` | 6 | Secrets & channel config (gitignored) | ✅ Configured |
| `.gitignore` | 17 | Protects `.session`, `.env`, `__pycache__`, `.venv` | ✅ Active |
| `channel_history_1y.jsonl` | 3055 lines | Offline message backup (Feb 2025 – Feb 2026) | ✅ Complete |
| `matches.csv` | 225 rows | Processed match results from offline analysis | ✅ Generated |
| `anomalies.csv` | 1 line (header only) | Anomaly tracking — currently empty | ⚠️ Unused |
| `context.md` | 169 lines | Project documentation | ✅ Updated |

---

## Active Target Channel

- **Name**: satta automation
- **Channel ID**: `-1003898959289`
- **Invite link**: `https://t.me/+CK-lEZsWXOZmMjY1`
- **Previously tracked**: D COMPANY TIPS DUBAI 💰 (`-1001165742515`)

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

### history_replay.py — Offline Replay Engine
- **Date range**: `START_UTC` / `END_UTC` constants (currently set to IPL 2026: Mar 28 – Apr 4)
- **`ASSUME_UNCLOSED_AS_LOSS = True`**: Unclosed matches counted as losses
- **`MAX_ENTRIES_PER_MATCH = 2`**: Max 2 entry signals per match
- **State machine**: `MatchState` dataclass tracks active match, entries count
- **Odds extraction**: `extract_favorite_odds()` finds lowest `p` value (strongest favorite)
- **Global counters**: `wins`, `explicit_match_losses`, `general_loss_posts`, `unclosed_matches`, `assumed_losses`, `ignored`

### parser.py — Message Classifier
- **12 message types**: EMPTY, MATCH_SETUP, SIGNAL_WAIT, SIGNAL_LOSS_CUT, SIGNAL_CASHOUT_BOOK, WIN_POST, LOSS_POST, SIGNAL_FIRST_ENTRY, SIGNAL_JACKPOT_ENTRY, ODDS_UPDATE, OTHER, MATCH_CANCELLED
- **Entry detection**: Requires odds (`NNp`) + strong CTA (KARO, KARLO, PLUS, etc.)
- **Jackpot disambiguation**: Accepts "JACKPOT BANEGA/BANEGI" (future), rejects "JACKPOT BANA HAI" (recap)
- **Loss negation**: "NO LOSS", "NO PROFIT" phrases prevent false loss detection
- **Cancel detection**: "CALLED OFF", "ABANDONED", "MATCH NHI HOGA", etc.
- **Line-by-line regex**: Preserves newlines for accurate team/winner extraction

### tg_listener.py — Real-time Listener
- **Event-driven**: Uses `@client.on(events.NewMessage)` handler
- **Logs every message**: Shows msg ID, timestamp, parsed type, and action
- **Deduplication**: `recent_ids` deque (maxlen=500) prevents double-processing
- **Entry rules**: First entry #1 always allowed; #2 only if odds improved (fav p increased)
- **State tracking**: `first_count`, `jackpot_done`, `first1_fav_p/team`
- **Auto-join**: Attempts invite hash if configured

### config.py — Env-based Config
- Reads `.env` file at import time
- No hardcoded secrets — all values from environment
- Supports `TARGET_CHAT_ID`, `TARGET_CHAT_USERNAME`, `TARGET_INVITE_HASH`

### export_history.py — History Exporter
- **One-time use**: Already ran, produced `channel_history_1y.jsonl`
- **Fields exported**: chat_id, msg_id, date_utc, raw_text, is_reply, reply_to_msg_id, is_forward, forward_from, has_media, media_type, grouped_id, views, forwards, edit_date_utc, post_author, sender_id

---

## Configuration (.env)

| Setting | Value | Notes |
|---------|-------|-------|
| `API_ID` | `33508270` | From my.telegram.org |
| `API_HASH` | `04004...` | From my.telegram.org |
| `SESSION_NAME` | `"tg2_session"` | Active session file exists |
| `TARGET_CHAT_ID` | `-1003898959289` | satta automation |
| `TARGET_CHAT_USERNAME` | _(empty)_ | Not used |
| `TARGET_INVITE_HASH` | _(empty)_ | Already a member |

---

## Known Issues / TODOs

- [ ] **`anomalies.csv` is empty** — header exists but no anomaly detection logic populates it
- [ ] **`INNINGS_UPDATE` type not handled** — parser doesn't have a dedicated type for it (falls to OTHER)
- [ ] **`history_replay.py` and `tg_listener.py` have duplicate code** — `extract_favorite_odds()` is duplicated in both files
- [ ] **No error handling for network failures** — scripts will crash on disconnect
- [ ] **`.env` contains real credentials** — should use `.env.example` template for repo

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `telethon` | 1.42.0 | Telegram client library |

Virtual env: `.venv` (Python 3.10)

---

## How to Run

### Live real-time monitoring (recommended)
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
