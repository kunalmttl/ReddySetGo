# live_monitor.py
import asyncio
import re
from datetime import datetime, timezone

from telethon import TelegramClient, events

import config
from parser import parse_message, extract_entry_team_odds
from state import MatchState
from bet_action import BetAction

W = 62
HR  = "=" * W
SEP = "-" * W

def now() -> str:
    return datetime.now().strftime("%H:%M:%S")

def log(tag: str, msg: str):
    print(f"[{now()}] [{tag}] {msg}")

def print_match_header(state: MatchState):
    print("\n" + HR)
    print(f"  MATCH #{state.match_no}  |  {now()}")
    print(f"  {state.team_a}  vs  {state.team_b}")
    print(f"  WINNER  ->  {state.predicted_winner}")
    print(f"  STAKE   ->  {state.stake_summary()}")
    print(HR)

def print_event(tag: str, msg: str):
    print(f"  [{now()}] {tag:<10}  {msg}")


async def main():
    # -- Start Playwright browser ---------------------------------------
    bet = BetAction()
    await bet.start()

    # -- Start Telethon client ------------------------------------------
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start()

    me = await client.get_me()
    log("AUTH", f"Logged in as: {me.username or me.phone}")

    entity = await client.get_entity(config.TARGET_CHAT_ID)
    log("OK", f"Connected to: {entity.title} (id={entity.id})")

    print("\n" + HR)
    print("  TELEGRAM LIVE MONITOR  +  REDDYBOOK AUTOMATION")
    print(HR)

    state = MatchState()
    match_idx = 0

    @client.on(events.NewMessage(chats=config.TARGET_CHAT_ID))
    async def handler(event):
        nonlocal match_idx, state

        msg = event.message
        text = msg.message or ""
        meta = {
            "msg_id": msg.id,
            "date_utc": (msg.date.astimezone(timezone.utc).isoformat()
                         if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc).isoformat()),
            "is_reply": bool(msg.is_reply),
            "reply_to_msg_id": getattr(msg, "reply_to_msg_id", None),
        }

        parsed = parse_message(text, meta=meta)
        t = parsed.get("type", "OTHER")

        # -- MATCH SETUP ------------------------------------------------
        if t == "MATCH_SETUP":
            match_idx += 1

            # Fetch balance for stake calculation
            balance = await bet.get_balance()

            state.setup(
                match_no=match_idx,
                league=parsed.get("league", ""),
                team_a=parsed["team_a"],
                team_b=parsed["team_b"],
                predicted_winner=parsed["predicted_winner"],
                predicted_winner_short=parsed.get("predicted_winner_short", parsed["predicted_winner"]),
                balance=balance,
            )
            print_match_header(state)

            # Navigate browser to cricket page and find match
            found = await bet.find_and_open_match(state.team_a, state.team_b)
            if not found:
                print_event("WARN", f"Match not found on site - bets will be skipped")
            return

        # -- Ignore if no active match ----------------------------------
        if not state.active:
            return

        # -- FIRST ENTRY ------------------------------------------------
        if t == "SIGNAL_FIRST_ENTRY":
            info = extract_entry_team_odds(text)
            odds_raw = info.get("odds", "")
            team = info.get("team", state.predicted_winner)
            odds_val = _parse_float(odds_raw)

            print_event("ENTRY", f"odds={odds_raw}  team={team}  stake=Rs.{state.first_entry_stake:.0f}")

            state.first_entry_odds = odds_val
            success = await bet.place_back_bet(
                team=state.predicted_winner,
                signal_odds=odds_val,
                stake=state.first_entry_stake,
            )
            state.first_bet_placed = success
            if success:
                print_event("BET_OK", f"First entry placed")
            else:
                print_event("ABORT", f"First entry aborted (odds drifted >15%)")
            return

        # -- JACKPOT ENTRY ----------------------------------------------
        if t == "SIGNAL_JACKPOT_ENTRY":
            info = extract_entry_team_odds(text)
            odds_raw = info.get("odds", "")
            odds_val = _parse_float(odds_raw)

            state.has_jackpot = True
            print_event("JACKPOT", f"odds={odds_raw}  stake=Rs.{state.jackpot_stake:.0f}")

            state.jackpot_entry_odds = odds_val
            success = await bet.place_back_bet(
                team=state.predicted_winner,
                signal_odds=odds_val,
                stake=state.jackpot_stake,
            )
            state.jackpot_bet_placed = success
            if success:
                print_event("BET_OK", f"Jackpot entry placed")
            else:
                print_event("ABORT", f"Jackpot entry aborted (odds drifted >15%)")
            return

        # -- CASHOUT ----------------------------------------------------
        if t == "SIGNAL_CASHOUT_BOOK":
            print_event("CASHOUT", "Cashout signal received")
            await bet.cashout()
            state.close("CASHOUT")
            return

        # -- LOSS CUT ---------------------------------------------------
        if t == "SIGNAL_LOSS_CUT":
            print_event("LOSS_CUT", "Loss cut signal received")
            await bet.loss_cut()
            state.close("LOSS_CUT")
            return

        # -- WIN / LOSS -------------------------------------------------
        if t == "WIN_POST":
            print_event("WIN", "Match won")
            print(SEP)
            state.close("WIN")
            return

        if t == "LOSS_POST":
            print_event("LOSS", "Match lost")
            print(SEP)
            state.close("LOSS")
            return

        # -- CANCELLED --------------------------------------------------
        if t == "MATCH_CANCELLED":
            print_event("CANCEL", "Match cancelled")
            state.close("CANCELLED")
            return

    # Keep running
    log("LIVE", "Listening for signals... (Ctrl+C to stop)")
    await client.run_until_disconnected()
    await bet.stop()


def _parse_float(s: str) -> float:
    """Convert '46p' -> 1.46 decimal odds"""
    try:
        p = float(re.findall(r"[\d.]+", str(s).replace("p", ""))[0])
        return 1 + p / 100
    except:
        return 1.5  # safe fallback


if __name__ == "__main__":
    asyncio.run(main())
