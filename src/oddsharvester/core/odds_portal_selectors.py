from typing import ClassVar


class OddsPortalSelectors:
    """Centralized CSS selectors for OddsPortal website elements."""

    # Cookie banner
    COOKIE_BANNER = "#onetrust-accept-btn-handler"

    # The public header uses button options (legacy pages used anchors).
    # Scope by the odds label, not gap utility classes shared with language controls.
    ODDS_FORMAT_BUTTON_CSS = "div.group > button:has-text('Odds')"
    ODDS_FORMAT_OPTIONS_CSS = "div.group:has(> button:has-text('Odds')) > div > ul > li > :is(button, a)"

    # Market navigation tabs
    MARKET_TAB_SELECTORS: ClassVar[list[str]] = [
        "li.tab-item > button",
        "ul.visible-links.bg-black-main.odds-tabs > li",
        "ul.odds-tabs > li",
        "ul[class*='odds-tabs'] > li",
        "div[class*='odds-tabs'] li",
        "li[class*='tab']",
        "nav li",
    ]
    PUBLIC_ACTIVE_MARKET_CSS = "li.tab-item.active-item-feed > button"
    PUBLIC_MARKET_TAB_CSS = "li.tab-item > button"
    PUBLIC_SUBMARKET_CSS = "table tr.cursor-pointer > td span[class~='max-sm:hidden']"
    PUBLIC_SUBMARKET_ROW_CSS = "table tr.cursor-pointer"
    PUBLIC_SUBMARKET_NAME_CSS = "td span[class~='max-sm:hidden']"
    PUBLIC_SUBMARKET_COUNT_CSS = "td span.ml-auto"
    PUBLIC_BOOKMAKER_ROW_CSS = "table tr:has(> td a[href^='/proxy/bookmakers/'][href$='/link/'])"
    PUBLIC_BOOKMAKER_NAME_CSS = "a[href^='/proxy/bookmakers/'][href$='/link/'] p"
    PUBLIC_ODDS_CELL_CSS = "td[class*='event-table-odd-col']"
    PUBLIC_ODDS_VALUE_CSS = "div.flex.flex-col.items-center.justify-center.font-main.font-bold"
    PUBLIC_PERIOD_BUTTON_CSS = "div.no-scrollbar > button"
    EVENT_HEADER_CONTENT_CSS = "#react-event-header, script[type='application/ld+json']"
    PUBLIC_EVENT_METADATA_CSS = "script[type='application/ld+json']"

    # "More" dropdown button selectors
    MORE_BUTTON_SELECTORS: ClassVar[list[str]] = [
        "button.toggle-odds:has-text('More')",
        "button[class*='toggle-odds']",
        ".visible-btn-odds:has-text('More')",
        "li:has-text('More')",
        "li:has-text('more')",
        "li[class*='more']",
        "li button:has-text('More')",
        "li a:has-text('More')",
    ]

    # Market navigation - sub-market selection
    SUB_MARKET_SELECTOR = "div.flex.w-full.items-center.justify-start.pl-3.font-bold p"

    # Bookmaker filter navigation
    BOOKIES_FILTER_CONTAINER = "div[data-testid='bookies-filter-nav']"
    BOOKIES_FILTER_ACTIVE_CLASS = "active-item-calendar"

    # Period selection navigation
    PERIOD_SELECTOR_CONTAINER = "div[data-testid='kickoff-events-nav']"
    PERIOD_ACTIVE_CLASS = "active-item-calendar"

    @staticmethod
    def get_dropdown_selectors_for_market(market_name: str) -> list[str]:
        """Generate dropdown selectors for a specific market name."""
        return [
            f"li:has-text('{market_name}')",
            f"a:has-text('{market_name}')",
            f"button:has-text('{market_name}')",
            f"div:has-text('{market_name}')",
            f"span:has-text('{market_name}')",
        ]

    @staticmethod
    def get_bookies_filter_selector(filter_value: str) -> str:
        """
        Generate selector for a specific bookmaker filter option.

        Args:
            filter_value: The filter value (e.g., 'all', 'classic', 'crypto').

        Returns:
            str: CSS selector for the filter option.
        """
        return f"div[data-testid='bookies-filter-nav'] div[data-testid='{filter_value}']"

    # Bookmaker elements — BeautifulSoup class patterns
    BOOKMAKER_ROW_CLASS = "border-black-borders"
    BOOKMAKER_ROW_FALLBACK_CLASS = r"^border-black-borders flex h-9"
    BOOKMAKER_LOGO_CLASS = "bookmaker-logo"
    ODDS_BLOCK_CLASS_PATTERN = r"flex-center.*flex-col.*font-bold"

    # Bookmaker elements — Playwright CSS selectors
    BOOKMAKER_ROW_CSS = "div.border-black-borders.flex.h-9"
    BOOKMAKER_LOGO_CSS = "img.bookmaker-logo"
    ODDS_BLOCK_CSS = "div.flex-center.flex-col.font-bold"
    ODDS_MOVEMENT_HEADER = "h3:text('Odds movement')"

    # Event listing — BeautifulSoup class pattern
    EVENT_ROW_CLASS_PATTERN = "^eventRow"
    # Redesigned public listings link to an H2H route with an event ID fragment.
    # A pair-only H2H URL is not a specific fixture.
    PUBLIC_MATCH_LINK_CSS = "a.group[href*='/h2h/'][href*='/#']"
    PUBLIC_MATCH_HREF_PATTERN = r"^/[a-z-]+/h2h/[^/?#]+-[A-Za-z0-9]{8}/[^/?#]+-[A-Za-z0-9]{8}/#[A-Za-z0-9]{8}$"
    EVENT_LISTING_CONTENT_CSS = f"div[class*='eventRow'], {PUBLIC_MATCH_LINK_CSS}"
    # Public league listings group fixtures under "Today, 01 Nov" or "05 Nov 2026" headers.
    LISTING_DATE_HEADER_PATTERN = (
        r"^(?:(?:Yesterday|Today|Tomorrow), (?P<day_month>\d{2} [A-Z][a-z]{2})"
        r"|(?P<absolute>\d{2} [A-Z][a-z]{2} \d{4}))$"
    )

    # Submarket name — BeautifulSoup class
    SUBMARKET_CLEAN_NAME_CLASS = "max-sm:!hidden"

    # Debug selectors
    DROPDOWN_DEBUG_ELEMENTS = "li, a, button, div, span"
