# context.md — reddy_set_go

## Project Overview

**reddy_set_go** is a Telegram channel monitoring & history analysis tool for cricket/sports betting tips channels. It replays past messages or listens live in real-time, parses them using a custom message classifier, and prints a structured match-by-match event timeline to the console.

---

## Project Directory

```
D:\reddy_set_go\
├── history_replay.py        # Offline replay engine — iterates past messages
├── tg_listener.py           # Live real-time listener — monitors new messages
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
# Live real-time monitoring (recommended)
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

## Match Lifecycle

```
MATCH_SETUP        ← opens a match block, prints header
  └── SIGNAL_FIRST_ENTRY    ← printed as [FIRST ENTRY #1]
  └── SIGNAL_FIRST_ENTRY    ← printed as [FIRST ENTRY #2] (if odds improved)
  └── SIGNAL_JACKPOT_ENTRY  ← printed as [JACKPOT ENTRY]
  └── SIGNAL_CASHOUT_BOOK   ← printed as [CASHOUT], closes block
  └── WIN_POST              ← printed as [WIN POST], closes block
  └── LOSS_POST             ← printed as [LOSS POST]
  └── SIGNAL_LOSS_CUT       ← printed as [LOSS_CUT], closes block
  └── MATCH_CANCELLED       ← printed as [CANCELLED], closes block
```

A new `MATCH_SETUP` before a close auto-closes the previous block as `UNCLOSED`.

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
```

Install: `pip install telethon`

Virtual env: `.venv` (activate before running)

---

## Notes

- The **bet side is always the opposing team** — entry signal says `"90p CHENNAI KARO"` but the predicted winner is `BANGLORE`, meaning: lay Chennai / back Bangalore.
- Cashout signals (`"NNp TEAM BOOKSET KARO"`) close the match early — profit already locked.
- Parser uses line-by-line processing for clean team name extraction (regex preserves newlines).
- `tg_listener.py` logs every message with timestamp, ID, parsed type, and action taken.
- `history_replay.py` date range is configurable via `START_UTC` / `END_UTC` constants.
