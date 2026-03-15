"""
tests/test_bricklink.py — pytest suite for bricklink.py

The only thing mocked is bricklink_py.Bricklink (the third-party OAuth client)
since it requires live credentials. All BrickLinkAPI methods are tested with
real logic against a mocked self.session.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


# ── Stub bricklink_py and force-reload bricklink so the real code runs ───────
import sys

_bl_py_stub = MagicMock()
sys.modules['bricklink_py'] = _bl_py_stub  # always overwrite, not setdefault

# Force reload bricklink so it re-executes `from bricklink_py import Bricklink`
# and binds the stub. This ensures patch('bricklink.Bricklink') always works
# regardless of import order with other test files.
sys.modules.pop('bricklink', None)
import bricklink  # noqa: E402
from bricklink import BrickLinkAPI  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def make_api(tmp_path):
    """Return a BrickLinkAPI instance wired to a temp config, with a mock session."""
    cfg = tmp_path / 'config.ini'
    cfg.write_text(
        '[secrets]\n'
        'consumer_key = ck\n'
        'consumer_secret = cs\n'
        'token_value = tv\n'
        'token_secret = ts\n'
    )
    mock_session = MagicMock()
    # Patch where Bricklink is looked up — in the bricklink module namespace
    with patch('bricklink.Bricklink', return_value=mock_session):
        api = BrickLinkAPI(str(cfg))
    api.session = mock_session
    return api


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrickLinkAPIInit:
    def test_reads_credentials_from_config(self, tmp_path):
        cfg = tmp_path / 'config.ini'
        cfg.write_text(
            '[secrets]\nconsumer_key = MY_CK\nconsumer_secret = MY_CS\n'
            'token_value = MY_TV\ntoken_secret = MY_TS\n'
        )
        mock_session = MagicMock()
        _bl_py_stub.Bricklink.reset_mock()
        _bl_py_stub.Bricklink.return_value = mock_session
        BrickLinkAPI(str(cfg))
        _bl_py_stub.Bricklink.assert_called_once_with(
            consumer_key='MY_CK',
            consumer_secret='MY_CS',
            token='MY_TV',
            token_secret='MY_TS',
        )

    def test_sets_dict_initialised_empty(self, tmp_path):
        api = make_api(tmp_path)
        assert api.sets == {}

    def test_session_stored_on_instance(self, tmp_path):
        api = make_api(tmp_path)
        assert api.session is not None


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.get_last_sale_date  (static — no mock needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetLastSaleDate:
    def test_returns_most_recent_date(self):
        sales = {
            1: {'date_ordered': '2023-05-27T01:09:39.493Z'},
            2: {'date_ordered': '2023-12-11T18:44:02.100Z'},
            3: {'date_ordered': '2022-08-03T09:15:55.000Z'},
        }
        assert BrickLinkAPI.get_last_sale_date(sales) == '2023-12-11T18:44:02.100Z'

    def test_returns_none_for_empty_dict(self):
        assert BrickLinkAPI.get_last_sale_date({}) is None

    def test_returns_none_for_empty_list(self):
        assert BrickLinkAPI.get_last_sale_date([]) is None

    def test_accepts_list_input(self):
        sales = [
            {'date_ordered': '2024-01-01T00:00:00.000Z'},
            {'date_ordered': '2024-06-15T12:00:00.000Z'},
        ]
        assert BrickLinkAPI.get_last_sale_date(sales) == '2024-06-15T12:00:00.000Z'

    def test_skips_entries_with_missing_date(self):
        sales = [
            {'date_ordered': ''},
            {'date_ordered': '2024-03-10T08:00:00.000Z'},
            {},
        ]
        assert BrickLinkAPI.get_last_sale_date(sales) == '2024-03-10T08:00:00.000Z'

    def test_skips_entries_with_invalid_date(self):
        sales = [
            {'date_ordered': 'not-a-date'},
            {'date_ordered': '2024-03-10T08:00:00.000Z'},
        ]
        assert BrickLinkAPI.get_last_sale_date(sales) == '2024-03-10T08:00:00.000Z'

    def test_returns_none_when_all_dates_invalid(self):
        sales = [{'date_ordered': 'bad'}, {'date_ordered': ''}]
        assert BrickLinkAPI.get_last_sale_date(sales) is None

    def test_single_entry_returned(self):
        sales = [{'date_ordered': '2025-02-08T21:05:26.307Z'}]
        assert BrickLinkAPI.get_last_sale_date(sales) == '2025-02-08T21:05:26.307Z'

    def test_handles_timezone_comparison_correctly(self):
        # Earlier calendar date but later in the year should lose
        sales = [
            {'date_ordered': '2023-01-31T23:59:59.000Z'},
            {'date_ordered': '2023-11-01T00:00:01.000Z'},
        ]
        assert BrickLinkAPI.get_last_sale_date(sales) == '2023-11-01T00:00:01.000Z'


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.getSetInfo
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSetInfo:
    def test_stores_set_fields(self, tmp_path):
        api = make_api(tmp_path)
        api.session.catalog_item.get_item.return_value = {
            'name':          'Millennium Falcon',
            'year_released': 2017,
            'image_url':     '//img.bricklink.com/SL/75192-1.jpg',
            'thumbnail_url': '//img.bricklink.com/S/75192-1.jpg',
            'category_id':   65,
        }
        api.getSetInfo('75192-1', 'SET')

        assert api.sets['75192-1']['name']        == 'Millennium Falcon'
        assert api.sets['75192-1']['year']        == 2017
        assert api.sets['75192-1']['image']       == '//img.bricklink.com/SL/75192-1.jpg'
        assert api.sets['75192-1']['thumbnail']   == '//img.bricklink.com/S/75192-1.jpg'
        assert api.sets['75192-1']['category_id'] == 65

    def test_calls_api_with_correct_item_type(self, tmp_path):
        api = make_api(tmp_path)
        api.session.catalog_item.get_item.return_value = {
            'name': 'X', 'year_released': 2020,
            'image_url': '', 'thumbnail_url': '', 'category_id': 1,
        }
        api.getSetInfo('75192-1', 'GEAR')
        api.session.catalog_item.get_item.assert_called_once_with('GEAR', '75192-1')

    def test_unescapes_html_entities_in_name(self, tmp_path):
        api = make_api(tmp_path)
        api.session.catalog_item.get_item.return_value = {
            'name': 'Pirates &amp; Knights',
            'year_released': 2010, 'image_url': '',
            'thumbnail_url': '', 'category_id': 1,
        }
        api.getSetInfo('1-1', 'SET')
        assert api.sets['1-1']['name'] == 'Pirates & Knights'


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.getSetPastSales
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSetPastSales:
    def _setup(self, tmp_path, price_detail=None):
        api = make_api(tmp_path)
        api.sets['75192-1'] = {}
        api.session.catalog_item.get_price_guide.return_value = {
            'avg_price':    '929.50',
            'max_price':    '1298.00',
            'min_price':    '520.75',
            'unit_quantity': 14,
            'currency_code': 'USD',
            'price_detail':  price_detail or [],
        }
        return api

    def test_stores_past_sales_fields(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetPastSales('75192-1', 'SET')
        past = api.sets['75192-1']['past']
        assert past['avg']      == 929
        assert past['max']      == 1298
        assert past['min']      == 520
        assert past['quantity'] == 14
        assert past['currency'] == 'USD'

    def test_prices_are_rounded_integers(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetPastSales('75192-1', 'SET')
        past = api.sets['75192-1']['past']
        assert isinstance(past['avg'], int)
        assert isinstance(past['max'], int)
        assert isinstance(past['min'], int)

    def test_last_sale_date_populated_from_price_detail(self, tmp_path):
        detail = [
            {'date_ordered': '2023-05-01T00:00:00.000Z'},
            {'date_ordered': '2024-02-08T21:05:26.307Z'},
        ]
        api = self._setup(tmp_path, price_detail=detail)
        api.getSetPastSales('75192-1', 'SET')
        assert api.sets['75192-1']['past']['last_sale_date'] == '2024-02-08T21:05:26.307Z'

    def test_last_sale_date_none_when_no_detail(self, tmp_path):
        api = self._setup(tmp_path, price_detail=[])
        api.getSetPastSales('75192-1', 'SET')
        assert api.sets['75192-1']['past']['last_sale_date'] is None

    def test_calls_api_with_correct_params(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetPastSales('75192-1', 'SET')
        api.session.catalog_item.get_price_guide.assert_called_once_with(
            'SET', '75192-1',
            new_or_used='N', guide_type='sold',
            country_code='US', region='north_america',
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.getSetCurrentSales
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSetCurrentSales:
    def _setup(self, tmp_path):
        api = make_api(tmp_path)
        api.sets['75192-1'] = {}
        api.session.catalog_item.get_price_guide.return_value = {
            'avg_price':     '450.00',
            'max_price':     '800.00',
            'min_price':     '350.00',
            'unit_quantity': 5,
            'currency_code': 'USD',
        }
        return api

    def test_stores_current_sales_fields(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetCurrentSales('75192-1', 'SET')
        current = api.sets['75192-1']['current']
        assert current['avg']      == 450
        assert current['max']      == 800
        assert current['min']      == 350
        assert current['quantity'] == 5
        assert current['currency'] == 'USD'

    def test_prices_are_rounded_integers(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetCurrentSales('75192-1', 'SET')
        current = api.sets['75192-1']['current']
        assert isinstance(current['avg'], int)
        assert isinstance(current['max'], int)
        assert isinstance(current['min'], int)

    def test_calls_api_without_guide_type(self, tmp_path):
        api = self._setup(tmp_path)
        api.getSetCurrentSales('75192-1', 'SET')
        _, kwargs = api.session.catalog_item.get_price_guide.call_args
        assert 'guide_type' not in kwargs


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.getSetCatalogInfo
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSetCatalogInfo:
    def test_stores_category_name(self, tmp_path):
        api = make_api(tmp_path)
        api.sets['75192-1'] = {'category_id': 65}
        api.session.category.get_category.return_value = {'category_name': 'Star Wars'}
        api.getSetCatalogInfo('75192-1')
        assert api.sets['75192-1']['category'] == 'Star Wars'

    def test_unescapes_html_in_category_name(self, tmp_path):
        api = make_api(tmp_path)
        api.sets['75192-1'] = {'category_id': 65}
        api.session.category.get_category.return_value = {'category_name': 'Pirates &amp; Treasure'}
        api.getSetCatalogInfo('75192-1')
        assert api.sets['75192-1']['category'] == 'Pirates & Treasure'

    def test_calls_api_with_category_id(self, tmp_path):
        api = make_api(tmp_path)
        api.sets['75192-1'] = {'category_id': 65}
        api.session.category.get_category.return_value = {'category_name': 'Star Wars'}
        api.getSetCatalogInfo('75192-1')
        api.session.category.get_category.assert_called_once_with(65)


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.processSet
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessSet:
    def _mock_api_methods(self, api, set_number='75192-1'):
        """Stub the four internal methods so processSet runs without real API calls."""
        api.getSetInfo         = MagicMock()
        api.getSetCatalogInfo  = MagicMock()
        api.getSetPastSales    = MagicMock()
        api.getSetCurrentSales = MagicMock()
        api.sets = {set_number: {'name': 'Test Set'}}

    def test_returns_sets_dict_on_success(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api)
        result = api.processSet('75192-1')
        assert result == {'75192-1': {'name': 'Test Set'}}

    def test_uses_set_item_type_by_default(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api)
        api.processSet('75192-1')
        api.getSetInfo.assert_called_once_with('75192-1', 'SET')

    def test_uses_gear_item_type_for_40158(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api, set_number='40158')
        api.processSet('40158')
        api.getSetInfo.assert_called_once_with('40158', 'GEAR')

    def test_calls_all_four_sub_methods(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api)
        api.processSet('75192-1')
        api.getSetInfo.assert_called_once()
        api.getSetCatalogInfo.assert_called_once()
        api.getSetPastSales.assert_called_once()
        api.getSetCurrentSales.assert_called_once()

    def test_returns_empty_dict_on_exception(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api)
        api.getSetInfo.side_effect = Exception('API error')
        result = api.processSet('75192-1')
        assert result == {}

    def test_exception_does_not_propagate(self, tmp_path):
        api = make_api(tmp_path)
        self._mock_api_methods(api)
        api.getSetCatalogInfo.side_effect = RuntimeError('network timeout')
        # Should not raise
        api.processSet('75192-1')


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.getSets
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSets:
    def test_returns_sets_dict(self, tmp_path):
        api = make_api(tmp_path)
        api.sets = {'75192-1': {'name': 'Falcon'}}
        assert api.getSets() == {'75192-1': {'name': 'Falcon'}}

    def test_returns_empty_dict_initially(self, tmp_path):
        api = make_api(tmp_path)
        assert api.getSets() == {}


# ═══════════════════════════════════════════════════════════════════════════════
# BrickLinkAPI.print_details
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrintDetails:
    def _sample_data(self):
        return {
            'name': 'Millennium Falcon', 'category': 'Star Wars',
            'current': {'avg': 450, 'max': 800, 'min': 350,
                        'quantity': 5, 'currency': 'USD'},
            'past':    {'avg': 400, 'max': 750, 'min': 300,
                        'quantity': 12, 'currency': 'USD',
                        'last_sale_date': '2024-06-15T10:00:00.000Z'},
            'year': 2017,
            'image': '//img.bricklink.com/SL/75192-1.jpg',
            'thumbnail': '//img.bricklink.com/S/75192-1.jpg',
        }

    def test_does_not_raise(self, tmp_path):
        api = make_api(tmp_path)
        # Should complete without error regardless of log level
        api.print_details(self._sample_data(), '75192-1')

    def test_accepts_none_last_sale_date(self, tmp_path):
        api = make_api(tmp_path)
        data = self._sample_data()
        data['past']['last_sale_date'] = None
        api.print_details(data, '75192-1')