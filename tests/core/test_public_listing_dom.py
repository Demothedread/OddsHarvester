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
