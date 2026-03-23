"""
database.py — Database initialisation and session/upsert helpers.

Usage:
    from database import init_db, get_session, upsert_set, upsert_inventory

    init_db(db_path)          # call once at app startup
    with get_session() as s:  # use anywhere a DB operation is needed
        ...
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Set, SetPrice, Inventory

# Module-level engine and Session factory — initialised by init_db()
_engine       = None
_SessionLocal = None

PRICE_TTL_HOURS = int(os.environ.get('PRICE_TTL_HOURS', 24))


def init_db(db_path: str) -> None:
    """
    Create the SQLite engine, run CREATE TABLE IF NOT EXISTS for all models,
    and initialise the module-level session factory.

    Call once at application startup before any route is served.
    """
    global _engine, _SessionLocal

    _engine       = create_engine(f'sqlite:///{db_path}', future=True)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


@contextmanager
def get_session():
    """
    Context manager that yields a SQLAlchemy Session, commits on success
    and rolls back on exception.

        with get_session() as session:
            session.add(some_model_instance)
    """
    if _SessionLocal is None:
        raise RuntimeError('Database not initialised — call init_db() first.')
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Price freshness ───────────────────────────────────────────────────────────

def is_price_stale(set_row: Set) -> bool:
    """
    Return True if the set has no price snapshot or the newest snapshot is
    older than PRICE_TTL_HOURS.
    """
    if not set_row.last_fetched:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=PRICE_TTL_HOURS)
    # last_fetched may be stored as a naive UTC datetime from older rows
    last = set_row.last_fetched
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last < cutoff


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_set(session, set_data: dict) -> Set:
    """
    Insert a new Set row or update an existing one from the dict returned
    by SetHandler / the Bricklink API.

    set_data keys: set_number, name, category, year, image, thumbnail,
                   current{avg,max,min,quantity,currency},
                   past{avg,max,min,quantity,currency,last_sale_date}
    """
    set_number = set_data['set_number']
    row = session.query(Set).filter_by(set_number=set_number).first()

    if row is None:
        row = Set(set_number=set_number)
        session.add(row)

    row.name         = set_data.get('name')
    row.category     = set_data.get('category')
    row.year         = set_data.get('year')
    row.image        = set_data.get('image')
    row.thumbnail    = set_data.get('thumbnail')
    row.last_fetched = datetime.now(timezone.utc)

    # Append a new price snapshot
    cur  = set_data.get('current', {})
    prev = set_data.get('past',    {})

    price = SetPrice(
        cur_avg      = cur.get('avg'),
        cur_max      = cur.get('max'),
        cur_min      = cur.get('min'),
        cur_qty      = cur.get('quantity'),
        cur_currency = cur.get('currency'),

        prev_avg      = prev.get('avg'),
        prev_max      = prev.get('max'),
        prev_min      = prev.get('min'),
        prev_qty      = prev.get('quantity'),
        prev_currency = prev.get('currency'),
        prev_last_sale_date = prev.get('last_sale_date'),
    )
    row.prices.append(price)
    session.flush()  # populate row.id before upsert_inventory uses it
    return row


def upsert_inventory(session, set_row: Set) -> Inventory:
    """
    Add a set to inventory or increment its quantity if already present.
    Returns the Inventory row.
    """
    inv = session.query(Inventory).filter_by(set_id=set_row.id).first()

    if inv is None:
        inv = Inventory(set_id=set_row.id, quantity=1)
        session.add(inv)
    else:
        inv.quantity  += 1
        inv.updated_at = datetime.now(timezone.utc)

    return inv


def decrement_inventory(session, set_id: int) -> Inventory | None:
    """
    Decrement quantity by 1. If quantity reaches 0, delete the row.
    Returns the Inventory row (with updated quantity) or None if deleted.
    """
    inv = session.query(Inventory).filter_by(set_id=set_id).first()
    if inv is None:
        return None

    inv.quantity -= 1
    if inv.quantity <= 0:
        session.delete(inv)
        return None

    inv.updated_at = datetime.now(timezone.utc)
    return inv


def set_to_dict(set_row: Set) -> dict:
    """
    Serialise a Set + its latest SetPrice snapshot to the same JSON shape
    that SetHandler returns, with extra inventory fields added.
    """
    price = set_row.latest_price

    def _fmt(val, currency):
        if val is None:
            return '—'
        return f'{val} {currency}' if currency else str(val)

    cur_currency  = price.cur_currency  if price else None
    prev_currency = price.prev_currency if price else None

    inv = set_row.inventory[0] if set_row.inventory else None

    return {
        'set_number':   set_row.set_number,
        'name':         set_row.name      or '—',
        'category':     set_row.category  or '—',
        'year':         set_row.year,
        'image':        set_row.image     or '',
        'thumbnail':    set_row.thumbnail or '',
        'quantity':     inv.quantity      if inv else 0,
        'last_fetched': set_row.last_fetched.isoformat() if set_row.last_fetched else None,
        'current': {
            'avg':      price.cur_avg      if price else None,
            'max':      price.cur_max      if price else None,
            'min':      price.cur_min      if price else None,
            'quantity': price.cur_qty      if price else None,
            'currency': cur_currency,
        } if price else {},
        'past': {
            'avg':            price.prev_avg            if price else None,
            'max':            price.prev_max            if price else None,
            'min':            price.prev_min            if price else None,
            'quantity':       price.prev_qty            if price else None,
            'currency':       prev_currency,
            'last_sale_date': price.prev_last_sale_date if price else None,
        } if price else {},
    }