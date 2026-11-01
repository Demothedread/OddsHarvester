from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.browser_helper import BrowserHelper
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.sport_market_registry import SportMarketRegistry
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.constants import DEFAULT_MARKET_TIMEOUT_MS

# Sample HTML for testing
SAMPLE_HTML_ODDS = """
<div class="border-black-borders flex h-9">
    <img class="bookmaker-logo" title="Bookmaker1">
    <div class="flex-center flex-col font-bold">1.90</div>
    <div class="flex-center flex-col font-bold">3.50</div>
    <div class="flex-center flex-col font-bold">4.20</div>
</div>
<div class="border-black-borders flex h-9">
    <img class="bookmaker-logo" title="Bookmaker2">
    <div class="flex-center flex-col font-bold">1.85</div>
    <div class="flex-center flex-col font-bold">3.60</div>
    <div class="flex-center flex-col font-bold">4.10</div>
</div>
"""

SAMPLE_HTML_ODDS_HISTORY = """
<div>
    <h3>Odds movement</h3>
    <div class="flex flex-col gap-1">
        <div class="flex gap-3">
            <div class="font-normal">10 Jun, 14:30</div>
        </div>
        <div class="flex gap-3">
            <div class="font-normal">10 Jun, 12:00</div>
        </div>
    </div>
    <div class="flex flex-col gap-1">
        <div class="font-bold">1.95</div>
        <div class="font-bold">1.90</div>
    </div>
    <div class="mt-2 gap-1">
        <div class="flex gap-1">
            <div>10 Jun, 08:00</div>
            <div class="font-bold">1.85</div>
        </div>
    </div>
</div>
"""


