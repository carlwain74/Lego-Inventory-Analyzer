"""
models.py — SQLAlchemy ORM models.

Three tables:
  sets        — Bricklink set metadata (shared cache, one row per set number)
  set_prices  — Price snapshots per set (append-only, newest used for display)
  inventory   — User's owned sets with quantity tracking
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _now():
    return datetime.now(timezone.utc)


class Set(Base):
    """Bricklink set metadata cache."""
    __tablename__ = 'sets'

    id           = Column(Integer, primary_key=True)
    set_number   = Column(String, nullable=False, unique=True)
    name         = Column(String)
    category     = Column(String)
    year         = Column(Integer)
    image        = Column(Text)
    thumbnail    = Column(Text)
    last_fetched = Column(DateTime(timezone=True))

    prices    = relationship('SetPrice', back_populates='set',
                             order_by='SetPrice.fetched_at.desc()',
                             cascade='all, delete-orphan',
                             lazy='joined')
    inventory = relationship('Inventory', back_populates='set',
                             cascade='all, delete-orphan',
                             lazy='joined')

    @property
    def latest_price(self):
        """Return the most recent SetPrice snapshot, or None."""
        return self.prices[0] if self.prices else None

    def __repr__(self):
        return f'<Set {self.set_number} "{self.name}">'


class SetPrice(Base):
    """Append-only price snapshot for a set."""
    __tablename__ = 'set_prices'

    id            = Column(Integer, primary_key=True)
    set_id        = Column(Integer, ForeignKey('sets.id'), nullable=False)
    fetched_at    = Column(DateTime(timezone=True), default=_now, nullable=False)

    cur_avg       = Column(Integer)
    cur_max       = Column(Integer)
    cur_min       = Column(Integer)
    cur_qty       = Column(Integer)
    cur_currency  = Column(String)

    prev_avg      = Column(Integer)
    prev_max      = Column(Integer)
    prev_min      = Column(Integer)
    prev_qty      = Column(Integer)
    prev_currency = Column(String)
    prev_last_sale_date = Column(String)

    set = relationship('Set', back_populates='prices')

    def __repr__(self):
        return f'<SetPrice set_id={self.set_id} fetched_at={self.fetched_at}>'


class Inventory(Base):
    """A set owned by the user, with quantity tracking."""
    __tablename__ = 'inventory'

    id         = Column(Integer, primary_key=True)
    set_id     = Column(Integer, ForeignKey('sets.id'), nullable=False)
    quantity   = Column(Integer, nullable=False, default=1)
    added_at   = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now,
                        onupdate=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('set_id', name='uq_inventory_set'),
    )

    set = relationship('Set', back_populates='inventory')

    def __repr__(self):
        return f'<Inventory set_id={self.set_id} qty={self.quantity}>'