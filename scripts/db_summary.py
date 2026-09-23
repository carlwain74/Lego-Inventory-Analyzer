"""
db_summary.py — Inspect an inventory.db file and print a summary of its contents.

Usage:
    python db_summary.py                       # summarise ./inventory.db
    python db_summary.py --db /path/to/other.db
    python db_summary.py --list                # also list every inventory row
"""

import argparse
import os
import sys
from collections import Counter

from database import init_db, get_session, is_price_stale
from models import Set, SetPrice, Inventory


def format_price(value, currency=None):
    if value is None:
        return '—'
    return f'{value} {currency}' if currency else str(value)


def print_summary(db_path, show_list):
    if not os.path.isfile(db_path):
        print(f'No database file found at: {db_path}')
        sys.exit(1)

    init_db(db_path)

    with get_session() as session:
        sets       = session.query(Set).order_by(Set.set_number).all()
        inventory  = session.query(Inventory).all()
        price_rows = session.query(SetPrice).count()

        total_sets      = len(sets)
        total_inventory = len(inventory)
        total_quantity  = sum(inv.quantity for inv in inventory)

        stale_count = sum(1 for s in sets if is_price_stale(s))
        fresh_count = total_sets - stale_count

        with_retail    = sum(1 for s in sets if s.latest_price and s.latest_price.retail_price_usd is not None)
        without_retail = total_sets - with_retail

        categories = Counter(s.category or 'Uncategorised' for s in sets)

        print('=' * 60)
        print(f'Database: {db_path}')
        print('=' * 60)
        print(f'Sets cached:              {total_sets}')
        print(f'Price snapshots stored:   {price_rows}')
        print(f'  fresh (within TTL):     {fresh_count}')
        print(f'  stale:                  {stale_count}')
        print(f'Sets with US retail price: {with_retail}')
        print(f'Sets missing retail price: {without_retail}')
        print()
        print(f'Inventory rows:           {total_inventory}')
        print(f'Total sets owned (qty):   {total_quantity}')
        print()

        if categories:
            print('By category:')
            for category, count in categories.most_common():
                print(f'  {category:<30} {count}')
            print()

        if show_list:
            print('-' * 60)
            print(f'{"Set #":<12}{"Name":<32}{"Qty":<5}{"Cur Avg":<14}{"Retail (US)"}')
            print('-' * 60)
            inv_by_set_id = {inv.set_id: inv for inv in inventory}
            for s in sets:
                inv   = inv_by_set_id.get(s.id)
                price = s.latest_price
                cur_avg = format_price(price.cur_avg, price.cur_currency) if price else '—'
                retail  = format_price(price.retail_price_usd, 'USD') if price and price.retail_price_usd is not None else '—'
                qty     = inv.quantity if inv else 0
                name    = (s.name or '—')[:31]
                print(f'{s.set_number:<12}{name:<32}{qty:<5}{cur_avg:<14}{retail}')


def main():
    parser = argparse.ArgumentParser(description='Summarise an inventory.db file.')
    parser.add_argument('--db', default=os.path.join(os.path.dirname(__file__), 'inventory.db'),
                        help='Path to the SQLite database file (default: ./inventory.db)')
    parser.add_argument('--list', action='store_true',
                        help='List every set in inventory, not just the summary counts')
    args = parser.parse_args()

    print_summary(args.db, args.list)


if __name__ == '__main__':
    main()
