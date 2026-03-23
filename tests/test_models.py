"""
tests/test_models.py — Tests for SQLAlchemy models in models.py

Uses an in-memory SQLite database so no files are created on disk.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Set, SetPrice, Inventory


@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════════════════════
# Set model
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetModel:
    def test_create_set(self, session):
        s = Set(set_number='75192-1', name='Millennium Falcon',
                category='Star Wars', year=2017)
        session.add(s)
        session.commit()
        assert session.query(Set).count() == 1

    def test_set_number_unique(self, session):
        session.add(Set(set_number='75192-1', name='Falcon'))
        session.commit()
        session.add(Set(set_number='75192-1', name='Duplicate'))
        with pytest.raises(Exception):
            session.commit()

    def test_latest_price_none_when_no_prices(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.commit()
        assert s.latest_price is None

    def test_latest_price_returns_most_recent(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.flush()
        older = SetPrice(set_id=s.id, fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                         cur_avg=400)
        newer = SetPrice(set_id=s.id, fetched_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                         cur_avg=500)
        session.add_all([older, newer])
        session.commit()
        # Refresh to load relationship
        session.expire(s)
        assert s.latest_price.cur_avg == 500

    def test_repr(self, session):
        s = Set(set_number='75192-1', name='Falcon')
        assert '75192-1' in repr(s)

    def test_cascade_delete_prices(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.flush()
        session.add(SetPrice(set_id=s.id, cur_avg=400))
        session.commit()
        session.delete(s)
        session.commit()
        assert session.query(SetPrice).count() == 0

    def test_cascade_delete_inventory(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.flush()
        session.add(Inventory(set_id=s.id, quantity=2))
        session.commit()
        session.delete(s)
        session.commit()
        assert session.query(Inventory).count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SetPrice model
# ═══════════════════════════════════════════════════════════════════════════════

class TestSetPriceModel:
    def _set(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.flush()
        return s

    def test_create_price_snapshot(self, session):
        s = self._set(session)
        p = SetPrice(set_id=s.id, cur_avg=450, cur_max=800,
                     cur_min=350, cur_qty=5, cur_currency='USD',
                     prev_avg=400, prev_max=750, prev_min=300,
                     prev_qty=12, prev_currency='USD',
                     prev_last_sale_date='2024-06-15T10:00:00.000Z')
        session.add(p)
        session.commit()
        assert session.query(SetPrice).count() == 1

    def test_fetched_at_defaults_to_now(self, session):
        s = self._set(session)
        before = datetime.now(timezone.utc)
        p = SetPrice(set_id=s.id)
        session.add(p)
        session.commit()
        assert p.fetched_at >= before

    def test_repr(self, session):
        s = self._set(session)
        p = SetPrice(set_id=s.id)
        session.add(p)
        session.flush()
        assert 'SetPrice' in repr(p)


# ═══════════════════════════════════════════════════════════════════════════════
# Inventory model
# ═══════════════════════════════════════════════════════════════════════════════

class TestInventoryModel:
    def _set(self, session):
        s = Set(set_number='75192-1')
        session.add(s)
        session.flush()
        return s

    def test_create_inventory_row(self, session):
        s = self._set(session)
        inv = Inventory(set_id=s.id, quantity=1)
        session.add(inv)
        session.commit()
        assert session.query(Inventory).count() == 1

    def test_default_quantity_is_one(self, session):
        s = self._set(session)
        inv = Inventory(set_id=s.id)
        session.add(inv)
        session.commit()
        assert inv.quantity == 1

    def test_unique_constraint_on_set_id(self, session):
        s = self._set(session)
        session.add(Inventory(set_id=s.id, quantity=1))
        session.commit()
        session.add(Inventory(set_id=s.id, quantity=1))
        with pytest.raises(Exception):
            session.commit()

    def test_added_at_defaults_to_now(self, session):
        s = self._set(session)
        before = datetime.now(timezone.utc)
        inv = Inventory(set_id=s.id)
        session.add(inv)
        session.commit()
        added = inv.added_at
        if added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)
        assert added >= before

    def test_repr(self, session):
        s = self._set(session)
        inv = Inventory(set_id=s.id, quantity=3)
        session.add(inv)
        session.flush()
        assert 'Inventory' in repr(inv)
        assert '3' in repr(inv)