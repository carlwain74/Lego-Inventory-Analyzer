"""
tests/test_inventory_routes.py — Tests for inventory and import blueprints.

conftest.py stubs database, models, and route modules for app.py isolation.
We pop all those stubs here, reload the real modules, then reimport app so
the blueprints are actually registered before the test client is created.
"""

import io
import json
import sys
import os
import pytest
from unittest.mock import patch

# ── Ensure project root is on sys.path first ─────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Pop conftest stubs so real modules load ───────────────────────────────────
# Must pop in reverse-dependency order. Keep set_handler/bricklink stubs in
# place since app.py imports SetHandler — we only want real DB/route modules.
for _mod in (
    'app',
    'routes.inventory', 'routes.import_routes', 'routes',
    'database', 'models',
):
    sys.modules.pop(_mod, None)

# ── Load real modules in dependency order ─────────────────────────────────────
from models import Base, Set, Inventory  # noqa: E402 — real models
import database                          # noqa: E402 — real database helpers
from database import (                   # noqa: E402
    init_db, get_session, upsert_set, upsert_inventory,
)

# Import routes explicitly so Python registers the package before app.py does
import routes.inventory                  # noqa: E402
import routes.import_routes              # noqa: E402

import app as flask_app                  # noqa: E402 — real blueprints registered


SAMPLE_DATA = {
    'set_number': '75192-1',
    'name':       'Millennium Falcon',
    'category':   'Star Wars',
    'year':       2017,
    'image':      '//img.bricklink.com/SL/75192-1.jpg',
    'thumbnail':  '//img.bricklink.com/S/75192-1.jpg',
    'current': {'avg': 450, 'max': 800, 'min': 350, 'quantity': 5,  'currency': 'USD'},
    'past':    {'avg': 400, 'max': 750, 'min': 300, 'quantity': 12, 'currency': 'USD',
                'last_sale_date': '2024-06-15T10:00:00.000Z'},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'test.db')
    init_db(db_path)
    monkeypatch.setattr(flask_app, 'CONFIG_PATH', str(tmp_path / 'config.ini'))
    monkeypatch.setattr(flask_app, 'OUTPUT_DIR',  str(tmp_path))
    monkeypatch.setattr(flask_app, 'APP_VERSION', '0.3.1')
    flask_app.app.config['TESTING'] = True
    with flask_app.app.test_client() as c:
        yield c
    database._engine       = None
    database._SessionLocal = None


def _seed_inventory(quantity=1):
    with get_session() as s:
        row = upsert_set(s, SAMPLE_DATA)
        s.flush()
        s.add(Inventory(set_id=row.id, quantity=quantity))


def _parse_sse(response):
    events = []
    for line in response.data.decode().splitlines():
        if line.startswith('data: '):
            events.append(json.loads(line[6:]))
    return events


# ═══════════════════════════════════════════════════════════════════════════════
# GET /inventory
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetInventory:
    def test_returns_200(self, client):
        assert client.get('/inventory').status_code == 200

    def test_empty_inventory_returns_empty_dict(self, client):
        assert client.get('/inventory').get_json() == {}

    def test_returns_set_in_inventory(self, client):
        _seed_inventory()
        assert '75192-1' in client.get('/inventory').get_json()

    def test_returns_correct_name(self, client):
        _seed_inventory()
        assert client.get('/inventory').get_json()['75192-1']['name'] == 'Millennium Falcon'

    def test_returns_quantity(self, client):
        _seed_inventory(quantity=3)
        assert client.get('/inventory').get_json()['75192-1']['quantity'] == 3

    def test_returns_price_data(self, client):
        _seed_inventory()
        assert client.get('/inventory').get_json()['75192-1']['current']['avg'] == 450


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /inventory/<set_number>
# ═══════════════════════════════════════════════════════════════════════════════

class TestRemoveSet:
    def test_404_when_set_not_in_db(self, client):
        assert client.delete('/inventory/99999-1').status_code == 404

    def test_decrements_quantity(self, client):
        _seed_inventory(quantity=3)
        r = client.delete('/inventory/75192-1').get_json()
        assert r['quantity'] == 2
        assert r['removed'] is False

    def test_removes_row_when_quantity_reaches_zero(self, client):
        _seed_inventory(quantity=1)
        r = client.delete('/inventory/75192-1').get_json()
        assert r['removed'] is True
        assert r['quantity'] == 0
        with get_session() as s:
            assert s.query(Inventory).count() == 0

    def test_set_row_remains_after_inventory_removal(self, client):
        _seed_inventory(quantity=1)
        client.delete('/inventory/75192-1')
        with get_session() as s:
            assert s.query(Set).filter_by(set_number='75192-1').count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /inventory  (clear all)
