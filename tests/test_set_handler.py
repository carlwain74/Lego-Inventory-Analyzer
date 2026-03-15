"""
tests/test_set_handler.py — pytest suite for set_handler.py

bricklink_py (third-party OAuth client) and generate_sheets (file I/O) are
mocked. BrickLinkAPI is patched per-test via patch('set_handler.BrickLinkAPI')
so the real SetHandler code runs. conftest.py registers set_handler as a mock
for app.py tests, so we explicitly reload the real module here.
"""

import os
import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch, call


# ── Ensure third-party dependencies are stubbed ───────────────────────────────
sys.modules['bricklink_py']    = MagicMock()
sys.modules['generate_sheets'] = MagicMock()

# ── Force-load the real set_handler module, bypassing any conftest mock ───────
# conftest registers set_handler as a MagicMock for app.py tests.
# We remove it here so importlib loads the real file from disk.
sys.modules.pop('set_handler', None)
sys.modules.pop('bricklink',   None)

import bricklink    # noqa: E402 — loads real bricklink.py with bricklink_py stubbed
import set_handler as sh_module  # noqa: E402 — loads real set_handler.py
from set_handler import SetHandler  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_SETS = {
    '75192-1': {
        'name': 'Millennium Falcon', 'category': 'Star Wars',
        'current': {'avg': 450, 'max': 800, 'min': 350, 'quantity': 5,  'currency': 'USD'},
        'past':    {'avg': 400, 'max': 750, 'min': 300, 'quantity': 12, 'currency': 'USD',
                    'last_sale_date': '2024-06-15T10:00:00.000Z'},
        'year': 2017,
        'image':     '//img.bricklink.com/SL/75192-1.jpg',
        'thumbnail': '//img.bricklink.com/S/75192-1.jpg',
    }
}


def make_handler(set_num=None, set_list=None, multi_sheet=False,
                 output_file='Sets.xlsx', config_file='config.ini'):
    """
    Instantiate a real SetHandler with BrickLinkAPI patched out.
    Returns (handler, mock_session).
    """
    mock_session = MagicMock()
    with patch('set_handler.BrickLinkAPI', return_value=mock_session):
        handler = SetHandler(
            set_num=set_num,
            set_list=set_list,
            multi_sheet=multi_sheet,
            output_file=output_file,
            config_file=config_file,
        )
    return handler, mock_session


# ═══════════════════════════════════════════════════════════════════════════════
# SetHandler.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetHandlerInit:
    def test_stores_set_number(self):
        h, _ = make_handler(set_num='75192-1')
        assert h.set_number == '75192-1'

    def test_stores_set_list(self, tmp_path):
        path = str(tmp_path / 'sets.txt')
        h, _ = make_handler(set_list=path)
        assert h.set_list == path

    def test_stores_multi_sheet(self):
        h, _ = make_handler(multi_sheet=True)
        assert h.multi_sheet is True

    def test_stores_output_file(self):
        h, _ = make_handler(output_file='/tmp/out.xlsx')
        assert h.output_file == '/tmp/out.xlsx'

    def test_stores_config_file(self):
        h, _ = make_handler(config_file='/tmp/config.ini')
        assert h.config_file == '/tmp/config.ini'

    def test_creates_bricklink_session(self):
        with patch('set_handler.BrickLinkAPI') as mock_cls:
            mock_cls.return_value = MagicMock()
            SetHandler(set_num='1-1', set_list=None, multi_sheet=False,
                       config_file='config.ini')
        mock_cls.assert_called_once_with('config.ini')

    def test_bricklink_session_stored(self):
        h, mock_session = make_handler(set_num='75192-1')
        assert h.bricklink_session is mock_session


# ═══════════════════════════════════════════════════════════════════════════════
# SetHandler.set_handler — single set mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetHandlerSingleSet:
    def test_returns_sets_dict(self):
        h, session = make_handler(set_num='75192-1')
        session.getSets.return_value = SAMPLE_SETS
        result = h.set_handler()
        assert result == SAMPLE_SETS

    def test_calls_processSet_with_set_number(self):
        h, session = make_handler(set_num='75192-1')
        session.getSets.return_value = SAMPLE_SETS
        h.set_handler()
        session.processSet.assert_called_once_with('75192-1')

    def test_calls_print_details_for_each_set(self):
        h, session = make_handler(set_num='75192-1')
        session.getSets.return_value = SAMPLE_SETS
        h.set_handler()
        session.print_details.assert_called_once_with(SAMPLE_SETS['75192-1'], '75192-1')

    def test_returns_none_when_processSet_raises(self):
        h, session = make_handler(set_num='75192-1')
        session.processSet.side_effect = Exception('API error')
        result = h.set_handler()
        assert result is None

    def test_exception_does_not_propagate(self):
        h, session = make_handler(set_num='75192-1')
        session.processSet.side_effect = RuntimeError('timeout')
        h.set_handler()  # should not raise

    def test_set_list_not_processed_when_set_number_given(self, tmp_path):
        set_file = tmp_path / 'sets.txt'
        set_file.write_text('10698-1\n')
        h, session = make_handler(set_num='75192-1', set_list=str(set_file))
        session.getSets.return_value = SAMPLE_SETS
        h.set_handler()
        session.processSet.assert_called_once_with('75192-1')


