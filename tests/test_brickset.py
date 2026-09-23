"""
tests/test_brickset.py — pytest suite for brickset.py

BrickSetAPI.get_retail_price_usd() imports the third-party `brickse`
package lazily inside the method, so it's stubbed via sys.modules rather
than patched at import time.
"""

import sys
import json
import pytest
from unittest.mock import MagicMock

sys.modules.pop('brickset', None)
from brickset import BrickSetAPI  # noqa: E402


def make_config(tmp_path, section=True, api_key='bs-key-123'):
    cfg = tmp_path / 'config.ini'
    if section:
        cfg.write_text(f'[bricklink]\napi_key = {api_key}\n')
    else:
        cfg.write_text('[secrets]\nconsumer_key = ck\n')
    return str(cfg)


def make_response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode('utf8')
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# BrickSetAPI.__init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrickSetAPIInit:
    def test_reads_api_key_from_config(self, tmp_path):
        api = BrickSetAPI(make_config(tmp_path))
        assert api.api_key == 'bs-key-123'

    def test_none_when_section_missing(self, tmp_path):
        api = BrickSetAPI(make_config(tmp_path, section=False))
        assert api.api_key is None

    def test_none_when_config_file_missing(self, tmp_path):
        api = BrickSetAPI(str(tmp_path / 'missing.ini'))
        assert api.api_key is None

    def test_none_when_key_blank(self, tmp_path):
        api = BrickSetAPI(make_config(tmp_path, api_key=''))
        assert api.api_key is None


# ═══════════════════════════════════════════════════════════════════════════════
# BrickSetAPI.get_retail_price_usd
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRetailPriceUsd:
    def test_returns_none_without_api_key(self, tmp_path):
        api = BrickSetAPI(make_config(tmp_path, section=False))
        assert api.get_retail_price_usd('75192-1') is None

    def test_returns_none_when_brickse_not_installed(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        monkeypatch.delitem(sys.modules, 'brickse', raising=False)
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'brickse':
                raise ImportError('no module named brickse')
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', fake_import)
        assert api.get_retail_price_usd('75192-1') is None

    def test_returns_price_for_matching_set(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.return_value = make_response({
            'status': 'success',
            'matches': 1,
            'sets': [{'LEGOCom': {'US': {'retailPrice': '849.99'}}}],
        })
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        price = api.get_retail_price_usd('75192-1')

        assert price == 849.99
        mock_brickse.init.assert_called_once_with('bs-key-123')
        mock_brickse.lego.get_set.assert_called_once_with(set_number='75192-1', extended_data=True)

    def test_returns_none_when_no_sets_matched(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.return_value = make_response({'status': 'success', 'matches': 0, 'sets': []})
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        assert api.get_retail_price_usd('99999-1') is None

    def test_returns_none_when_status_is_error(self, tmp_path, monkeypatch, caplog):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.return_value = make_response({
            'status': 'error', 'message': 'INVALID_APIKEY',
        })
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        with caplog.at_level('WARNING'):
            assert api.get_retail_price_usd('75192-1') is None
        assert 'INVALID_APIKEY' in caplog.text

    def test_returns_none_when_retail_price_missing(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.return_value = make_response({
            'status': 'success', 'matches': 1, 'sets': [{'LEGOCom': {'US': {}}}],
        })
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        assert api.get_retail_price_usd('75192-1') is None

    def test_returns_none_when_retail_price_not_numeric(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.return_value = make_response({
            'status': 'success', 'matches': 1,
            'sets': [{'LEGOCom': {'US': {'retailPrice': 'n/a'}}}],
        })
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        assert api.get_retail_price_usd('75192-1') is None

    def test_returns_none_when_request_raises(self, tmp_path, monkeypatch):
        api = BrickSetAPI(make_config(tmp_path))
        mock_brickse = MagicMock()
        mock_brickse.lego.get_set.side_effect = Exception('network error')
        monkeypatch.setitem(sys.modules, 'brickse', mock_brickse)

        assert api.get_retail_price_usd('75192-1') is None
