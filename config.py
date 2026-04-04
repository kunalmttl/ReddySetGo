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

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_NAME = os.environ.get("SESSION_NAME", "tg_session")

TARGET_CHAT_USERNAME = os.environ.get("TARGET_CHAT_USERNAME") or None
_TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID")
TARGET_CHAT_ID = int(_TARGET_CHAT_ID) if _TARGET_CHAT_ID else None

TARGET_INVITE_HASH = os.environ.get("TARGET_INVITE_HASH") or None
