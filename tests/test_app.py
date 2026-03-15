"""
tests/test_app.py — pytest suite for app.py

Run from the project root:
    pipenv sync --dev
    pipenv run pytest tests/test_app.py -v

set_handler is stubbed in conftest.py so no real Bricklink credentials
are needed.
"""

import io
import os
import configparser
import pytest
from unittest.mock import patch

import app as flask_app

import sys
_sh_stub      = sys.modules['set_handler']
_sh_instance  = _sh_stub.SetHandler.return_value  # the mock SetHandler instance

SAMPLE_SET = {
    '75192-1': {
        'name': 'Millennium Falcon', 'category': 'Star Wars',
        'current':  {'avg': 450, 'max': 800, 'min': 350, 'quantity': 5,  'currency': 'USD'},
        'past':     {'avg': 400, 'max': 750, 'min': 300, 'quantity': 12, 'currency': 'USD',
                     'last_sale_date': '2024-06-15T10:00:00.000Z'},
        'year': 2017,
        'image':     '//img.bricklink.com/SL/75192-1.jpg',
        'thumbnail': '//img.bricklink.com/S/75192-1.jpg',
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(flask_app, 'CONFIG_PATH', str(tmp_path / 'config.ini'))
    monkeypatch.setattr(flask_app, 'OUTPUT_DIR',  str(tmp_path))
    flask_app.app.config['TESTING'] = True
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / 'config.ini'
    monkeypatch.setattr(flask_app, 'CONFIG_PATH', str(path))
    return path


@pytest.fixture(autouse=True)
def reset_stubs():
    # Reset SetHandler constructor — use return_value/side_effect args so child
    # mocks are not wiped, then restore them explicitly below
    _sh_stub.SetHandler.side_effect  = None
    _sh_stub.SetHandler.return_value = _sh_instance

    # Reset set_handler instance method
    _sh_instance.set_handler.return_value = SAMPLE_SET
    _sh_instance.set_handler.side_effect  = None

    # Reset test_config instance method — must reset side_effect explicitly
    # because reset_mock() does not clear side_effects on child mocks by default
    _sh_instance.test_config.return_value = True
    _sh_instance.test_config.side_effect  = None

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
        _sh_instance.set_handler.return_value = {good: {'name': 'Test'}}
        assert self._post(client, good).status_code == 200

    def test_sets_returned_directly_in_response(self, client):
        _sh_instance.set_handler.return_value = SAMPLE_SET
        r = self._post(client, '75192-1')
        assert r.get_json() == SAMPLE_SET

    def test_empty_result_returns_500(self, client):
        _sh_instance.set_handler.return_value = {}
        r = self._post(client, '75192-1')
        assert r.status_code == 500
        assert 'error' in r.get_json()

    def test_exception_returns_500_with_error(self, client):
        _sh_instance.set_handler.side_effect = RuntimeError('API down')
        r = self._post(client, '75192-1')
        assert r.status_code == 500
        assert 'API down' in r.get_json()['error']

    def test_set_number_passed_to_SetHandler(self, client):
        self._post(client, '75192-1')
        assert _sh_stub.SetHandler.call_args[1]['set_num'] == '75192-1'

    def test_output_file_path_uses_output_dir(self, client, tmp_path):
        self._post(client, '75192-1')
        assert _sh_stub.SetHandler.call_args[1]['output_file'] == os.path.join(str(tmp_path), 'Sets.xlsx')

    def test_config_path_passed_to_SetHandler(self, client, tmp_path):
        self._post(client, '75192-1')
        assert _sh_stub.SetHandler.call_args[1]['config_file'] == str(tmp_path / 'config.ini')


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
        assert self._post(client).status_code == 200

    def test_result_returned_directly_in_response(self, client):
        assert self._post(client).get_json() == SAMPLE_SET

    def test_multi_sheet_true_forwarded(self, client):
        self._post(client, multi_sheet='true')
        assert _sh_stub.SetHandler.call_args[1]['multi_sheet'] is True

    def test_multi_sheet_false_forwarded(self, client):
        self._post(client, multi_sheet='false')
        assert _sh_stub.SetHandler.call_args[1]['multi_sheet'] is False

    def test_temp_file_deleted_after_success(self, client):
        paths = []
        def spy(**kw):
            path = kw.get('set_list')
            if path: paths.append(path)
            _sh_stub.SetHandler.return_value = _sh_instance
        _sh_stub.SetHandler.side_effect = spy
        self._post(client)
        assert paths and not any(os.path.exists(p) for p in paths)

    def test_temp_file_deleted_after_exception(self, client):
        paths = []
        def spy(**kw):
            path = kw.get('set_list')
            if path: paths.append(path)
            raise RuntimeError('crash')
        _sh_stub.SetHandler.side_effect = spy
        r = self._post(client)
        assert r.status_code == 500
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

    def test_empty_json_body_returns_400(self, client):
        # force=True+silent=True means Flask parses the body regardless of content-type;
        # an empty body parses to None which triggers the 400 branch
        assert client.post('/settings', data=b'', content_type='application/json').status_code == 400

    def test_malformed_json_returns_400(self, client):
        # Malformed JSON also silently returns None from get_json(force, silent)
        assert client.post('/settings', data=b'{bad json', content_type='application/json').status_code == 400

    def test_creates_config_if_absent(self, client, config_path):
        assert not config_path.exists()
        client.post('/settings', json={'consumer_key': 'ck'})
        assert config_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /settings/test
# ═══════════════════════════════════════════════════════════════════════════════

class TestTestConnection:
    def test_ok_true_on_success(self, client):
        _sh_instance.test_config.return_value = True
        assert client.post('/settings/test', json={}).get_json()['ok'] is True

    def test_ok_false_on_failure(self, client):
        _sh_instance.test_config.return_value = False
        assert client.post('/settings/test', json={}).get_json()['ok'] is False

    def test_ok_false_and_error_message_on_exception(self, client):
        _sh_instance.test_config.side_effect = Exception('timeout')
        data = client.post('/settings/test', json={}).get_json()
        assert data['ok'] is False
        assert 'timeout' in data.get('error', '')

    def test_config_restored_after_success(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        client.post('/settings/test', json={'consumer_key': 'temp'})
        assert config_path.read_text() == original

    def test_config_restored_after_failure(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        _sh_instance.test_config.return_value = False
        client.post('/settings/test', json={'consumer_key': 'temp'})
        assert config_path.read_text() == original

    def test_config_restored_after_exception(self, client, config_path):
        original = '[secrets]\nconsumer_key = original_key\n'
        config_path.write_text(original)
        _sh_instance.test_config.side_effect = Exception('crash')
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
        _sh_instance.test_config.side_effect = capture
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