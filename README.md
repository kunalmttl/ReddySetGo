# ReddySetGo

Telegram channel monitoring & history analysis tool for cricket/sports betting tips channels. Replays past messages or listens live in real-time, parses them using a custom message classifier, and prints a structured match-by-match event timeline to the console.

## Features

- **Live Monitoring** — Real-time listener for new channel messages
- **History Replay** — Offline analysis of past channel messages
- **Message Classification** — 12 message types (match setup, entry signals, cashout, win/loss posts, etc.)
- **Match State Tracking** — Tracks full match lifecycle from setup to close
- **Odds Extraction** — Parses favorite odds and team names from Hinglish text

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/kunalmttl/ReddySetGo.git
cd ReddySetGo
python -m venv .venv
.venv\Scripts\activate
pip install telethon

# 2. Configure
cp .env.example .env
# Edit .env with your Telegram API credentials and target channel

# 3. Run
.venv\Scripts\python.exe tg_listener.py   # Live monitoring
.venv\Scripts\python.exe history_replay.py  # Offline replay
```

## Configuration

Create a `.env` file:

```env
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=tg_session
TARGET_CHAT_ID=-100xxxxxxxxxx
TARGET_CHAT_USERNAME=
TARGET_INVITE_HASH=
```

Get API credentials from [my.telegram.org](https://my.telegram.org).

## How It Works

The parser classifies channel messages into types:

1. **MATCH_SETUP** — Channel posts a match prediction
2. **SIGNAL_FIRST_ENTRY** — Entry signal with odds (e.g., "90p TEAM KARO")
3. **SIGNAL_JACKPOT_ENTRY** — Second/jackpot entry signal
4. **SIGNAL_CASHOUT_BOOK** — Cashout signal (close match)
5. **WIN_POST** — Match won confirmation
6. **LOSS_POST** — Match lost
7. **SIGNAL_LOSS_CUT** — Cut losses signal

## License

Private project.
