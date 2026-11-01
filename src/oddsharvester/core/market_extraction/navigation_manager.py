import logging

from playwright.async_api import Page

from oddsharvester.core.browser_helper import BrowserHelper
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import DEFAULT_MARKET_TIMEOUT_MS, MARKET_SWITCH_WAIT_TIME_MS, SCROLL_PAUSE_TIME_MS


class NavigationManager:
    """Handles browser navigation for market extraction."""

    def __init__(self, browser_helper: BrowserHelper):
        """Initialize NavigationManager."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.browser_helper = browser_helper

    async def navigate_to_market_tab(self, page: Page, market_tab_name: str) -> bool:
        """Navigate to a specific market tab."""
        return await self.browser_helper.navigate_to_market_tab(
            page=page, market_tab_name=market_tab_name, timeout=DEFAULT_MARKET_TIMEOUT_MS
        )

    async def wait_for_market_switch(self, page: Page, market_name: str, max_attempts: int = 3) -> bool:
        """
        Wait for the market switch to complete and verify the correct market is active.

        Args:
            page (Page): The Playwright page instance.
            market_name (str): The name of the market that should be active.
            max_attempts (int): Maximum number of verification attempts.

        Returns:
            bool: True if the market switch is confirmed, False otherwise.
        """
        self.logger.info(f"Waiting for market switch to complete for: {market_name}")

        for attempt in range(max_attempts):
            try:
                # Wait for the market switch animation to complete
                await page.wait_for_timeout(MARKET_SWITCH_WAIT_TIME_MS)

                public_tabs = await page.query_selector_all(OddsPortalSelectors.PUBLIC_MARKET_TAB_CSS)
                if public_tabs:
                    active_tab = await page.query_selector(OddsPortalSelectors.PUBLIC_ACTIVE_MARKET_CSS)
                    if active_tab and (await active_tab.text_content()).strip().casefold() == market_name.casefold():
                        return True
                    continue

                # Check if the market tab is active
                active_tab = await page.query_selector("li.active, li[class*='active'], .active")
                if active_tab:
                    tab_text = await active_tab.text_content()
                    if tab_text and market_name.lower() in tab_text.lower():
                        self.logger.info(f"Market switch confirmed: {market_name} is active")
                        return True

            except Exception as e:
                self.logger.warning(f"Market switch verification attempt {attempt + 1} failed: {e}")

        self.logger.warning(f"Market switch verification failed after {max_attempts} attempts")
        return False

    async def select_specific_market(self, page: Page, specific_market: str) -> bool:
        """Select a specific submarket within the main market."""
        if await page.query_selector_all(OddsPortalSelectors.PUBLIC_SUBMARKET_CSS):
            return await self._click_public_submarket(page, specific_market)
        return await self.browser_helper.scroll_until_visible_and_click_parent(
            page=page,
            selector=OddsPortalSelectors.SUB_MARKET_SELECTOR,
            text=specific_market,
        )

    async def close_specific_market(self, page: Page, specific_market: str) -> bool:
        """Close a specific submarket after scraping."""
        self.logger.info(f"Closing sub-market: {specific_market}")
        if await page.query_selector_all(OddsPortalSelectors.PUBLIC_SUBMARKET_CSS):
            return await self._click_public_submarket(page, specific_market)
        return await self.browser_helper.scroll_until_visible_and_click_parent(
            page=page,
            selector=OddsPortalSelectors.SUB_MARKET_SELECTOR,
            text=specific_market,
        )

    async def _click_public_submarket(self, page: Page, specific_market: str) -> bool:
        """Click the exact line's header, not another line or a bookmaker odds cell."""
        for header in await page.query_selector_all(OddsPortalSelectors.PUBLIC_SUBMARKET_CSS):
            if (await header.text_content()).strip() == specific_market:
                await header.click()
                return True
        self.logger.warning(f"Public submarket unavailable: {specific_market}")
        return False

    async def wait_for_page_load(self, page: Page) -> None:
        """Wait for page content to load."""
        await page.wait_for_timeout(SCROLL_PAUSE_TIME_MS)
