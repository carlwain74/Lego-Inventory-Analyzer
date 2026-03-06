"""
tests/test_app.py — pytest suite for app.py

Run from the project root:
    pip install pytest flask
    pytest tests/test_app.py -v

generate_sheets is stubbed in conftest.py so no real Bricklink credentials
are needed.
"""

import io
import os
import configparser
import pytest
from unittest.mock import patch, MagicMock

import app as flask_app

# Grab the stub that conftest registered
import sys
_gs_stub = sys.modules['generate_sheets']


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, 'CONFIG_PATH', str(tmp_path / 'config.ini'))
    flask_app.app.config['TESTING'] = True
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / 'config.ini'
    monkeypatch.setattr(flask_app, 'CONFIG_PATH', str(path))
    return path


@pytest.fixture(autouse=True)
def reset_gs_stub():
    _gs_stub.sheet_handler.reset_mock()
    _gs_stub.sheet_handler.side_effect = None
    _gs_stub.test_config.reset_mock()
    _gs_stub.test_config.return_value = True
    _gs_stub.test_config.side_effect  = None
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# GET /
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndex:
    def test_returns_200(self, client):
        assert client.get('/').status_code == 200

    def test_content_type_is_html(self, client):
        assert 'text/html' in client.get('/').content_type

    def test_contains_app_title(self, client):
        assert b'Lego Inventory' in client.get('/').data


# ═══════════════════════════════════════════════════════════════════════════════
# capture_output
# ═══════════════════════════════════════════════════════════════════════════════

class TestCaptureOutput:
    def test_captures_info_log_messages(self):
        import logging
        output = flask_app.capture_output(lambda: logging.getLogger().info('hello'))
        assert 'hello' in output

    def test_does_not_capture_debug_messages(self):
        import logging
        output = flask_app.capture_output(lambda: (
            logging.getLogger().debug('hidden'),
            logging.getLogger().info('shown'),
        ))
        assert 'hidden' not in output
        assert 'shown'  in output

    def test_restores_logger_level_after_call(self):
        import logging
        before = logging.getLogger().level
        flask_app.capture_output(lambda: None)
        assert logging.getLogger().level == before

    def test_restores_handlers_on_exception(self):
        import logging
        before = list(logging.getLogger().handlers)
        with pytest.raises(RuntimeError):
            flask_app.capture_output(lambda: (_ for _ in ()).throw(RuntimeError('boom')))
        assert logging.getLogger().handlers == before

    def test_returns_empty_string_for_no_output(self):
        assert flask_app.capture_output(lambda: None) == ''


# ═══════════════════════════════════════════════════════════════════════════════
# POST /generate — set mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateSetMode:
    def _post(self, client, set_number):
        return client.post('/generate', data={'mode': 'set', 'set_number': set_number})

    def test_empty_set_number_returns_400(self, client):
        r = self._post(client, '')
        assert r.status_code == 400
        assert 'error' in r.get_json()

    @pytest.mark.parametrize('bad', ['abc', '75192', 'XXXXX-1', '123-', '-1', '75 192-1'])
    def test_invalid_format_returns_400(self, client, bad):
        assert self._post(client, bad).status_code == 400

    @pytest.mark.parametrize('good', ['75192-1', '1-1', '123456-2', '10698-1'])
    def test_valid_format_returns_200(self, client, good):
        with patch.object(flask_app, 'capture_output', return_value='Item: ' + good):
            assert self._post(client, good).status_code == 200

    def test_output_returned_in_response(self, client):
        with patch.object(flask_app, 'capture_output', return_value='Item: 75192-1\nName: Falcon'):
            r = self._post(client, '75192-1')
        assert 'Item: 75192-1' in r.get_json()['output']

    def test_empty_output_returns_placeholder(self, client):
        with patch.object(flask_app, 'capture_output', return_value=''):
            r = self._post(client, '75192-1')
        assert r.get_json()['output'] == '(No output returned)'

    def test_exception_returns_error_json(self, client):
        with patch.object(flask_app, 'capture_output', side_effect=RuntimeError('API down')):
            r = self._post(client, '75192-1')
        assert 'API down' in r.get_json()['error']

    def test_set_number_passed_to_capture_output(self, client):
        with patch.object(flask_app, 'capture_output', return_value='ok') as mock_cap:
            self._post(client, '75192-1')
        assert mock_cap.call_args[1]['set_num'] == '75192-1'


