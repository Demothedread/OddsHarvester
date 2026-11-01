from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import async_playwright
import pytest

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.browser_helper import BrowserHelper
from oddsharvester.core.market_extraction.navigation_manager import NavigationManager
from oddsharvester.core.market_extraction.odds_parser import OddsParser
from oddsharvester.utils.period_constants import AmericanFootballPeriod

FIXTURE = Path(__file__).parents[1] / "fixtures" / "nfl_public_match_20261101.html"


@pytest.mark.asyncio
async def test_real_sports_event_identity_uses_timezone_and_keeps_fragment():
    page = AsyncMock()
    page.content.return_value = FIXTURE.read_text()
    scraper = BaseScraper(MagicMock(), MagicMock(), MagicMock())
    link = "https://www.oddsportal.com/american-football/h2h/atlanta-falcons-hClIiQIR/tampa-bay-buccaneers-40on8pjK/#j9Uxe71b"
    details = await scraper._extract_match_details_event_header(page, link)
    assert details is not None
    assert details["match_date"] == "2026-11-01 18:00:00 UTC"
    assert details["match_link"] == link
    assert details["home_team"] == "Tampa Bay Buccaneers"
    assert details["away_team"] == "Atlanta Falcons"
    assert details["league_name"] == "NFL"
    assert details["venue"] == "Raymond James Stadium"
    assert details["home_score"] is None


def test_real_table_odds_preserve_labels_not_handicap_or_payout():
    rows = OddsParser().parse_market_odds(FIXTURE.read_text(), "FullTime", ["1", "2"])
    assert rows == [
        {"1": "1.75", "2": "2.13", "bookmaker_name": "bet365.us", "period": "FullTime"},
        {"1": None, "2": None, "is_suspended": True, "bookmaker_name": "BetMGM.us", "period": "FullTime"},
    ]
    totals = OddsParser().parse_market_odds(FIXTURE.read_text(), "FullTime", ["odds_over", "odds_under"], "BetMGM.us")
    assert totals == [
        {
            "odds_over": None,
            "odds_under": None,
            "is_suspended": True,
            "bookmaker_name": "BetMGM.us",
            "period": "FullTime",
        }
    ]


def test_public_suspended_odds_are_not_published_as_active_values():
    html = FIXTURE.read_text().replace(
        'class="font-main text-xs underline"', 'class="font-main text-xs line-through cursor-pointer"'
    )
    rows = OddsParser().parse_market_odds(html, "FullTime", ["1", "2"])
    assert len(rows) == 2
    assert all(row["1"] is None and row["2"] is None and row["is_suspended"] for row in rows)


def test_nested_expansion_wrapper_does_not_duplicate_bookmaker():
    html = FIXTURE.read_text()
    wrapped = '<table><tbody><tr><td colspan="5">' + html + "</td></tr></tbody></table>"
    assert OddsParser().parse_market_odds(wrapped, "FullTime", ["1", "2"]) == OddsParser().parse_market_odds(
        html, "FullTime", ["1", "2"]
    )


@pytest.mark.asyncio
async def test_public_period_button_selected_and_verified():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(FIXTURE.read_text())
            assert await BrowserHelper().ensure_period_selected(page, AmericanFootballPeriod.FULL_INCLUDING_OT)
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_real_tab_buttons_verify_selected_market_not_page_text(monkeypatch):
    monkeypatch.setattr("oddsharvester.core.browser_helper.TAB_SWITCH_WAIT_MS", 0)
    monkeypatch.setattr("oddsharvester.core.market_extraction.navigation_manager.MARKET_SWITCH_WAIT_TIME_MS", 0)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(FIXTURE.read_text())
            await page.evaluate("""() => {
                for (const button of document.querySelectorAll('li.tab-item > button')) {
                    button.onclick = () => {
                        document.querySelector('.active-item-feed').classList.remove('active-item-feed');
                        button.parentElement.classList.add('active-item-feed');
                    };
                }
            }""")
            helper = BrowserHelper()
            # All names exist on the page; only one is actually selected.
            assert not await helper._verify_tab_is_active(page, "Asian Handicap")
            assert await helper.navigate_to_market_tab(page, "Asian Handicap", timeout=100)
            assert await NavigationManager(helper).wait_for_market_switch(page, "Asian Handicap", max_attempts=1)
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_real_submarket_span_selects_exact_row_and_closes():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(FIXTURE.read_text())
            await page.evaluate("""() => {
                for (const row of document.querySelectorAll('tr.cursor-pointer')) {
                    row.onclick = () => row.dataset.clicks = String(Number(row.dataset.clicks || 0) + 1);
                }
            }""")
            navigation = NavigationManager(BrowserHelper())
            assert await navigation.select_specific_market(page, "Asian Handicap -3.5")
            assert await navigation.close_specific_market(page, "Asian Handicap -3.5")
            assert await navigation.select_specific_market(page, "Over/Under +23.5")
            assert await page.locator("tr.cursor-pointer").first.get_attribute("data-clicks") == "2"
            assert await page.locator("tr.cursor-pointer").last.get_attribute("data-clicks") == "1"
        finally:
            await browser.close()
