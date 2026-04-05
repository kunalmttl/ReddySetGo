# state.py
from dataclasses import dataclass, field
from typing import Optional


def round_stake(amount: float) -> float:
    """Round to nearest 100, minimum 100"""
    return float(max(100, round(amount / 100) * 100))


@dataclass
class MatchState:
    # Match info
    match_no: int = 0
    league: str = ""
    team_a: str = ""
    team_b: str = ""
    predicted_winner: str = ""
    predicted_winner_short: str = ""

    # Stake plan
    balance_at_start: float = 0.0
    match_limit: float = 0.0
    first_entry_stake: float = 0.0
    jackpot_stake: float = 0.0

    # Execution tracking
    first_bet_placed: bool = False
    jackpot_bet_placed: bool = False
    first_entry_odds: Optional[float] = None
    jackpot_entry_odds: Optional[float] = None
    has_jackpot: bool = False

    active: bool = False

    def setup(self, match_no, league, team_a, team_b,
              predicted_winner, predicted_winner_short, balance: float):
        self.match_no = match_no
        self.league = league
        self.team_a = team_a
        self.team_b = team_b
        self.predicted_winner = predicted_winner
        self.predicted_winner_short = predicted_winner_short
        self.balance_at_start = balance
        self.match_limit = round_stake(balance * 0.05)
        self.first_entry_stake = round_stake(self.match_limit * 0.40)
        self.jackpot_stake = round_stake(self.match_limit * 0.60)
        self.first_bet_placed = False
        self.jackpot_bet_placed = False
        self.first_entry_odds = None
        self.jackpot_entry_odds = None
        self.has_jackpot = False
        self.active = True

    def close(self, reason: str = ""):
        print(f"[STATE] Match #{self.match_no} closed. Reason: {reason}")
        self.active = False

    def stake_summary(self) -> str:
        return (
            f"Balance=Rs.{self.balance_at_start:.0f} | Limit=Rs.{self.match_limit:.0f} "
            f"| FirstEntry=Rs.{self.first_entry_stake:.0f} | Jackpot=Rs.{self.jackpot_stake:.0f}"
        )
