# context.md — reddy_set_go

## Project Overview

**reddy_set_go** is a Telegram channel monitoring & automated betting tool for cricket/sports betting tips channels. It replays past messages or listens live in real-time, parses them using a custom message classifier, and automatically places bets on Reddybook via Playwright browser automation.

---

## Project Directory

```
D:\reddy_set_go\
├── history_replay.py        # Offline replay engine — iterates past messages
├── tg_listener.py           # Live Telegram listener (monitor only, no betting)
├── live_monitor.py          # Live Telegram listener + Reddybook auto-betting
├── bet_action.py            # Playwright browser automation (login, find match, place bet, cashout)
├── state.py                 # Match state tracker + stake calculator
├── config.py                # Env-based config loader (reads .env)
├── .env                     # Secrets & channel config (gitignored)
├── parser.py                # Message classifier + odds/team extractor
├── export_history.py        # One-time channel history exporter
├── channel_history_1y.jsonl # Exported 1-year channel history (offline backup)
├── matches.csv              # Processed match results from offline analysis
├── anomalies.csv            # Anomaly tracking (header only)
├── new_test.py              # Telegram session login test
├── .gitignore               # Protects .session, .env, __pycache__, .venv
└── context.md               # This file
```

---

## Entrypoints

```bash
# Live monitoring + automated betting (recommended)
.venv\Scripts\python.exe live_monitor.py

# Live Telegram listener only (no betting)
.venv\Scripts\python.exe tg_listener.py

# Offline history replay
.venv\Scripts\python.exe history_replay.py

# Test session auth
.venv\Scripts\python.exe new_test.py

# Export channel history (one-time)
.venv\Scripts\python.exe export_history.py
```

---

## Configuration (.env)

| Key                  | Type       | Description                                      |
|----------------------|------------|--------------------------------------------------|
| `API_ID`             | `int`      | Telegram API ID from my.telegram.org             |
| `API_HASH`           | `str`      | Telegram API hash                                |
| `SESSION_NAME`       | `str`      | Telethon session filename (e.g. `"tg2_session"`) |
| `TARGET_CHAT_ID`     | `int`      | Channel ID (e.g. `-1003898959289`)               |
| `TARGET_CHAT_USERNAME` | `str`    | (Optional) Channel @username                     |
| `TARGET_INVITE_HASH` | `str`      | (Optional) Invite link hash for auto-join        |
| `SITE_URL`           | `str`      | Betting site URL (e.g. `https://reddybook.live/home`) |
| `SITE_USERNAME`      | `str`      | Betting site username                            |
| `SITE_PASSWORD`      | `str`      | Betting site password                            |
| `HEADLESS`           | `bool`     | Browser visibility (`False` = visible window)    |
| `MATCH_LIMIT_PCT`    | `float`    | % of balance per match limit (default: `5`)      |
| `FIRST_ENTRY_PCT`    | `float`    | % of limit for first entry (default: `40`)       |
| `JACKPOT_PCT`        | `float`    | % of limit for jackpot entry (default: `60`)     |
| `ODDS_DRIFT_ABORT`   | `float`    | Abort bet if odds drift > this % (default: `15`) |

Config is loaded by `config.py` from `.env` — no hardcoded secrets.

---

## Target Channels

### Primary: satta automation
- **Channel ID**: `-1003898959289`
- **Invite link**: `https://t.me/+CK-lEZsWXOZmMjY1`
- **Channel type**: Cricket/sports betting tips
- **Leagues covered**: IPL, PSL, international matches
- **Language**: Hinglish (Hindi + English mixed)

### Previously tracked: D COMPANY TIPS DUBAI 💰
- **Channel ID**: `-1001165742515`
- **Invite link**: `https://t.me/joinchat/wo38LtQ34nk3M2Qx`

---

## parser.py — Message Types

`parse_message(text, meta={})` returns a dict with key `"type"` — one of:

