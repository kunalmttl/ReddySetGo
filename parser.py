# parser.py
import re
from typing import Any, Dict, Optional

# ---------------------------
# Normalization helpers
# ---------------------------


def norm_team(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9 .&-]", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()


def _clean_upper_keep_basic(text: str) -> str:
    """
    Uppercase + remove emojis/symbols but keep letters, digits, space, dot, ampersand, hyphen, newlines.
    Good for VS/WINNER extraction.
    """
    t = (text or "").upper()
    t = re.sub(r"[^A-Z0-9 .&\n-]", " ", t)
    t = re.sub(r" {2,}", " ", t)
    t = re.sub(r"\n\s*\n", "\n", t)
    t = t.strip()
    return t


def _has_odds(text_u: str) -> bool:
    return bool(RE_ODDS_P.search(text_u) or RE_ODDS_HYPHEN.search(text_u))


# ---------------------------
# Match setup extraction
# ---------------------------

RE_VS_LINE = re.compile(
    r"\b([A-Z][A-Z0-9 ]{1,25}?)\s+VS\s+([A-Z][A-Z0-9 ]{1,25}?)\b", re.I
)
RE_WINNER_LINE = re.compile(
    r"(?:MATCH\s+WINNER|WINNER)\s*[-–]\s*([A-Z][A-Z0-9 ]{1,25}?)\s*$", re.I | re.M
)
RE_KE_LELO = re.compile(
    r"([A-Z0-9][A-Z0-9 .&-]{1,})\s+(?:KE\s+LELO|LIKH\s+KE\s+LELO)\b", re.I
)

# ---------------------------
# Odds
# ---------------------------

RE_ODDS_P = re.compile(r"\b(\d{1,3})p\b", re.I)
RE_ODDS_HYPHEN = re.compile(r"\b(\d{1,3})-\d+\b", re.I)

# Entry team+odds like: "80p DESERT", "90p UP W"
RE_ENTRY_TEAM_ODDS = re.compile(r"\b(\d{1,3}p)\b\s*([A-Z][A-Z0-9 .&-]{1,30})", re.I)

# ---------------------------
# Wait (avoid bare "WAIT")
# ---------------------------

RE_WAIT = re.compile(
    r"\bWAIT\s+(?:KARIYE|KARO|KARNA)\b|\bENTRY\s+MAI\s+DUNGA\b|\bENTRY\s+KA\s+WAIT\b",
    re.I,
)

# ---------------------------
# Signals / posts
# ---------------------------

# Strong CTA for entry (NOT just the word "ENTRY" because recaps contain it)
CTA_STRONG = [
    "KARO",
    "KARLO",
    "KARLENA",
    "LELO",
    "PLUS",
    "HOJAAO",
    "HOJAO",
    "HOJANA",
    "LIMIT",
    "KHEL",  # "KHEL LENA"
]

KW_FIRST = [
    "PEHLI ENTRY",
    "PEHLE ENTRY",
    "FIRST ENTRY",
]

# Jackpot disambiguation: accept future "JACKPOT BANEGA/BANEGI", reject "JACKPOT BANA HAI" recaps
RE_JACKPOT = re.compile(r"\bJACKPOT\b", re.I)
RE_JACKPOT_FUTURE = re.compile(r"\bJACKPOT\s+BAN(EGA|EGI)\b", re.I)

# Loss cut (accept LOSSCUT too)
RE_LOSSCUT = re.compile(r"\bLOSS\s*CUT\b", re.I)

# Cashout/bookset must be ACTIONABLE (avoid "BOOKSET KE LIYE READY REHNA")
RE_CASHOUT_ACTION = re.compile(
    r"\bCASH\s*OUT\b|\bCASHOUT\b|"
    r"\bBOOK\s*SET\s*(?:KARO|KARO SAB|BANAAO|BANAO|BANALO|DONE)\b|"
    r"\bBOOKSET\s*(?:KARO|BANAAO|BANAO|DONE)\b|"
    r"\bCUT\s*BOOK\b|"
    r"\bBOOK\s*BANAAO\b|\bBOOK\s*BANALO\b|\bBOOK\s*BANA\b",
    re.I,
)

# Win post (avoid plain "JEET" because it appears mid-match; accept common end phrases)
RE_WIN_POST = re.compile(
    r"JEET\s+MUBARAK|CHASE\s+MUBARAK|WON\s+THE\s+MATCH|"
    r"\bWIN\s+HUA\b|"
    r"\bWIN\b(?!.{0,10}NER)|"  # WIN but not WINNER nearby
    r"DONE\s+AND\s+DUSTED",
    re.I,
)

# Loss post (end-of-match loss)
RE_LOSS_POST = re.compile(r"\bAAJ\s+LOSS\b|\bFAIL\b|\bLOSS\b|HARD\s+LUCK|NUKSAAN", re.I)
RE_LOSS_NEG = re.compile(r"NO\s+LOSS|NO\s+PROFIT|NO\s+LOSS\s+NO\s+PROFIT", re.I)

# Cancel/abandon (helps close active match on called-off messages)
RE_CANCEL = re.compile(
    r"CALLED\s+OFF|ABANDONED|NO\s+RESULT|MATCH\s+NHI\s+HOGA|MATCH\s+NAHI\s+HOGA|"
    r"MATCH\s+STOP|MATCH\s+STOPS|MATCH\s+CANCEL",
    re.I,
)


