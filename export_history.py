import asyncio
import json
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient

import config

OUT_FILE = "channel_history_1y.jsonl"
DAYS_BACK = 365


def safe(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def to_iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


async def resolve_target(client: TelegramClient):
    if config.TARGET_CHAT_ID is not None:
        return config.TARGET_CHAT_ID
    if config.TARGET_CHAT_USERNAME:
        return await client.get_entity(config.TARGET_CHAT_USERNAME)
    raise RuntimeError("Set TARGET_CHAT_ID or TARGET_CHAT_USERNAME in config.py")


async def main():
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start()

    target = await resolve_target(client)

    start_utc = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    count = 0
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        async for msg in client.iter_messages(
            target, reverse=True, offset_date=start_utc
        ):
            # reverse=True => oldest->newest; offset_date meaning reverses too [web:119]
            if msg.date and msg.date < start_utc:
                continue

            # Some fields can be None depending on message type
            row = {
                "chat_id": safe(
                    getattr(msg.peer_id, "channel_id", None)
                    or getattr(msg.peer_id, "chat_id", None)
                    or getattr(msg.peer_id, "user_id", None)
                ),
                "msg_id": msg.id,
                "date_utc": to_iso(msg.date),
                "raw_text": msg.raw_text or "",
                "is_reply": bool(msg.reply_to),
                "reply_to_msg_id": getattr(
                    getattr(msg, "reply_to", None), "reply_to_msg_id", None
                ),
                "is_forward": bool(msg.fwd_from),
                "forward_from": safe(msg.fwd_from.to_dict()) if msg.fwd_from else None,
                "has_media": bool(msg.media),
                "media_type": type(msg.media).__name__ if msg.media else None,
                "grouped_id": getattr(
                    msg, "grouped_id", None
                ),  # albums / grouped media
                "views": getattr(msg, "views", None),
                "forwards": getattr(msg, "forwards", None),
                "edit_date_utc": to_iso(getattr(msg, "edit_date", None)),
                "post_author": getattr(msg, "post_author", None),
                "sender_id": getattr(msg, "sender_id", None),
            }

            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
            if count % 1000 == 0:
                print(f"Exported {count} messages...")

    print(f"Done. Exported {count} messages to {OUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
