# bet_action.py
import asyncio
import re
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

import config

W = 70
HR = "-" * W

def log(tag: str, msg: str):
    print(f"[{tag}] {msg}")


class BetAction:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=getattr(config, "HEADLESS", False),
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            viewport=None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        # Remove webdriver flag
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        self.page = await self.context.new_page()
        await self.login()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self):
        page = self.page
        login_url = "https://reddybook.live/home"
        log("LOGIN", f"Navigating to {login_url}")
        await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)

        # Fill credentials — try common selectors
        await page.locator(
            'input[type="text"], input[name="username"], input[placeholder*="Username" i], input[placeholder*="User" i], input[autocomplete="username"]'
        ).first.fill(config.SITE_USERNAME)

        await page.locator(
            'input[type="password"], input[name="password"], input[autocomplete="current-password"]'
        ).first.fill(config.SITE_PASSWORD)

        await page.locator(
            'button[type="submit"], button:has-text("Login"), button:has-text("Sign In"), button:has-text("Log In")'
        ).first.click()

        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        log("LOGIN", "Logged in successfully")

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    async def get_balance(self) -> float:
        page = self.page
        try:
            # BAL is shown top right
            for sel in [
                '[class*="balance"]',
                '[class*="bal"]',
                'text=BAL',
                '.header-bal',
            ]:
                els = page.locator(sel)
                if await els.count() > 0:
                    txt = await els.first.inner_text()
                    nums = re.findall(r"[\d]+\.?\d*", txt.replace(",", ""))
                    if nums:
                        bal = float(nums[-1])
                        log("BAL", f"Current balance: Rs.{bal:.0f}")
                        return bal
        except Exception as e:
            log("BAL", f"Could not read balance: {e}")
        return 0.0

    # ------------------------------------------------------------------
    # Match Finding
    # ------------------------------------------------------------------

    async def find_and_open_match(self, team_a: str, team_b: str) -> bool:
        page = self.page
        log("MATCH", f"Searching for {team_a} vs {team_b} on cricket page")
        await page.goto("https://reddybook.live/sports/4", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        keywords = _keywords(team_a) + _keywords(team_b)
        log("MATCH", f"Keywords: {keywords}")

        # Try rows/cells containing match names
        for sel in ["tr", ".event-row", '[class*="event"]', '[class*="match-row"]', "a"]:
            rows = await page.locator(sel).all()
            for row in rows:
                try:
                    txt = (await row.inner_text()).upper()
                    if sum(1 for kw in keywords if kw in txt) >= 2:
                        log("MATCH", f"Found: {txt[:80].strip()}")
                        await row.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2)
                        return True
                except:
                    continue

        log("MATCH", "Match not found on page")
        return False

    # ------------------------------------------------------------------
    # Place Back Bet (MATCH ODDS, blue column)
    # ------------------------------------------------------------------

    async def place_back_bet(
        self,
        team: str,
        signal_odds: float,
        stake: float,
    ) -> bool:
        """
        Click BACK (blue) odds for `team` in MATCH ODDS section.
        Retry indefinitely. Abort if live odds drift > ODDS_DRIFT_ABORT% from signal.
        """
        page = self.page
        abort_below = signal_odds * (1 - config.ODDS_DRIFT_ABORT / 100)
        log("BET", f"BACK {team} | signal_odds={signal_odds} | stake=Rs.{stake:.0f} | abort_below={abort_below:.2f}")

        attempt = 0
        while True:
            attempt += 1
            try:
                # Close any stale bet panel
                await self._cancel_panel()

                # Click best BACK odds for team
                clicked_odds = await self._click_back_odds_for_team(team)
                if clicked_odds is None:
                    log("BET", f"Attempt {attempt}: could not find odds, retrying in 1s...")
                    await asyncio.sleep(1)
                    continue

                # Drift check
                if clicked_odds < abort_below:
                    log("BET", f"ABORT: odds {clicked_odds} below drift threshold {abort_below:.2f}")
                    await self._cancel_panel()
                    return False

                # Enter stake
                await self._fill_stake(stake)

                # Click PLACE BET
                await page.locator('button:has-text("PLACE BET")').last.click()
                await asyncio.sleep(1.5)

                # Check result
                result = await self._read_result()
                if result == "success":
                    log("BET", f"Bet placed! odds={clicked_odds} stake=Rs.{stake:.0f} (attempt {attempt})")
                    return True
                elif result == "odds_changed":
                    log("BET", f"Odds changed notification, retrying... (attempt {attempt})")
                    await asyncio.sleep(0.3)
                else:
                    log("BET", f"Attempt {attempt}: unknown result, retrying...")
                    await asyncio.sleep(1)

            except Exception as e:
                log("BET", f"Attempt {attempt} error: {e}")
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Cashout
    # ------------------------------------------------------------------

    async def cashout(self) -> bool:
        """Click CASHOUT -> panel opens with pre-filled amount -> click PLACE BET"""
        page = self.page
        log("CASHOUT", "Clicking CASHOUT button...")

        while True:
            try:
                await self._cancel_panel()
                await page.locator('button:has-text("CASHOUT")').first.click()
                await asyncio.sleep(1)

                # Wait for place bet panel with pre-filled amount
                await page.wait_for_selector('button:has-text("PLACE BET")', timeout=5000)

                # DO NOT change stake — just click PLACE BET
                await page.locator('button:has-text("PLACE BET")').last.click()
                await asyncio.sleep(1.5)

                result = await self._read_result()
                if result == "odds_changed":
                    log("CASHOUT", "Odds changed, retrying cashout...")
                    await asyncio.sleep(0.3)
                    continue
                else:
                    log("CASHOUT", "Cashout placed!")
                    return True

            except Exception as e:
                log("CASHOUT", f"Error: {e}, retrying...")
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Loss Cut
    # ------------------------------------------------------------------

    async def loss_cut(self) -> bool:
        """Click LOSS CUT -> panel -> PLACE BET (same flow as cashout)"""
        page = self.page
        log("LOSSCUT", "Clicking LOSS CUT button...")

        while True:
            try:
                await self._cancel_panel()
                await page.locator('button:has-text("LOSS CUT")').first.click()
                await asyncio.sleep(1)

                await page.wait_for_selector('button:has-text("PLACE BET")', timeout=5000)
                await page.locator('button:has-text("PLACE BET")').last.click()
                await asyncio.sleep(1.5)

                result = await self._read_result()
                if result == "odds_changed":
                    log("LOSSCUT", "Odds changed, retrying...")
                    await asyncio.sleep(0.3)
                    continue
                else:
                    log("LOSSCUT", "Loss cut placed!")
                    return True

            except Exception as e:
                log("LOSSCUT", f"Error: {e}, retrying...")
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _click_back_odds_for_team(self, team: str) -> Optional[float]:
        """
        Find team row in MATCH ODDS section, click the best BACK (blue) button.
        Returns the odds value clicked, or None if not found.
        """
        page = self.page
        kws = _keywords(team)

        # Strategy: find all rows, match by team name keyword,
        # then find blue/back buttons in that row
        for row_sel in ["tr", '[class*="runner"]', '[class*="selection"]', ".match-row"]:
            rows = await page.locator(row_sel).all()
            for row in rows:
                try:
                    row_text = (await row.inner_text()).upper()
                    if not any(kw in row_text for kw in kws):
                        continue

                    # Look for BACK buttons (blue cells) — 3 per row
                    # MATCH ODDS layout: ... BACK(3 cols) LAY(3 cols)
                    # The 3 BACK buttons are in columns 4,5,6 of the odds table
                    # Best back = highest decimal value = rightmost in back group
                    for back_sel in [
                        '[class*="back"]',
                        'td.back',
                        '[class*="blue"]',
                        "td:nth-child(4)",
                        "td:nth-child(5)",
                        "td:nth-child(6)",
                    ]:
                        btns = await row.locator(back_sel).all()
                        if not btns:
                            continue

                        # Pick button with highest odds value
                        best_btn = None
                        best_val = 0.0
                        for btn in btns:
                            txt = (await btn.inner_text()).strip().split("\n")[0]
                            val = _parse_decimal(txt)
                            if val > best_val:
                                best_val = val
                                best_btn = btn

                        if best_btn and best_val > 1.0:
                            await best_btn.click()
                            await asyncio.sleep(0.5)
                            return best_val

                except Exception:
                    continue
        return None

    async def _fill_stake(self, stake: float):
        page = self.page
        await page.wait_for_selector(
            '.place-bet, [class*="place-bet"], [class*="placeBet"], [class*="betSlip"]',
            timeout=5000,
        )
        # Two inputs at top of panel: [odds_box] [stake_box]
        # Stake is the RIGHT box (index 1)
        inputs = await page.locator(
            'input[type="number"], input[type="text"][class*="stake"], .stake-input'
        ).all()

        target = inputs[1] if len(inputs) >= 2 else (inputs[0] if inputs else None)
        if target:
            await target.triple_click()
            await target.fill(str(int(stake)))
            await asyncio.sleep(0.3)
        else:
            # Fallback: click EDIT STAKE then type
            edit = page.locator('button:has-text("EDIT STAKE")')
            if await edit.count() > 0:
                await edit.first.click()
                await asyncio.sleep(0.3)
                await page.keyboard.type(str(int(stake)))

    async def _cancel_panel(self):
        try:
            cancel = self.page.locator('button:has-text("CANCEL")')
            if await cancel.count() > 0:
                await cancel.first.click()
                await asyncio.sleep(0.3)
        except:
            pass

    async def _read_result(self) -> str:
        """Returns 'success', 'odds_changed', or 'unknown'"""
        page = self.page
        try:
            # Check success toast
            for sel in [
                ':has-text("Bet Placed")',
                ':has-text("bet placed")',
                '[class*="success"]',
                '[class*="toast"][class*="green"]',
            ]:
                if await page.locator(sel).count() > 0:
                    return "success"

            # Check odds changed
            for sel in [
                ':has-text("Odds Changed")',
                ':has-text("odds changed")',
                ':has-text("Price Changed")',
                '[class*="odds-changed"]',
            ]:
                if await page.locator(sel).count() > 0:
                    return "odds_changed"

            # If place bet panel disappeared -> success
            panel = page.locator('button:has-text("PLACE BET")')
            if await panel.count() == 0:
                return "success"

        except:
            pass
        return "unknown"


# ------------------------------------------------------------------
# Utils
# ------------------------------------------------------------------

def _keywords(team: str) -> list:
    """Extract uppercase keywords (>=4 chars) from team name for fuzzy matching"""
    words = re.sub(r"[^A-Za-z\s]", "", team).upper().split()
    kws = [w for w in words if len(w) >= 4]
    return kws if kws else [team.upper()]


def _parse_decimal(s: str) -> float:
    s = s.strip().replace(",", "").split()[0]
    try:
        return float(re.findall(r"[\d.]+", s)[0])
    except:
        return 0.0