def _has_strong_cta(text_u: str) -> bool:
    tu = text_u.upper()
    return any(k in tu for k in CTA_STRONG)


def parse_message(text: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Returns dict with at least:
      - type: str
      - raw: original text

    meta (optional):
      - is_reply: bool
      - reply_to_msg_id: int|None
      - msg_id: int|None
      - date_utc: str|None
    """
    meta = meta or {}
    raw = (text or "").strip()
    if not raw:
        return {"type": "EMPTY", "raw": ""}

    tu_raw = raw.upper()
    tu = _clean_upper_keep_basic(raw)

    # 0) Cancel/abandon
    if RE_CANCEL.search(tu_raw):
        return {"type": "MATCH_CANCELLED", "raw": raw}

    # 1) MATCH SETUP (supports "WINNER -" and "MATCH WINNER -")
    if " VS " in tu and "WINNER" in tu:
        # Process line by line for better extraction
        lines = [l.strip() for l in tu.splitlines() if l.strip()]
        
        vs_line = None
        winner_line = None
        
        for line in lines:
            if " VS " in line and vs_line is None:
                vs_line = line
            if "MATCH WINNER" in line and winner_line is None:
                winner_line = line
        
        # Fallback: search full text
        if vs_line is None:
            m_vs = RE_VS_LINE.search(tu)
            if m_vs:
                vs_line = m_vs.group(0)
        
        if winner_line is None:
            m_w = RE_WINNER_LINE.search(tu)
            if m_w:
                winner_line = m_w.group(0)
        
        if vs_line and winner_line:
            m_vs = RE_VS_LINE.search(vs_line)
            m_w = RE_WINNER_LINE.search(winner_line)
            
            if m_vs and m_w:
                a, b = norm_team(m_vs.group(1)), norm_team(m_vs.group(2))
                w_short = norm_team(m_w.group(1))

                # Prefer fuller winner from "X KE LELO / LIKH KE LELO"
                w_full = None
                k = RE_KE_LELO.search(tu)
                if k:
                    w_full = norm_team(k.group(1))

                return {
                    "type": "MATCH_SETUP",
                    "team_a": a,
                    "team_b": b,
                    "predicted_winner": w_full or w_short,
                    "predicted_winner_short": w_short,
                    "raw": raw,
                }

    # 2) WAIT
    if RE_WAIT.search(tu_raw):
        return {"type": "SIGNAL_WAIT", "raw": raw}

    # 3) Exit signals (loss-cut / cashout)
    if RE_LOSSCUT.search(tu_raw):
        return {"type": "SIGNAL_LOSS_CUT", "raw": raw}

    if RE_CASHOUT_ACTION.search(tu_raw):
        return {"type": "SIGNAL_CASHOUT_BOOK", "raw": raw}

    # 4) Win / loss posts
    # (Only these phrases, not plain "JEET")
    if RE_WIN_POST.search(tu_raw):
        return {"type": "WIN_POST", "raw": raw}

    if RE_LOSS_POST.search(tu_raw) and not RE_LOSS_NEG.search(tu_raw):
        return {
            "type": "LOSS_POST",
            "raw": raw,
            "is_reply": bool(meta.get("is_reply")),
            "reply_to_msg_id": meta.get("reply_to_msg_id"),
        }

    # 5) Entry signals
    has_first_kw = any(k in tu_raw for k in KW_FIRST)
    has_odds = _has_odds(tu_raw)
    has_cta = _has_strong_cta(tu_raw)

    has_jackpot = bool(RE_JACKPOT.search(tu_raw))
    is_jackpot_future = bool(RE_JACKPOT_FUTURE.search(tu_raw))

    # Jackpot entry rules:
    # - Accept if "JACKPOT BANEGA/BANEGI", OR (odds + strong CTA), OR first-entry keyword present.
    # - Reject jackpot recaps like "JACKPOT BANA HAI ..." (no future word, often no CTA).
    if has_jackpot and (is_jackpot_future or (has_odds and has_cta) or has_first_kw):
        return {"type": "SIGNAL_JACKPOT_ENTRY", "raw": raw, "combo_first": has_first_kw}

    # First entry keyword
    if has_first_kw:
        return {"type": "SIGNAL_FIRST_ENTRY", "raw": raw}

    # Inferred first entry (common in your logs): odds + KARO/PLUS/LIMIT etc
    if has_odds and has_cta:
        return {"type": "SIGNAL_FIRST_ENTRY", "raw": raw, "inferred": True}

    # 6) Odds-only update
    if has_odds:
        return {"type": "ODDS_UPDATE", "raw": raw}

    return {"type": "OTHER", "raw": raw}


def extract_entry_team_odds(text: str) -> Dict[str, Optional[str]]:
    """
    Best-effort extraction for entry messages:
      "80p DESERT" -> {"odds": "80p", "team": "DESERT"}
    """
    tu = _clean_upper_keep_basic(text or "")
    m = RE_ENTRY_TEAM_ODDS.search(tu)
    if not m:
        return {"odds": None, "team": None}
    odds = (m.group(1) or "").lower()
    team = norm_team(m.group(2) or "")
    return {"odds": odds, "team": team}
