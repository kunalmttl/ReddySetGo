import os
from pathlib import Path

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# -- Telegram --
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_NAME = os.environ.get("SESSION_NAME", "tg_session")

TARGET_CHAT_USERNAME = os.environ.get("TARGET_CHAT_USERNAME") or None
_TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID")
TARGET_CHAT_ID = int(_TARGET_CHAT_ID) if _TARGET_CHAT_ID else None
TARGET_INVITE_HASH = os.environ.get("TARGET_INVITE_HASH") or None

# -- Reddybook site --
SITE_URL = os.environ.get("SITE_URL", "https://reddybook.club/home")
SITE_USERNAME = os.environ.get("SITE_USERNAME", "")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "")
HEADLESS = os.environ.get("HEADLESS", "False").lower() == "true"

# -- Risk management --
MATCH_LIMIT_PCT = float(os.environ.get("MATCH_LIMIT_PCT", "5"))
FIRST_ENTRY_PCT = float(os.environ.get("FIRST_ENTRY_PCT", "40"))
JACKPOT_PCT = float(os.environ.get("JACKPOT_PCT", "60"))
ODDS_DRIFT_ABORT = float(os.environ.get("ODDS_DRIFT_ABORT", "15"))