# ═══════════════════════════════════════════════════════════════════════════════
# POST /generate — file mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateFileMode:
    def _post(self, client, content=b'75192-1\n', multi_sheet='false'):
        return client.post('/generate', data={
            'mode':        'file',
            'multi_sheet': multi_sheet,
            'set_file':    (io.BytesIO(content), 'sets.txt'),
        }, content_type='multipart/form-data')

    def test_missing_file_returns_400(self, client):
        assert client.post('/generate', data={'mode': 'file'}).status_code == 400

    def test_valid_upload_returns_200(self, client):
        with patch.object(flask_app, 'capture_output', return_value='Item: 75192-1\n'):
            assert self._post(client).status_code == 200

    def test_multi_sheet_true_forwarded(self, client):
        captured = {}
        def spy(fn, **kw): captured.update(kw); return 'ok'
        with patch.object(flask_app, 'capture_output', side_effect=spy):
            self._post(client, multi_sheet='true')
        assert captured['multi_sheet'] is True

    def test_multi_sheet_false_forwarded(self, client):
        captured = {}
        def spy(fn, **kw): captured.update(kw); return 'ok'
        with patch.object(flask_app, 'capture_output', side_effect=spy):
            self._post(client, multi_sheet='false')
        assert captured['multi_sheet'] is False

    def test_temp_file_deleted_after_success(self, client):
        paths = []
        def spy(fn, **kw):
            if kw.get('set_list'): paths.append(kw['set_list'])
            return 'ok'
        with patch.object(flask_app, 'capture_output', side_effect=spy):
            self._post(client)
        assert paths and not any(os.path.exists(p) for p in paths)

    def test_temp_file_deleted_after_exception(self, client):
        paths = []
        def spy(fn, **kw):
            if kw.get('set_list'): paths.append(kw['set_list'])
            raise RuntimeError('crash')
        with patch.object(flask_app, 'capture_output', side_effect=spy):
            self._post(client)
        assert paths and not any(os.path.exists(p) for p in paths)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /generate — invalid mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateInvalidMode:
    @pytest.mark.parametrize('mode', ['', 'unknown', 'SET', 'FILE'])
    def test_returns_400(self, client, mode):
        r = client.post('/generate', data={'mode': mode})
        assert r.status_code == 400
        assert 'error' in r.get_json()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /settings
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSettings:
    def test_all_false_when_config_absent(self, client):
        data = client.get('/settings').get_json()
        assert data == {k: False for k in
                        ('consumer_key', 'consumer_secret', 'token_value', 'token_secret')}

    def test_true_only_for_populated_keys(self, client, config_path):
        config_path.write_text(
            '[secrets]\nconsumer_key = abc\nconsumer_secret = \n'
            'token_value = xyz\ntoken_secret = \n'
        )
        data = client.get('/settings').get_json()
        assert data['consumer_key']    is True
        assert data['consumer_secret'] is False
        assert data['token_value']     is True
        assert data['token_secret']    is False

    def test_whitespace_only_value_is_false(self, client, config_path):
        config_path.write_text('[secrets]\nconsumer_key =    \n')
        assert client.get('/settings').get_json()['consumer_key'] is False

    def test_secret_values_never_returned(self, client, config_path):
        config_path.write_text('[secrets]\nconsumer_key = supersecret123\n')
        assert b'supersecret123' not in client.get('/settings').data

    def test_missing_secrets_section_returns_all_false(self, client, config_path):
        config_path.write_text('[other]\nfoo = bar\n')
        assert all(v is False for v in client.get('/settings').get_json().values())


