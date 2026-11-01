from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pytest

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.odds_portal_scraper import OddsPortalScraper
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

FIXTURE = Path(__file__).parents[1] / "fixtures" / "nfl_public_listing_20261101.html"
MATCH_PATHS = [
    "/american-football/h2h/atlanta-falcons-hClIiQIR/tampa-bay-buccaneers-40on8pjK/#j9Uxe71b",
    "/american-football/h2h/detroit-lions-boZWV3E7/minnesota-vikings-IsfjpsbD/#Ctb7daL5",
]


def test_listing_content_counter_uses_real_fixture_anchors():
    soup = BeautifulSoup(FIXTURE.read_text(), "lxml")
    assert not soup.select("div[class*='eventRow']")
    assert len(soup.select(OddsPortalSelectors.EVENT_LISTING_CONTENT_CSS)) == 2


@pytest.mark.asyncio
async def test_extract_real_public_listing_preserves_event_fragment():
    scraper = BaseScraper(MagicMock(), MagicMock(), MagicMock())
    page = AsyncMock()
    page.content.return_value = FIXTURE.read_text()
    assert sorted(await scraper.extract_match_links(page)) == [ODDSPORTAL_BASE_URL + p for p in MATCH_PATHS]


@pytest.mark.asyncio
async def test_public_listing_deduplicates_and_rejects_non_event_h2h_links():
    """Mutations exercise boundaries; they are not production data."""
    html = FIXTURE.read_text()
    html += html
    html += '<a class="group" href="/american-football/h2h/a/b/#not-an-event">H2H</a>'
    html += '<a class="group" href="https://example.invalid/american-football/h2h/a/b/#j9Uxe71b">External</a>'
    scraper = BaseScraper(MagicMock(), MagicMock(), MagicMock())
    page = AsyncMock()
    page.content.return_value = html
    assert sorted(await scraper.extract_match_links(page)) == [ODDSPORTAL_BASE_URL + p for p in MATCH_PATHS]


@pytest.mark.asyncio
async def test_real_format_dropdown_buttons(monkeypatch):
    """Offline browser uses captured DOM; JS only models the control's interaction."""
    monkeypatch.setattr("oddsharvester.core.base_scraper.ODDS_FORMAT_SELECTOR_TIMEOUT_MS", 200)
    monkeypatch.setattr("oddsharvester.core.base_scraper.ODDS_FORMAT_WAIT_MS", 0)
    scraper = BaseScraper(MagicMock(), MagicMock(), MagicMock())
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(FIXTURE.read_text())
            await page.evaluate("""() => {
                const group = document.querySelector('div.group');
                const button = group.querySelector(':scope > button');
                const menu = group.querySelector(':scope > div');
                button.querySelector('p').textContent = 'Money Line Odds';
                button.onclick = () => {
                    button.setAttribute('aria-expanded', 'true');
                    menu.setAttribute('aria-hidden', 'false');
                };
                for (const option of menu.querySelectorAll('button')) {
                    option.onclick = () => {
                        button.querySelector('p').textContent =
                            option.textContent.split('(')[0].trim();
                        button.setAttribute('aria-expanded', 'false');
                    };
                }
            }""")
            await scraper.set_odds_format(page)
            assert await page.locator("div.group > button > p").inner_text() == "Decimal Odds"
            assert await page.locator("div.group > button").get_attribute("aria-expanded") == "false"
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_prepare_dismisses_cookie_before_format():
    calls = []
    helper = MagicMock()

    async def dismiss(**_kwargs):
        calls.append("cookie")

    async def set_format(**_kwargs):
        calls.append("format")

    helper.dismiss_cookie_banner = dismiss
    scraper = OddsPortalScraper(MagicMock(), helper, MagicMock())
    scraper.set_odds_format = set_format
    await scraper._prepare_page_for_scraping(MagicMock())
    assert calls == ["cookie", "format"]


DATED_FIXTURE = Path(__file__).parents[1] / "fixtures" / "nfl_public_listing_dated_20261101.html"
FIRST_TODAY_PREGAME = (
    ODDSPORTAL_BASE_URL + "/american-football/h2h/los-angeles-chargers-K0iU7PXK/los-angeles-rams-z7hZioyR/#OMSpgoWA"
)
LAST_IN_216H_WINDOW = (
    ODDSPORTAL_BASE_URL + "/american-football/h2h/buffalo-bills-t2lcn4tk/minnesota-vikings-IsfjpsbD/#AZfrTiDs"
)


def test_full_season_listing_keeps_dom_order_and_skips_inplay_links():
    links = BaseScraper.parse_match_links(DATED_FIXTURE.read_text())
    assert len(links) == 156
    assert links[0] == FIRST_TODAY_PREGAME
    assert not [link for link in links if "/inplay-odds/" in link]


def test_days_ahead_bounds_full_season_listing_to_header_dates():
    html = DATED_FIXTURE.read_text()
    links = BaseScraper.parse_match_links(html, reference_date=date(2026, 11, 1), days_ahead=9)
    assert len(links) == 20
    assert links[0] == FIRST_TODAY_PREGAME
    assert links[-1] == LAST_IN_216H_WINDOW
    assert len(BaseScraper.parse_match_links(html, reference_date=date(2026, 11, 1), days_ahead=1)) == 4
    # "Today, 01 Nov" keeps its explicit date even when the clock has crossed midnight.
    assert BaseScraper.parse_match_links(html, reference_date=date(2026, 11, 2), days_ahead=1) == [
        ODDSPORTAL_BASE_URL + "/american-football/h2h/chicago-bears-2clovUM8/seattle-seahawks-f5h1oOee/#GdqKfb7F"
    ]


def test_days_ahead_excludes_undated_links_and_resolves_year_boundary():
    """Mutations exercise boundaries; they are not production data."""
    link = '<a class="group" href="/american-football/h2h/a-AAAAAAAA/b-BBBBBBBB/#{}">x</a>'
    html = (
        link.format("UNDATED1")
        + "<div>Yesterday, 31 Dec</div>"
        + link.format("PASTGAME")
        + "<div>Today, 01 Jan</div>"
        + link.format("NEWYEAR1")
    )
    assert BaseScraper.parse_match_links(html, reference_date=date(2027, 1, 1), days_ahead=2) == [
        ODDSPORTAL_BASE_URL + "/american-football/h2h/a-AAAAAAAA/b-BBBBBBBB/#NEWYEAR1"
    ]
    assert len(BaseScraper.parse_match_links(html)) == 3


def test_days_ahead_keeps_event_row_links_under_listing_date_headers():
    html = (
        "<div>Today, 01 Nov</div>"
        '<div class="eventRow">'
        '<a href="/american-football/h2h/team-a-AAAAAAAA/team-b-BBBBBBBB/#EVENTROW1">game</a>'
        "</div>"
    )

    assert BaseScraper.parse_match_links(
        html,
        reference_date=date(2026, 11, 1),
        days_ahead=1,
    ) == [ODDSPORTAL_BASE_URL + "/american-football/h2h/team-a-AAAAAAAA/team-b-BBBBBBBB/#EVENTROW1"]


@pytest.mark.asyncio
async def test_extract_match_links_uses_page_date_for_window():
    scraper = BaseScraper(MagicMock(), MagicMock(), MagicMock())
    page = AsyncMock()
    page.content.return_value = DATED_FIXTURE.read_text()
    page.evaluate.return_value = [2026, 11, 1]
    links = await scraper.extract_match_links(page, days_ahead=9)
    assert len(links) == 20
    page.evaluate.assert_awaited_once()
