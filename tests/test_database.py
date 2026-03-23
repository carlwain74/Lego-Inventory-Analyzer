"""
tests/test_database.py — Tests for database helper functions in database.py

Uses a temp file SQLite database per test via the fresh_db fixture.
conftest.py stubs models and database for app.py isolation — we pop those
stubs here and reload the real modules before any test runs.
"""

import sys
import os
import pytest
from datetime import datetime, timezone, timedelta

# ── Ensure project root is on sys.path ───────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Remove conftest stubs and load real modules ───────────────────────────────
for _mod in ('database', 'models'):
    sys.modules.pop(_mod, None)

from models import Base, Set, SetPrice, Inventory  # noqa: E402
import database                                     # noqa: E402
from database import (                              # noqa: E402
    init_db, get_session, is_price_stale,
    upsert_set, upsert_inventory, decrement_inventory, set_to_dict,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Initialise a fresh SQLite DB for each test and tear down after."""
    db_path = str(tmp_path / 'test.db')
    init_db(db_path)
    yield
    database._engine       = None
    database._SessionLocal = None


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


# ═══════════════════════════════════════════════════════════════════════════════
# init_db
# ═══════════════════════════════════════════════════════════════════════════════

class TestInitDb:
    def test_creates_tables(self):
        with get_session() as s:
            assert s.query(Set).count() == 0

    def test_raises_if_not_initialised(self, tmp_path):
        database._SessionLocal = None
        with pytest.raises(RuntimeError, match='not initialised'):
            with get_session() as s:
                pass
        init_db(str(tmp_path / 'reinit.db'))


# ═══════════════════════════════════════════════════════════════════════════════
# get_session
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSession:
    def test_commits_on_success(self):
        with get_session() as s:
            s.add(Set(set_number='75192-1', name='Falcon'))
        with get_session() as s:
            assert s.query(Set).filter_by(set_number='75192-1').count() == 1

    def test_rolls_back_on_exception(self):
        with pytest.raises(ValueError):
            with get_session() as s:
                s.add(Set(set_number='75192-1', name='Falcon'))
                raise ValueError('intentional')
        with get_session() as s:
            assert s.query(Set).count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# is_price_stale
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsPriceStale:
    def test_stale_when_no_last_fetched(self):
        s = Set(set_number='75192-1')
        assert is_price_stale(s) is True

    def test_fresh_when_fetched_recently(self):
        s = Set(set_number='75192-1',
                last_fetched=datetime.now(timezone.utc) - timedelta(hours=1))
        assert is_price_stale(s) is False

    def test_stale_when_fetched_over_ttl_ago(self):
        s = Set(set_number='75192-1',
                last_fetched=datetime.now(timezone.utc) - timedelta(hours=25))
        assert is_price_stale(s) is True

    def test_handles_naive_datetime(self):
        s = Set(set_number='75192-1',
                last_fetched=datetime.utcnow() - timedelta(hours=1))
        assert is_price_stale(s) is False


# ═══════════════════════════════════════════════════════════════════════════════
# upsert_set
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpsertSet:
    def test_creates_new_set_row(self):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            assert s.query(Set).filter_by(set_number='75192-1').count() == 1

    def test_updates_existing_set_row(self):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        updated = {**SAMPLE_DATA, 'name': 'Updated Falcon'}
        with get_session() as s:
            upsert_set(s, updated)
        with get_session() as s:
            row = s.query(Set).filter_by(set_number='75192-1').first()
            assert row.name == 'Updated Falcon'

    def test_appends_new_price_snapshot_each_call(self):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            assert s.query(SetPrice).count() == 2

    def test_price_fields_stored_correctly(self):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            price = s.query(SetPrice).first()
            assert price.cur_avg      == 450
            assert price.cur_max      == 800
            assert price.cur_currency == 'USD'
            assert price.prev_last_sale_date == '2024-06-15T10:00:00.000Z'

    def test_last_fetched_updated(self):
        before = datetime.now(timezone.utc)
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            row = s.query(Set).filter_by(set_number='75192-1').first()
            fetched = row.last_fetched
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            assert fetched >= before


# ═══════════════════════════════════════════════════════════════════════════════
# upsert_inventory
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpsertInventory:
    def _make_set(self, session):
        return upsert_set(session, SAMPLE_DATA)

    def test_creates_inventory_row_first_import(self):
        with get_session() as s:
            set_row = self._make_set(s)
            upsert_inventory(s, set_row)
        with get_session() as s:
            assert s.query(Inventory).count() == 1
            assert s.query(Inventory).first().quantity == 1

    def test_increments_quantity_on_duplicate_import(self):
        with get_session() as s:
            set_row = self._make_set(s)
            upsert_inventory(s, set_row)
        with get_session() as s:
            set_row = s.query(Set).filter_by(set_number='75192-1').first()
            upsert_inventory(s, set_row)
        with get_session() as s:
            assert s.query(Inventory).first().quantity == 2

    def test_three_imports_gives_quantity_three(self):
        for _ in range(3):
            with get_session() as s:
                set_row = s.query(Set).filter_by(set_number='75192-1').first()
                if set_row is None:
                    set_row = self._make_set(s)
                upsert_inventory(s, set_row)
        with get_session() as s:
            assert s.query(Inventory).first().quantity == 3


# ═══════════════════════════════════════════════════════════════════════════════
# decrement_inventory
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecrementInventory:
    def _setup(self, quantity=2):
        with get_session() as s:
            set_row = upsert_set(s, SAMPLE_DATA)
            s.flush()
            s.add(Inventory(set_id=set_row.id, quantity=quantity))

    def test_decrements_quantity(self):
        self._setup(quantity=3)
        with get_session() as s:
            set_row = s.query(Set).first()
            result = decrement_inventory(s, set_row.id)
        assert result.quantity == 2

    def test_deletes_row_when_quantity_reaches_zero(self):
        self._setup(quantity=1)
        with get_session() as s:
            set_row = s.query(Set).first()
            decrement_inventory(s, set_row.id)
        with get_session() as s:
            assert s.query(Inventory).count() == 0

    def test_returns_none_when_deleted(self):
        self._setup(quantity=1)
        with get_session() as s:
            set_row = s.query(Set).first()
            result = decrement_inventory(s, set_row.id)
        assert result is None

    def test_returns_none_for_unknown_set(self):
        with get_session() as s:
            result = decrement_inventory(s, 99999)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# set_to_dict
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetToDict:
    def _setup(self, quantity=1):
        """Seed DB and return set_to_dict result while session is still open."""
        with get_session() as s:
            set_row = upsert_set(s, SAMPLE_DATA)
            s.flush()
            s.add(Inventory(set_id=set_row.id, quantity=quantity))
        # Call set_to_dict inside a fresh session so relationships can load
        with get_session() as s:
            row = s.query(Set).filter_by(set_number='75192-1').first()
            return set_to_dict(row)

    def test_returns_correct_set_number(self):
        assert self._setup()['set_number'] == '75192-1'

    def test_returns_correct_name(self):
        assert self._setup()['name'] == 'Millennium Falcon'

    def test_returns_quantity(self):
        assert self._setup(quantity=3)['quantity'] == 3

    def test_returns_current_prices(self):
        d = self._setup()
        assert d['current']['avg'] == 450
        assert d['current']['currency'] == 'USD'

    def test_returns_past_prices(self):
        d = self._setup()
        assert d['past']['avg'] == 400
        assert d['past']['last_sale_date'] == '2024-06-15T10:00:00.000Z'

    def test_zero_quantity_when_not_in_inventory(self):
        with get_session() as s:
            upsert_set(s, SAMPLE_DATA)
        with get_session() as s:
            row = s.query(Set).filter_by(set_number='75192-1').first()
            result = set_to_dict(row)
        assert result['quantity'] == 0

    def test_last_fetched_is_iso_string(self):
        assert isinstance(self._setup()['last_fetched'], str)