class TestOddsPortalMarketExtractor:
    """Unit tests for the OddsPortalMarketExtractor class."""

    @pytest.fixture
    def browser_helper_mock(self):
        """Create a mock for BrowserHelper."""
        mock = MagicMock(spec=BrowserHelper)
        return mock

    @pytest.fixture
    def extractor(self, browser_helper_mock):
        """Create an instance of OddsPortalMarketExtractor with a mocked BrowserHelper."""
        return OddsPortalMarketExtractor(browser_helper_mock)

    @pytest.fixture
    def page_mock(self):
        """Create a mock for the Playwright page."""
        mock = AsyncMock()
        mock.query_selector_all.return_value = []
        mock.content = AsyncMock(return_value=SAMPLE_HTML_ODDS)
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_parse_market_odds(self, extractor):
        """Test parsing odds from known HTML."""
        # Arrange
        odds_labels = ["1", "X", "2"]

        # Act
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 2
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"
        assert result[0]["period"] == "FullTime"
        assert result[1]["bookmaker_name"] == "Bookmaker2"

    @pytest.mark.asyncio
    async def test_parse_market_odds_with_target_bookmaker(self, extractor):
        """Test parsing odds with a specific target bookmaker."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        target_bookmaker = "Bookmaker1"

        # Act
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels, target_bookmaker)

        # Assert
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"

    @pytest.mark.asyncio
    async def test_parse_market_odds_no_bookmakers(self, extractor):
        """Test parsing odds when no bookmakers are found."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        empty_html = "<div>No bookmakers found</div>"

        # Act
        result = extractor.odds_parser.parse_market_odds(empty_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_parse_market_odds_preserves_partial_bookmaker_data(self, extractor):
        """Keep valid prices while marking the missing selection unavailable."""
        # Arrange
        odds_labels = ["1", "X", "2", "Extras"]

        # Act
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 2
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"
        assert result[0]["Extras"] is None

    @pytest.mark.asyncio
    async def test_parse_market_odds_error_handling(self, extractor):
        """Test error handling during odds parsing."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        broken_html = """
        <div class="border-black-borders flex h-9">
            <img class="bookmaker-logo" title="Bookmaker1">
            <!-- Data manquante/corrompue -->
        </div>
        """

        # Act
        result = extractor.odds_parser.parse_market_odds(broken_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0  # Should handle error gracefully

    def test_parse_odds_history_modal(self, extractor):
        """Test parsing odds history from a modal HTML."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)

            # Act
            result = extractor.odds_parser.parse_odds_history_modal(SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == 1.95
            assert result["odds_history"][1]["odds"] == 1.90

            # Verify that opening odds data is present without checking exact values
            # as they depend on the extractor implementation
            assert "opening_odds" in result

    def test_parse_odds_history_modal_invalid_html(self, extractor):
        """Test parsing odds history from invalid HTML."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)

            # Act
            invalid_html = "<div>Invalid HTML content</div>"
            result = extractor.odds_parser.parse_odds_history_modal(invalid_html)

            # Assert
            assert result == {}

    def test_parse_odds_history_modal_invalid_date(self, extractor):
        """Test parsing odds history with invalid date format."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            # Force ValueError on strptime
            mock_datetime.strptime.side_effect = ValueError("Invalid date format")

            # Act
            result = extractor.odds_parser.parse_odds_history_modal(SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 0

    @pytest.mark.asyncio
    async def test_extract_market_odds(self, extractor, page_mock, browser_helper_mock):
        """Test complete extraction of odds for a given market."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}]
        )

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="1X2")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        main_market = "1X2"
        odds_labels = ["1", "X", "2"]

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market=main_market, odds_labels=odds_labels)

        # Assert
        browser_helper_mock.navigate_to_market_tab.assert_called_once_with(
            page=page_mock, market_tab_name=main_market, timeout=DEFAULT_MARKET_TIMEOUT_MS
        )
        extractor.odds_parser.parse_market_odds.assert_called_once()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_specific_market(self, extractor, page_mock, browser_helper_mock):
        """Test extracting odds with a specific sub-market."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        browser_helper_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[
                {"bookmaker_name": "Bookmaker1", "odds_over": "1.90", "odds_under": "1.90", "period": "FullTime"}
            ]
        )

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="Over/Under")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        main_market = "Over/Under"
        specific_market = "Over/Under +2.5"
        odds_labels = ["odds_over", "odds_under"]

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market=main_market, specific_market=specific_market, odds_labels=odds_labels
        )

        # Assert
        browser_helper_mock.navigate_to_market_tab.assert_called_once()
        browser_helper_mock.scroll_until_visible_and_click_parent.assert_called()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_tab_not_found(self, extractor, page_mock, browser_helper_mock):
        """Test behavior when the market tab is not found."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=False)

        page_mock.query_selector = AsyncMock(return_value=None)

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market="NonExistentMarket", odds_labels=["1", "X", "2"]
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_specific_market_not_found(self, extractor, page_mock, browser_helper_mock):
        """Test behavior when the specific market is not found."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        browser_helper_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=False)

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="Over/Under")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="NonExistentSpecificMarket",
            odds_labels=["odds_over", "odds_under"],
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_odds_history(self, extractor, page_mock, browser_helper_mock):
        """Test extracting odds with odds history."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock(
            return_value=[SAMPLE_HTML_ODDS_HISTORY]
        )
        extractor.odds_parser.parse_odds_history_modal = MagicMock(
            return_value={
                "odds_history": [{"timestamp": "2025-06-10T14:30:00", "odds": 1.95}],
                "opening_odds": {"timestamp": "2025-06-10T08:00:00", "odds": 1.85},
            }
        )

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="1X2")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], scrape_odds_history=True
        )

        # Assert
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker.assert_called_once()
        extractor.odds_parser.parse_odds_history_modal.assert_called_once()
        assert len(result) == 1
        assert "odds_history_data" in result[0]
        assert result[0]["odds_history_data"][0]["odds_history"][0]["odds"] == 1.95

    @pytest.mark.asyncio
    async def test_extract_market_odds_exception(self, extractor, page_mock, browser_helper_mock):
        """Test handling of exceptions during market extraction."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker(self, extractor, page_mock):
        """Test extracting odds history for a specific bookmaker."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper and element
        modal_wrapper = AsyncMock()
        modal_element = AsyncMock()
        modal_element.inner_html = AsyncMock(return_value=SAMPLE_HTML_ODDS_HISTORY)
        modal_wrapper.as_element = MagicMock(return_value=modal_element)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.return_value = modal_wrapper

        # Act
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert len(result) == 1
        assert result[0] == SAMPLE_HTML_ODDS_HISTORY

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_no_match(self, extractor, page_mock):
        """Test extraction when no matching bookmaker is found."""
        # Arrange
        bookmaker_name = "NonExistentBookmaker"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value="DifferentBookmaker")
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_exception(self, extractor, page_mock):
        """Test error handling when an exception occurs during odds history extraction."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock that raises an exception
        page_mock.query_selector_all = AsyncMock(side_effect=Exception("Test exception"))

        # Act - This method handles exceptions internally
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert - Should return an empty list on exception
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_markets(self, extractor, page_mock):
        """Test scraping multiple markets for a match."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_market_func, "btts": mock_market_func}

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["1x2", "btts", "nonexistent_market"]
            )

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert "nonexistent_market_market" not in result
        assert mock_market_func.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_markets_with_exception(self, extractor, page_mock):
        """Test scraping markets where one market throws an exception."""
        # Arrange
        mock_success_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        mock_error_func = AsyncMock(side_effect=Exception("Test exception"))

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_success_func, "btts": mock_error_func}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["1x2", "btts"])

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert result["1x2_market"] is not None
        assert result["btts_market"] is None

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_groups_markets(self, extractor, page_mock):
        """Test that preview mode groups markets by main market and scrapes once."""
        # Arrange — two markets sharing the same main market
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]

        def _make_closure(main_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)

        func_a = _make_closure(main_market, odds_labels)
        func_b = _make_closure(main_market, odds_labels)

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock) as mock_extract,
        ):
            mock_mapping.return_value = {"over_under_1_5": func_a, "over_under_2_5": func_b}
            mock_extract.return_value = [{"submarket_name": "Over/Under 1.5", "odds_over": "1.50"}]

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        # Both markets should get the same data, extract called once for the group
        assert "over_under_1_5_market" in result
        assert "over_under_2_5_market" in result
        mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_assigns_each_line_its_own_row(self, extractor, page_mock):
        """One tab visit fills each specific line key with only its matching row."""

        def _make_closure(main_market, specific_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, specific_market, odds_labels)

        rows = [
            {"submarket_name": "Asian Handicap -3.5", "1": "2.02", "2": "1.82"},
            {"submarket_name": "Asian Handicap -2.5", "1": "1.81", "2": "2.10"},
        ]

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=rows) as mock_extract,
        ):
            mock_mapping.return_value = {
                "asian_handicap_-3_5": _make_closure("Asian Handicap", "Asian Handicap -3.5", ["1", "2"]),
                "asian_handicap_-2_5": _make_closure("Asian Handicap", "Asian Handicap -2.5", ["1", "2"]),
                "asian_handicap_-7_5": _make_closure("Asian Handicap", "Asian Handicap -7.5", ["1", "2"]),
            }

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="american-football",
                markets=["asian_handicap_-3_5", "asian_handicap_-2_5", "asian_handicap_-7_5"],
                preview_submarkets_only=True,
            )

        mock_extract.assert_called_once()
        assert result["asian_handicap_-3_5_market"] == [rows[0]]
        assert result["asian_handicap_-2_5_market"] == [rows[1]]
        assert result["asian_handicap_-7_5_market"] == []

    def test_distribute_grouped_rows_does_not_broadcast_unmatched_named_lines(self, extractor):
        def _make_closure(specific_market):
            main_market = "Asian Handicap"
            odds_labels = ["1", "2"]
            return lambda self, page, period, hist, bk, preview, sport: (
                main_market,
                specific_market,
                odds_labels,
            )

        rows = [{"submarket_name": "Asian Handicap -4.5", "1": "1.90", "2": "1.90"}]
        market_methods = {
            "asian_handicap_-14_5": _make_closure("Asian Handicap -14.5"),
            "asian_handicap_-3_5": _make_closure("Asian Handicap -3.5"),
        }

        result = extractor._distribute_grouped_rows(
            rows,
            list(market_methods),
            market_methods,
        )

        assert result == {
            "asian_handicap_-14_5_market": [],
            "asian_handicap_-3_5_market": [],
        }

    def test_distribute_grouped_rows_matches_integer_lines_without_decimal_suffix(self, extractor):
        def _make_closure(specific_market):
            main_market = "Asian Handicap"
            odds_labels = ["1", "2"]

            return lambda self, page, period, hist, bk, preview, sport: (
                main_market,
                specific_market,
                odds_labels,
            )

        rows = [{"submarket_name": "Asian Handicap -3", "1": "1.90", "2": "1.90"}]
        market_methods = {
            "asian_handicap_-3_0": _make_closure("Asian Handicap -3.0"),
            "asian_handicap_-4_0": _make_closure("Asian Handicap -4.0"),
        }

        result = extractor._distribute_grouped_rows(
            rows,
            list(market_methods),
            market_methods,
        )

        assert result == {
            "asian_handicap_-3_0_market": rows,
            "asian_handicap_-4_0_market": [],
        }

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_reads_single_markets_directly(self, extractor, page_mock):
        """Markets without line submarkets skip the passive preview attempt."""

        def _make_closure(main_market, specific_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, specific_market, odds_labels)

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[]) as mock_extract,
        ):
            mock_mapping.return_value = {"home_away": _make_closure("Home/Away", None, ["1", "2"])}

            await extractor.scrape_markets(
                page=page_mock, sport="american-football", markets=["home_away"], preview_submarkets_only=True
            )

        assert mock_extract.await_args.kwargs["preview_submarkets_only"] is False

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_exception_sets_none(self, extractor, page_mock):
        """Test that grouped market exception in preview mode sets all group entries to None."""
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]

        def _make_closure(main_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)

        func = _make_closure(main_market, odds_labels)

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, side_effect=Exception("boom")),
        ):
            mock_mapping.return_value = {"over_under_1_5": func, "over_under_2_5": func}

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        assert result["over_under_1_5_market"] is None
        assert result["over_under_2_5_market"] is None

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_period_selection(self, extractor, page_mock, browser_helper_mock):
        """Test that period selection is performed when sport is provided."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        browser_helper_mock.ensure_period_selected = AsyncMock()

        mock_period = MagicMock()
        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=mock_period):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        browser_helper_mock.ensure_period_selected.assert_called_once_with(page=page_mock, desired_period=mock_period)

    @pytest.mark.asyncio
    async def test_extract_market_odds_period_not_found_skips(self, extractor, page_mock, browser_helper_mock):
        """Test that period selection is skipped when period enum is not found."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        browser_helper_mock.ensure_period_selected = AsyncMock()

        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=None):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        browser_helper_mock.ensure_period_selected.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_mode_passive(self, extractor, page_mock, browser_helper_mock):
        """Test preview mode uses passive submarket extraction."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(
            return_value=[{"submarket_name": "Over/Under 2.5", "odds_over": "1.80", "odds_under": "2.00"}]
        )

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            odds_labels=["odds_over", "odds_under"],
            preview_submarkets_only=True,
        )

        extractor.submarket_extractor.extract_visible_submarkets_passive.assert_called_once()
        assert len(result) == 1
        assert result[0]["submarket_name"] == "Over/Under 2.5"

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_mode_fallback_to_active(self, extractor, page_mock, browser_helper_mock):
        """Test preview mode falls back to normal scraping when passive returns no data."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(return_value=[])
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90"}]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="1X2",
            odds_labels=["1", "X", "2"],
            preview_submarkets_only=True,
        )

        extractor.submarket_extractor.extract_visible_submarkets_passive.assert_called_once()
        extractor.odds_parser.parse_market_odds.assert_called_once()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_fallback_specific_market_not_found(
        self, extractor, page_mock, browser_helper_mock
    ):
        """Test preview fallback returns [] when specific market can't be selected."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(return_value=[])
        extractor.navigation_manager.select_specific_market = AsyncMock(return_value=False)

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="Over/Under +9.5",
            odds_labels=["odds_over", "odds_under"],
            preview_submarkets_only=True,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_history_skips_filtered_bk(self, extractor, page_mock, browser_helper_mock):
        """Test that odds history is skipped for bookmakers not matching target."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[
                {"bookmaker_name": "Bookmaker1", "1": "1.90", "period": "FullTime"},
                {"bookmaker_name": "Bookmaker2", "1": "1.85", "period": "FullTime"},
            ]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock()
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        await extractor.extract_market_odds(
            page=page_mock,
            main_market="1X2",
            odds_labels=["1"],
            scrape_odds_history=True,
            target_bookmaker="Bookmaker1",
        )

        # Only called for Bookmaker1, not Bookmaker2
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker.assert_called_once_with(
            page_mock, "Bookmaker1"
        )