# ═══════════════════════════════════════════════════════════════════════════════
# SetHandler.set_handler — file mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetHandlerFileMode:
    def setup_method(self):
        """Reset the generate_sheets mock before each test to prevent call count bleed."""
        sys.modules['generate_sheets'].reset_mock()

    def _make_set_file(self, tmp_path, content='75192-1\n10698-1\n'):
        path = tmp_path / 'sets.txt'
        path.write_text(content)
        return str(path)

    def test_returns_sets_dict(self, tmp_path):
        path = self._make_set_file(tmp_path)
        h, session = make_handler(set_list=path)
        session.getSets.return_value = SAMPLE_SETS
        sys.modules['generate_sheets'].create_wookbook_and_sheet.return_value = (MagicMock(), MagicMock())
        result = h.set_handler()
        assert result == SAMPLE_SETS

    def test_calls_processSet_for_each_line(self, tmp_path):
        path = self._make_set_file(tmp_path, '75192-1\n10698-1\n')
        h, session = make_handler(set_list=path)
        session.getSets.return_value = SAMPLE_SETS
        sys.modules['generate_sheets'].create_wookbook_and_sheet.return_value = (MagicMock(), MagicMock())
        h.set_handler()
        assert session.processSet.call_count == 2
        session.processSet.assert_any_call('75192-1')
        session.processSet.assert_any_call('10698-1')

    def test_single_sheet_mode_calls_correct_sheet_functions(self, tmp_path):
        path = self._make_set_file(tmp_path)
        h, session = make_handler(set_list=path, multi_sheet=False)
        session.getSets.return_value = SAMPLE_SETS
        mock_workbook  = MagicMock()
        mock_worksheet = MagicMock()
        sheets = sys.modules['generate_sheets']
        sheets.create_wookbook_and_sheet.return_value = (mock_workbook, mock_worksheet)

        h.set_handler()

        sheets.create_wookbook_and_sheet.assert_called_once_with(h.output_file)
        sheets.generate_single_sheet.assert_called_once_with(SAMPLE_SETS, mock_workbook, mock_worksheet)
        mock_workbook.save.assert_called_once_with(filename=h.output_file)

    def test_multi_sheet_mode_calls_correct_sheet_functions(self, tmp_path):
        path = self._make_set_file(tmp_path)
        h, session = make_handler(set_list=path, multi_sheet=True)
        session.getSets.return_value = SAMPLE_SETS
        mock_workbook = MagicMock()
        sheets = sys.modules['generate_sheets']
        sheets.create_wookbook.return_value = mock_workbook

        h.set_handler()

        sheets.create_wookbook.assert_called_once_with(h.output_file)
        sheets.generate_multi_sheet.assert_called_once_with(SAMPLE_SETS, mock_workbook)
        mock_workbook.save.assert_called_once_with(filename=h.output_file)

    def test_returns_none_when_file_does_not_exist(self, tmp_path):
        h, session = make_handler(set_list=str(tmp_path / 'missing.txt'))
        result = h.set_handler()
        assert result is None
        session.processSet.assert_not_called()

    def test_skips_blank_lines_in_file(self, tmp_path):
        path = self._make_set_file(tmp_path, '75192-1\n\n10698-1\n')
        h, session = make_handler(set_list=path)
        session.getSets.return_value = SAMPLE_SETS
        sys.modules['generate_sheets'].create_wookbook_and_sheet.return_value = (MagicMock(), MagicMock())
        h.set_handler()
        session.processSet.assert_any_call('75192-1')
        session.processSet.assert_any_call('10698-1')

    def test_returns_none_when_no_set_num_and_no_set_list(self):
        h, _ = make_handler()
        result = h.set_handler()
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# SetHandler.test_config
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetHandlerTestConfig:
    def test_returns_true_when_api_returns_data(self):
        h, session = make_handler(set_num='75192-1')
        session.getDetails.return_value = {'name': 'Clone Trooper'}
        assert h.test_config() is True

    def test_returns_false_when_api_returns_none(self):
        h, session = make_handler(set_num='75192-1')
        session.getDetails.return_value = None
        assert h.test_config() is False

    def test_returns_false_when_api_returns_empty_dict(self):
        h, session = make_handler(set_num='75192-1')
        session.getDetails.return_value = {}
        assert h.test_config() is False

    def test_calls_getDetails_with_correct_set_number(self):
        h, session = make_handler(set_num='75192-1')
        session.getDetails.return_value = {'name': 'Test'}
        h.test_config()
        session.getDetails.assert_called_once_with('75105-1')