# ═══════════════════════════════════════════════════════════════════════════════
# POST /settings
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveSettings:
    def test_saves_all_four_fields(self, client, config_path):
        client.post('/settings', json={
            'consumer_key': 'ck', 'consumer_secret': 'cs',
            'token_value':  'tv', 'token_secret':    'ts',
        })
        cfg = configparser.ConfigParser()
        cfg.read(str(config_path))
        assert cfg['secrets']['consumer_key']    == 'ck'
        assert cfg['secrets']['consumer_secret'] == 'cs'
        assert cfg['secrets']['token_value']     == 'tv'
        assert cfg['secrets']['token_secret']    == 'ts'

    def test_returns_ok_true(self, client):
        assert client.post('/settings', json={'consumer_key': 'x'}).get_json()['ok'] is True

    def test_empty_field_preserves_existing_value(self, client, config_path):
        config_path.write_text('[secrets]\nconsumer_key = original\n')
        client.post('/settings', json={'consumer_key': '', 'consumer_secret': 'new'})
        cfg = configparser.ConfigParser()
        cfg.read(str(config_path))
        assert cfg['secrets']['consumer_key']    == 'original'
        assert cfg['secrets']['consumer_secret'] == 'new'

    def test_whitespace_only_not_saved(self, client, config_path):
        config_path.write_text('[secrets]\nconsumer_key = real\n')
        client.post('/settings', json={'consumer_key': '   '})
        cfg = configparser.ConfigParser()
        cfg.read(str(config_path))
        assert cfg['secrets']['consumer_key'] == 'real'

    def test_no_body_returns_400(self, client):
        assert client.post('/settings', data='', content_type='application/json').status_code == 400

    def test_creates_config_if_absent(self, client, config_path):
        assert not config_path.exists()
        client.post('/settings', json={'consumer_key': 'ck'})
        assert config_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /settings/test
# ═══════════════════════════════════════════════════════════════════════════════

class TestTestConnection:
    def test_ok_true_on_success(self, client):
        _gs_stub.test_config.return_value = True
        assert client.post('/settings/test', json={}).get_json()['ok'] is True

    def test_ok_false_on_failure(self, client):
        _gs_stub.test_config.return_value = False
        assert client.post('/settings/test', json={}).get_json()['ok'] is False

    def test_ok_false_and_error_message_on_exception(self, client):
        _gs_stub.test_config.side_effect = Exception('timeout')
        data = client.post('/settings/test', json={}).get_json()
        assert data['ok'] is False
        assert 'timeout' in data.get('error', '')

    def test_config_restored_after_success(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        _gs_stub.test_config.return_value = True
        client.post('/settings/test', json={'consumer_key': 'temp'})
        assert config_path.read_text() == original

    def test_config_restored_after_failure(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        _gs_stub.test_config.return_value = False
        client.post('/settings/test', json={'consumer_key': 'temp'})
        assert config_path.read_text() == original

    def test_config_restored_after_exception(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        _gs_stub.test_config.side_effect = Exception('crash')
        client.post('/settings/test', json={'consumer_key': 'temp'})
        assert config_path.read_text() == original

    def test_config_not_created_if_absent(self, client, config_path):
        assert not config_path.exists()
        client.post('/settings/test', json={'consumer_key': 'ck'})
        assert not config_path.exists()

    def test_submitted_values_visible_during_test(self, client, config_path):
        config_path.write_text('[secrets]\nconsumer_key = existing\n')
        seen = []
        def capture():
            cfg = configparser.ConfigParser()
            cfg.read(str(config_path))
            seen.append(dict(cfg['secrets']))
            return True
        _gs_stub.test_config.side_effect = capture
        client.post('/settings/test', json={'consumer_secret': 'new_secret'})
        assert seen[0]['consumer_secret'] == 'new_secret'
        assert seen[0]['consumer_key']    == 'existing'


# ═══════════════════════════════════════════════════════════════════════════════
# GET /download
# ═══════════════════════════════════════════════════════════════════════════════

class TestDownload:
    def test_404_when_file_absent(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(os.path, 'dirname', lambda _: str(tmp_path))
        r = client.get('/download')
        assert r.status_code == 404
        assert 'error' in r.get_json()

    def test_200_with_spreadsheet_mimetype(self, client, tmp_path, monkeypatch):
        (tmp_path / 'Sets.xlsx').write_bytes(b'PK\x03\x04fake')
        monkeypatch.setattr(os.path, 'dirname', lambda _: str(tmp_path))
        r = client.get('/download')
        assert r.status_code == 200
        assert 'spreadsheetml' in r.content_type

    def test_content_disposition_is_attachment(self, client, tmp_path, monkeypatch):
        (tmp_path / 'Sets.xlsx').write_bytes(b'PK\x03\x04fake')
        monkeypatch.setattr(os.path, 'dirname', lambda _: str(tmp_path))
        r = client.get('/download')
        assert 'attachment' in r.headers.get('Content-Disposition', '')