| Type                    | Trigger Pattern                                              | Description                           |
|-------------------------|--------------------------------------------------------------|---------------------------------------|
| `MATCH_SETUP`           | `"LEAGUE - Nth TEAM_A VS TEAM B\nWINNER - TEAM"`            | Match prediction post, starts a match block |
| `SIGNAL_FIRST_ENTRY`    | `"90p TEAM KARO..."` / `"NNp TEAM entry signal"`            | First entry with odds                 |
| `SIGNAL_JACKPOT_ENTRY`  | `"NNp ... JACKPOT / PLUS KARO"`                              | Second/jackpot entry signal           |
| `SIGNAL_CASHOUT_BOOK`   | `"NNp TEAM CUT BOOK SET KARO"` / `"CASHOUT KARO"`           | Cashout or bookset signal             |
| `SIGNAL_LOSS_CUT`       | Loss cut / exit signal                                       | Cut losses signal                     |
| `WIN_POST`              | `"TEAM WIN"` / `"TEAM JEET MUBARAK"`                        | Match won confirmation                |
| `LOSS_POST`             | Loss / fail message                                         | Match lost (checked against reply_to) |
| `WAIT_SIGNAL`           | `"ENTRY KA WAIT KARIYE"`                                    | Wait for entry signal                 |
| `ODDS_UPDATE`           | Standalone odds line like `"65p DESERT"`                    | Odds change update                    |
| `MATCH_CANCELLED`       | `"CALLED OFF"` / `"ABANDONED"` / `"MATCH NHI HOGA"`         | Match cancelled/abandoned             |
| `OTHER`                 | Everything else (media, forwards, noise)                    | Ignored                               |
| `EMPTY`                 | No text content                                             | Ignored                               |

`extract_entry_team_odds(text)` → `{"odds": "90p", "team": "GUJARAT W"}`

---

## Match Lifecycle (with betting)

```
MATCH_SETUP        ← fetch balance, calc stake, find match on site
  └── SIGNAL_FIRST_ENTRY    ← place back bet (40% of match limit)
  └── SIGNAL_JACKPOT_ENTRY  ← place second back bet (60% of match limit)
  └── SIGNAL_CASHOUT_BOOK   ← click CASHOUT, accept pre-filled amount, close
  └── WIN_POST              ← log win, close match
  └── LOSS_POST             ← log loss, close match
  └── SIGNAL_LOSS_CUT       ← click LOSS CUT, accept pre-filled amount, close
  └── MATCH_CANCELLED       ← log cancel, close match
```

A new `MATCH_SETUP` before a close auto-closes the previous block as `UNCLOSED`.

---

## Stake Calculation

- **Match limit** = `balance * MATCH_LIMIT_PCT%` (default: 5%)
- **First entry** = `match_limit * FIRST_ENTRY_PCT%` (default: 40%)
- **Jackpot entry** = `match_limit * JACKPOT_PCT%` (default: 60%)
- **Single entry only** = first entry stake (40% used)
- Stake rounded to nearest ₹100, minimum ₹100

Example: Balance ₹10,000 → Limit ₹500 → First ₹200, Jackpot ₹300

---

## Odds Conversion

Channel sends Indian format: `46p` → Decimal: `1.46`
Formula: `decimal = 1 + p/100`

Drift check: abort if live odds drop >15% below signal odds.

---

## channel_history_1y.jsonl — Schema

Each line is a JSON object:

```json
{
  "chat_id": 1165742515,
  "msg_id": 17703,
  "date_utc": "2025-03-28T14:07:02",
  "raw_text": "INDIAN PREMIER LEAGUE 2025 - 8th BANGLORE VS CHENNAI...",
  "is_reply": false,
  "reply_to_msg_id": null,
  "is_forward": false,
  "has_media": false,
  "media_type": null,
  "views": 36088,
  "forwards": 5,
  "sender_id": -1001165742515
}
```

---

## Match Setup Message — Raw Format

```
INDIAN PREMIER LEAGUE 2025 - 8th BANGLORE VS CHENNAI
WINNER - BANGLORE
ROYAL CHALLENGERS BANGLORE KE LELO
1001 PAPER PE LIKH LO
1001 HOKE KHELO
1001
COMPANY - D BHAI
```

Key fields extracted:
- `team_a` = `BANGLORE`
- `team_b` = `CHENNAI`
- `predicted_winner` = `BANGLORE` (short) / `ROYAL CHALLENGERS BANGLORE` (full)

---

## Entry Signal — Raw Format

```
90p CHENNAI KARO SABHI LOG.. 1 LIMIT SE PLUS KARO
ABHI BANGLORE JEETEGA AAJ WALA MATCH
COMPANY D BHAI...
```

Extracted: `odds = "90p"`, `team = "CHENNAI"` (team to fade/lay)

---

## Dependencies

```
telethon==1.42.0
playwright==1.58.0
```

Install: `pip install telethon playwright && playwright install chromium`

Virtual env: `.venv` (activate before running)

---

## Notes

- The **bet side is always the predicted winner** — entry signal says `"90p CHENNAI KARO"` but we BACK Bangalore.
- Cashout/Loss Cut buttons open a pre-filled bet panel — amount is auto-calculated by site, we just click "PLACE BET".
- Bet placement retries indefinitely on "odds changed" errors, aborts only if odds drift >15%.
- Parser uses line-by-line processing for clean team name extraction (regex preserves newlines).
- `live_monitor.py` runs both Telethon listener and Playwright browser simultaneously.
- `history_replay.py` date range is configurable via `START_UTC` / `END_UTC` constants.
