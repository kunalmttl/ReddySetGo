# tg_listener.py — Live Telegram Channel Monitor
import asyncio
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.functions.messages import ImportChatInviteRequest

import config
from parser import norm_team, parse_message

sys.stdout.reconfigure(encoding='utf-8')

SEPARATOR = "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="

# -------- Odds extraction (emoji-safe) --------
RE_P = re.compile(r"\b(\d{1,3})p\b", re.I)
RE_HYPHEN = re.compile(r"\b(\d{1,3})-\d+\b", re.I)

BAD_PHRASE_RE = re.compile(
    r"(OPPOSITE SE APNI TEAM|LANKA SE APNI TEAM|SE APNI TEAM|APNI TEAM|OPPOSITE)",
    re.I,
)


def ts(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def extract_favorite_odds(raw_text: str):
    if not raw_text:
        return None
    best = None
    for line in raw_text.splitlines():
        l = line.strip()
        if not l:
            continue
        m = RE_P.search(l) or RE_HYPHEN.search(l)
        if not m:
            continue
        p = int(m.group(1))
        rest = l[m.end():].strip()
        if BAD_PHRASE_RE.search(rest):
            continue
        rest_clean = re.sub(r"[^A-Za-z0-9 .&]", " ", rest)
        rest_clean = re.sub(r"\s+", " ", rest_clean).strip()
        if not rest_clean:
            continue
        words = rest_clean.split()
        team_guess = " ".join(words[:4])
        team = norm_team(team_guess)
        if len(team) < 3:
            continue
        if BAD_PHRASE_RE.search(team):
            continue
        if best is None or p < best[0]:
            best = (p, team)
    return best


# -------- State machine --------
@dataclass
class MatchState:
    active: bool = False
    team_a: str | None = None
    team_b: str | None = None
    predicted: str | None = None
    first_count: int = 0
    jackpot_done: bool = False
    first1_fav_p: int | None = None
    first1_fav_team: str | None = None

    def start(self, a: str, b: str, predicted: str):
        self.active = True
        self.team_a, self.team_b, self.predicted = a, b, predicted
        self.first_count = 0
        self.jackpot_done = False
        self.first1_fav_p = None
        self.first1_fav_team = None

    def end(self):
        self.active = False
        self.team_a = self.team_b = self.predicted = None
        self.first_count = 0
        self.jackpot_done = False
        self.first1_fav_p = None
        self.first1_fav_team = None


state = MatchState()
ignored = 0
msg_count = 0
recent_ids = deque(maxlen=500)


def print_event(dt: datetime, label: str, details: str = ""):
    if details:
        print(f"  [{ts(dt)}] {label}: {details}")
    else:
        print(f"  [{ts(dt)}] {label}")


def handle_parsed(dt: datetime, msg_id: int, parsed: dict, raw_text: str):
    global ignored

    if msg_id in recent_ids:
        return
    recent_ids.append(msg_id)

    t = parsed.get("type")

    # Log noise at low level
    if t in ("EMPTY", "OTHER", "SIGNAL_WAIT", "ODDS_UPDATE"):
        ignored += 1
        return

    fav = extract_favorite_odds(raw_text)
    fav_str = f"{fav[0]}p {fav[1]}" if fav else "n/a"

    if t == "MATCH_SETUP":
        if state.active:
            print(SEPARATOR)
            print_event(dt, "UNCLOSED", "Previous match auto-closed")
            state.end()
        state.start(parsed["team_a"], parsed["team_b"], parsed["predicted_winner"])
        print(SEPARATOR)
        print_event(dt, "MATCH", f"{state.team_a} vs {state.team_b}")
        print_event(dt, "WINNER", state.predicted)
        return

    if not state.active:
        ignored += 1
        return

    if t == "SIGNAL_FIRST_ENTRY":
        if state.first_count == 0:
            state.first_count = 1
            if fav:
                state.first1_fav_p, state.first1_fav_team = fav[0], fav[1]
            print_event(dt, "FIRST ENTRY #1", f"favorite: {fav_str} | bet: {state.predicted}")
            return
        if state.first_count == 1:
            if fav and state.first1_fav_p and fav[0] > state.first1_fav_p:
                state.first_count = 2
                print_event(dt, "FIRST ENTRY #2", f"favorite: {fav_str} | bet: {state.predicted}")
                return
            ignored += 1
            return
        ignored += 1
        return

    if t == "SIGNAL_JACKPOT_ENTRY":
        if state.first_count < 1:
            ignored += 1
            return
        if state.jackpot_done:
            ignored += 1
            return
        state.jackpot_done = True
        print_event(dt, "JACKPOT ENTRY", f"favorite: {fav_str} | bet: {state.predicted}")
        return

    if t in ("SIGNAL_CASHOUT_BOOK", "SIGNAL_LOSS_CUT"):
        note = "action: CASHOUT" if t == "SIGNAL_CASHOUT_BOOK" else "action: LOSS_CUT"
        if state.first_count < 1:
            note += " (no entry seen)"
        print_event(dt, "CASHOUT/LOSS_CUT", f"favorite: {fav_str} | {note}")
        print(SEPARATOR)
        state.end()
        return

    if t == "WIN_POST":
        print_event(dt, "WIN POST", f"favorite: {fav_str}")
        print(SEPARATOR)
        state.end()
        return

    if t == "LOSS_POST":
        print_event(dt, "LOSS POST", raw_text[:80])
        return

    if t == "MATCH_CANCELLED":
        print_event(dt, "CANCELLED", raw_text[:80])
        print(SEPARATOR)
        state.end()
        return

    ignored += 1


async def resolve_target(client: TelegramClient):
    # Try invite hash first
    if config.TARGET_INVITE_HASH:
        print(f"[JOIN] Trying invite hash: {config.TARGET_INVITE_HASH}")
        try:
            await client(ImportChatInviteRequest(config.TARGET_INVITE_HASH))
            print("[JOIN] Successfully joined channel")
        except Exception as e:
            err = str(e)
            if "already a participant" in err:
                print("[JOIN] Already a member of this channel")
            else:
                print(f"[JOIN] Invite failed: {err}")

    # Resolve by ID
    if config.TARGET_CHAT_ID is not None:
        try:
            entity = await client.get_entity(config.TARGET_CHAT_ID)
            print(f"[OK] Connected to: {entity.title} (id={entity.id})")
            return entity
        except Exception as e:
            print(f"[ERR] Could not resolve channel by ID: {e}")

    # Resolve by username
    if config.TARGET_CHAT_USERNAME:
        try:
            entity = await client.get_entity(config.TARGET_CHAT_USERNAME)
            print(f"[OK] Connected to: {entity.title} (id={entity.id})")
            return entity
        except Exception as e:
            print(f"[ERR] Could not resolve channel by username: {e}")

    return None


async def main():
    global msg_count

    print("=" * 60)
    print("  TELEGRAM CHANNEL LIVE MONITOR")
    print("=" * 60)

    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"[AUTH] Logged in as: @{me.username} ({me.phone})")
    print()

    target = await resolve_target(client)
    if target is None:
        print("[FATAL] Could not resolve target channel. Exiting.")
        await client.disconnect()
        return

    @client.on(events.NewMessage(chats=target))
    async def handler(event):
        global msg_count
        msg_count += 1
        raw_text = event.raw_text or ""
        msg_preview = raw_text[:100].replace('\n', ' ') if raw_text else "(no text / media only)"
        print(f"\n[MSG #{msg_count}] id={event.id} | {ts(event.date)} | {msg_preview}")

        parsed = parse_message(raw_text)
        ptype = parsed.get("type", "UNKNOWN")
        print(f"  -> PARSED AS: {ptype}")

        handle_parsed(event.date, event.id, parsed, raw_text)

    print()
    print("[LISTENING] Waiting for new messages... (Ctrl+C to stop)")
    print("-" * 60)

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