# ═══════════════════════════════════════════════════════════════════════════════

class TestClearInventory:
    def test_returns_200_on_empty_inventory(self, client):
        r = client.delete('/inventory')
        assert r.status_code == 200
        assert r.get_json()['cleared'] is True

    def test_removes_all_inventory_rows(self, client):
        _seed_inventory(quantity=2)
        with get_session() as s:
            row = upsert_set(s, {**SAMPLE_DATA, 'set_number': '10698-1'})
            s.flush()
            s.add(Inventory(set_id=row.id, quantity=1))
        client.delete('/inventory')
        with get_session() as s:
            assert s.query(Inventory).count() == 0

    def test_reports_correct_removed_count(self, client):
        _seed_inventory()
        with get_session() as s:
            row = upsert_set(s, {**SAMPLE_DATA, 'set_number': '10698-1'})
            s.flush()
            s.add(Inventory(set_id=row.id, quantity=1))
        r = client.delete('/inventory').get_json()
        assert r['removed'] == 2

    def test_set_cache_preserved_after_clear(self, client):
        _seed_inventory()
        client.delete('/inventory')
        with get_session() as s:
            assert s.query(Set).count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# POST /inventory/import  (single set)
# ═══════════════════════════════════════════════════════════════════════════════

class TestImportSingle:
    def test_missing_set_number_returns_400(self, client):
        assert client.post('/inventory/import', json={}).status_code == 400

    def test_invalid_format_returns_400(self, client):
        assert client.post('/inventory/import',
                           json={'set_number': 'bad'}).status_code == 400

    def test_successful_import_returns_200(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.status_code == 200

    def test_response_contains_set_data(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.get_json()['set']['name'] == 'Millennium Falcon'

    def test_response_contains_quantity(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.get_json()['quantity'] == 1

    def test_second_import_increments_quantity(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            client.post('/inventory/import', json={'set_number': '75192-1'})
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.get_json()['quantity'] == 2

    def test_cached_flag_true_when_fresh(self, client):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with patch('routes.import_routes.is_price_stale', return_value=False):
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.get_json()['cached'] is True

    def test_error_from_fetch_returns_500(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=(None, 'API error')):
            r = client.post('/inventory/import', json={'set_number': '75192-1'})
        assert r.status_code == 500
        assert 'API error' in r.get_json()['error']


# ═══════════════════════════════════════════════════════════════════════════════
# POST /inventory/import/bulk  (SSE)
# ═══════════════════════════════════════════════════════════════════════════════

class TestImportBulk:
    def _upload(self, client, content):
        return client.post(
            '/inventory/import/bulk',
            data={'set_file': (io.BytesIO(content), 'sets.txt')},
            content_type='multipart/form-data',
        )

    def test_missing_file_returns_400(self, client):
        assert client.post('/inventory/import/bulk').status_code == 400

    def test_empty_file_returns_done_with_error(self, client):
        r = self._upload(client, b'')
        events = _parse_sse(r)
        assert any(e.get('done') for e in events)

    def test_streams_progress_events(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = self._upload(client, b'75192-1\n10698-1\n')
        progress = [e for e in _parse_sse(r) if 'progress' in e]
        assert len(progress) == 2

    def test_total_correct_in_events(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = self._upload(client, b'75192-1\n10698-1\n')
        progress = [e for e in _parse_sse(r) if 'progress' in e]
        assert all(e['total'] == 2 for e in progress)

    def test_done_event_at_end(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = self._upload(client, b'75192-1\n')
        assert _parse_sse(r)[-1].get('done') is True

    def test_error_status_on_fetch_failure(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=(None, 'not found')):
            r = self._upload(client, b'99999-1\n')
        errors = [e for e in _parse_sse(r) if e.get('status') == 'error']
        assert len(errors) == 1
        assert 'not found' in errors[0]['message']

    def test_errors_counted_in_done_event(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=(None, 'not found')):
            r = self._upload(client, b'99999-1\n')
        done = next(e for e in _parse_sse(r) if e.get('done'))
        assert done['errors'] == 1
        assert done['imported'] == 0

    def test_skips_blank_lines(self, client):
        with patch('routes.import_routes._fetch_set',
                   return_value=({**SAMPLE_DATA}, None)):
            r = self._upload(client, b'75192-1\n\n10698-1\n')
        progress = [e for e in _parse_sse(r) if 'progress' in e]
        assert len(progress) == 2