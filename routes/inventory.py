"""
routes/inventory.py — Inventory Blueprint

Routes:
    GET  /inventory                 — return all inventory sets as JSON
    DELETE /inventory/<set_number>  — decrement or remove a set
    DELETE /inventory               — clear all inventory (with confirmation)
    POST /inventory/<set_number>/refresh — re-fetch prices from Bricklink
"""

import os
from flask import Blueprint, jsonify, request

from database import get_session, decrement_inventory, upsert_set, set_to_dict, is_price_stale
from models import Set, Inventory

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@inventory_bp.route('', methods=['GET'])
def get_inventory():
    """Return all inventory sets with their latest prices."""
    with get_session() as session:
        rows = (
            session.query(Set)
            .join(Inventory)
            .order_by(Inventory.added_at.desc())
            .all()
        )
        sets = {row.set_number: set_to_dict(row) for row in rows}
    return jsonify(sets)


@inventory_bp.route('/<set_number>', methods=['DELETE'])
def remove_set(set_number):
    """
    Decrement the quantity of a set in inventory by 1.
    If quantity reaches 0 the row is deleted.
    """
    with get_session() as session:
        set_row = session.query(Set).filter_by(set_number=set_number).first()
        if set_row is None:
            return jsonify({'error': f'Set {set_number} not found.'}), 404

        result = decrement_inventory(session, set_row.id)

    if result is None:
        return jsonify({'removed': True, 'quantity': 0})
    return jsonify({'removed': False, 'quantity': result.quantity})


@inventory_bp.route('', methods=['DELETE'])
def clear_inventory():
    """Delete all rows from the inventory table."""
    with get_session() as session:
        count = session.query(Inventory).count()
        session.query(Inventory).delete()
    return jsonify({'cleared': True, 'removed': count})


@inventory_bp.route('/<set_number>/refresh', methods=['POST'])
def refresh_set(set_number):
    """
    Re-fetch prices for a single set from Bricklink and append a new
    SetPrice snapshot, regardless of TTL.
    """
    from set_handler import SetHandler

    config_file = os.environ.get('CONFIG_PATH', 'config.ini')
    output_file = os.path.join(os.environ.get('OUTPUT_DIR', '.'), 'Sets.xlsx')

    try:
        handler = SetHandler(
            set_num=set_number,
            set_list=None,
            multi_sheet=False,
            output_file=output_file,
            config_file=config_file,
        )
        result = handler.set_handler()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not result or set_number not in result:
        return jsonify({'error': 'No data returned from Bricklink.'}), 500

    data = result[set_number]
    data['set_number'] = set_number

    with get_session() as session:
        set_row = upsert_set(session, data)
        updated = set_to_dict(set_row)

    return jsonify(updated)