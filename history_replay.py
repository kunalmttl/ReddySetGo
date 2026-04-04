import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from telethon import TelegramClient

import config
from parser import norm_team, parse_message

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = None

SEPARATOR = "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="

START_UTC = datetime(2026, 3, 28, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(
    2026, 4, 4, 23, 59, 59, tzinfo=timezone.utc
)  # IPL 2026 season

ASSUME_UNCLOSED_AS_LOSS = True
MAX_ENTRIES_PER_MATCH = 2


# ---------- time formatting ----------
def dt_str(dt: datetime) -> str:
    if IST:
        return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------- odds extraction (emoji-safe + stopwords) ----------
RE_P = re.compile(r"\b(\d{1,3})p\b", re.I)
RE_HYPHEN = re.compile(r"\b(\d{1,3})-\d+\b", re.I)

TEAM_STOPWORDS = {
    "KE",
    "KA",
    "KI",
    "UNDER",
    "UPAR",
    "SE",
    "ME",
    "MAIN",
    "MAI",
    "PE",
    "PAR",
    "BOOK",
    "BOOKSET",
    "BOOK-SET",
    "SET",
    "CASHOUT",
    "KARO",
    "KARLO",
    "KARLENA",
    "ENTRY",
    "LELO",
    "BANAO",
    "BANALO",
    "PLUS",
    "HOJAAO",
    "HOJAO",
    "FAV",
    "NONFAV",
    "OPPOSITE",
    "APNI",
    "TEAM",
}

BAD_PHRASE_RE = re.compile(
    r"(OPPOSITE SE APNI TEAM|LANKA SE APNI TEAM|SE APNI TEAM|APNI TEAM|OPPOSITE)",
    re.I,
)


def extract_favorite_odds(raw_text: str):
    """
    Returns (p:int, team:str) or None.
    Picks the lowest p found (strongest favorite).
    """
    if not raw_text:
        return None

    best = None  # (p, team)
    for line in raw_text.splitlines():
        l = line.strip()
        if not l:
            continue

        m = RE_P.search(l) or RE_HYPHEN.search(l)
        if not m:
            continue

        p = int(m.group(1))
        rest = l[m.end() :].strip()
        if not rest or BAD_PHRASE_RE.search(rest):
            continue

        rest_clean = re.sub(r"[^A-Za-z0-9 .&]", " ", rest)
        rest_clean = re.sub(r"\s+", " ", rest_clean).strip()

        toks = rest_clean.split() if rest_clean else []
        chosen = []
        for tok in toks:
            t = tok.upper()
            if t in TEAM_STOPWORDS:
                break
            if len(t) <= 1:
                continue
            chosen.append(tok)
            if len(chosen) >= 4:
                break

        team_guess = " ".join(chosen).strip()
        team = norm_team(team_guess) if team_guess else "UNKNOWN"

        if best is None or p < best[0]:
            best = (p, team)

    return best


# ---------- win/loss posts ----------
LOSS_NEGATIVE = ["NO LOSS", "NO PROFIT", "NO LOSS NO PROFIT", "LOSS CUT"]

LOSS_EXPLICIT_MATCH_RE = re.compile(
    r"(ISS\s+MATCH|IS\s+MATCH|MATCH\s+ME|MATCH\s+MAIN|MATCH\s+MAI).{0,60}\bLOSS\b|\bLOSS\b.{0,60}(ISS\s+MATCH|MATCH\s+ME|MATCH\s+MAIN|MATCH\s+MAI)",
    re.I,
)
LOSS_GENERIC_RE = re.compile(r"\bLOSS\b", re.I)

WIN_POST_RE = re.compile(
    r"(JEET\s+MUBARAK|JEETGAYI|JEET\s+GAYI|DONE\s+AND\s+DUSTED|\bJEET\b)",
    re.I,
)


def is_loss_post(raw_text: str) -> bool:
    tu = (raw_text or "").upper()
    if any(x in tu for x in LOSS_NEGATIVE):
        return False
    return bool(LOSS_GENERIC_RE.search(tu))


def is_explicit_match_loss(raw_text: str) -> bool:
    tu = (raw_text or "").upper()
    if any(x in tu for x in LOSS_NEGATIVE):
        return False
    return bool(LOSS_EXPLICIT_MATCH_RE.search(tu))


def is_win_post(raw_text: str) -> bool:
    return bool(WIN_POST_RE.search(raw_text or ""))


# ---------- state ----------
@dataclass
class MatchState:
    active: bool = False
    ignore_until_next_setup: bool = False

    team_a: str | None = None
    team_b: str | None = None
    predicted: str | None = None

    entries: int = 0  # <= MAX_ENTRIES_PER_MATCH

    def start(self, a: str, b: str, predicted: str):
        self.active = True
        self.ignore_until_next_setup = False
        self.team_a, self.team_b, self.predicted = a, b, predicted
        self.entries = 0

    def end(self):
        self.active = False
        self.ignore_until_next_setup = True
        self.team_a = self.team_b = self.predicted = None
        self.entries = 0


state = MatchState()

wins = 0
explicit_match_losses = 0
general_loss_posts = 0
unclosed_matches = 0
assumed_losses = 0
ignored = 0


def log(dt: datetime, label: str, details: str = ""):
    if details:
        print(f"[{dt_str(dt)}] {label}: {details}")
    else:
        print(f"[{dt_str(dt)}] {label}")


def end_due_to_unclosed(dt: datetime):
    global unclosed_matches, assumed_losses
    unclosed_matches += 1
    log(
        dt,
        "UNCLOSED",
        "Previous match ended without CASHOUT/LOSS CUT/WIN POST (before next MATCH_SETUP)",
    )
    if ASSUME_UNCLOSED_AS_LOSS:
        assumed_losses += 1


def handle(dt: datetime, raw_text: str, parsed: dict):
    global wins, explicit_match_losses, general_loss_posts, ignored

    # Loss posts
    if is_loss_post(raw_text):
        general_loss_posts += 1
        if state.active and is_explicit_match_loss(raw_text):
            explicit_match_losses += 1
            log(dt, "MATCH LOSS", "Explicit loss-post for this match")
            print(SEPARATOR)
            state.end()
        else:
            log(dt, "LOSS POST", "General")
        return

    t = parsed.get("type")

    # Start new match
    if t == "MATCH_SETUP":
        if state.active:
            end_due_to_unclosed(dt)
            print(SEPARATOR)
            state.end()
            state.ignore_until_next_setup = False

        state.start(parsed["team_a"], parsed["team_b"], parsed["predicted_winner"])
        print(SEPARATOR)
        log(dt, "MATCH", f"{state.team_a} vs {state.team_b}")
        log(dt, "WINNER", state.predicted)
        return

    # After end: ignore all until next match setup
    if state.ignore_until_next_setup and not state.active:
        ignored += 1
        return

    # Ignore noise or outside match
    if not state.active or t in ("EMPTY", "OTHER", "SIGNAL_WAIT", "ODDS_UPDATE"):
        ignored += 1
        return

    fav = extract_favorite_odds(raw_text)
    fav_str = f"{fav[0]}p {fav[1]}" if fav else "n/a"

    # Win post ends match
    if is_win_post(raw_text):
        wins += 1
        log(dt, "WIN POST (END)", f"favorite: {fav_str}")
        print(SEPARATOR)
        state.end()
        return

    # ENTRY logic (max 2)
    if t in ("SIGNAL_FIRST_ENTRY", "SIGNAL_JACKPOT_ENTRY"):
        if state.entries >= MAX_ENTRIES_PER_MATCH:
            ignored += 1
            return
        state.entries += 1
        label = "JACKPOT ENTRY" if t == "SIGNAL_JACKPOT_ENTRY" else "FIRST ENTRY"
        log(
            dt,
            f"{label} #{state.entries}",
            f"favorite: {fav_str} | bet: {state.predicted}",
        )
        return

    # End logic (cashout & loss-cut are both end)
    if t in ("SIGNAL_CASHOUT_BOOK", "SIGNAL_LOSS_CUT"):
        wins += 1
        log(dt, "CASHOUT", f"favorite: {fav_str} | end: {t}")
        print(SEPARATOR)
        state.end()
        return

    ignored += 1


async def resolve_target(client: TelegramClient):
    if config.TARGET_CHAT_ID is not None:
        return config.TARGET_CHAT_ID
    if config.TARGET_CHAT_USERNAME:
        return await client.get_entity(config.TARGET_CHAT_USERNAME)
    raise RuntimeError(
        "Set TARGET_CHAT_ID or TARGET_CHAT_USERNAME in config.py (recommended: TARGET_CHAT_ID)"
    )


async def main():
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start()
    target = await resolve_target(client)

    print(f"Replaying {START_UTC.date()} -> {END_UTC.date()} (oldest -> newest)")
    async for msg in client.iter_messages(target, reverse=True, offset_date=START_UTC):
        if msg.date < START_UTC:
            continue
        if msg.date > END_UTC:
            break
        raw = msg.raw_text or ""
        parsed = parse_message(raw)
        handle(msg.date, raw, parsed)

    print("\nDONE")
    print(f"Wins proxy (cashout/loss-cut/win-post): {wins}")
    print(f"Explicit match-loss posts: {explicit_match_losses}")
    print(f"General loss posts: {general_loss_posts}")
    print(f"Unclosed matches: {unclosed_matches}")
    print(f"Assumed losses (from unclosed): {assumed_losses}")
    print(f"Ignored: {ignored}")


if __name__ == "__main__":
    asyncio.run(main())
