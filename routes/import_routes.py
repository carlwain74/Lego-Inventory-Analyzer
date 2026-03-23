"""
routes/import_routes.py — Import Blueprint

Routes:
    POST /inventory/import        — import a single set number
    POST /inventory/import/bulk   — import from file, streaming SSE progress
"""

import os
import json
import tempfile

from flask import Blueprint, jsonify, request, Response, stream_with_context

from database import get_session, upsert_set, upsert_inventory, is_price_stale, set_to_dict
from models import Set

import_bp = Blueprint('import', __name__, url_prefix='/inventory/import')


def _fetch_set(set_number: str) -> tuple[dict | None, str | None]:
    """
    Fetch set data from Bricklink via SetHandler.
    Returns (data_dict, error_message).
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
        return None, str(e)

    if not result or set_number not in result:
        return None, 'No data returned from Bricklink.'

    data = result[set_number]
    data['set_number'] = set_number
    return data, None


def _import_set(session, set_number: str) -> tuple[dict, bool, str | None]:
    """
    Import a single set into the database.
    Returns (set_dict, was_cached, error_message).
    """
    set_row = session.query(Set).filter_by(set_number=set_number).first()
    cached  = set_row is not None and not is_price_stale(set_row)

    if not cached:
        data, err = _fetch_set(set_number)
        if err:
            return {}, False, err
        set_row = upsert_set(session, data)

    upsert_inventory(session, set_row)
    return set_to_dict(set_row), cached, None


@import_bp.route('', methods=['POST'])
def import_single():
    """Import a single set number into inventory."""
    data       = request.get_json(force=True, silent=True) or {}
    set_number = data.get('set_number', '').strip()

    if not set_number:
        return jsonify({'error': 'set_number is required.'}), 400

    import re
    if not re.match(r'^\d+-\d+$', set_number):
        return jsonify({'error': 'Invalid set number format. Use XXXXX-1.'}), 400

    with get_session() as session:
        result, cached, err = _import_set(session, set_number)

    if err:
        return jsonify({'error': err}), 500

    return jsonify({'set': result, 'cached': cached, 'quantity': result.get('quantity', 1)})


@import_bp.route('/bulk', methods=['POST'])
def import_bulk():
    """
    Import multiple sets from an uploaded text file.
    Streams Server-Sent Events so the frontend can show a progress bar.

    Each SSE event is a JSON object:
      {"progress": 3, "total": 12, "set_number": "75192-1",
       "status": "ok"|"cached"|"error", "message": "..."}

    Final event:
      {"done": true, "imported": 11, "errors": 1}
    """
    uploaded_file = request.files.get('set_file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'Please upload a set list file.'}), 400

    # Write to temp file so we can iterate it
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as tmp:
        tmp_path = tmp.name
        uploaded_file.save(tmp)

    def generate():
        try:
            with open(tmp_path, 'r') as f:
                set_numbers = [line.strip() for line in f if line.strip()]

            total    = len(set_numbers)
            imported = 0
            errors   = 0

            if total == 0:
                yield _sse({'error': 'File is empty.', 'done': True})
                return

            for i, set_number in enumerate(set_numbers, start=1):
                try:
                    with get_session() as session:
                        result, cached, err = _import_set(session, set_number)

                    if err:
                        errors += 1
                        yield _sse({
                            'progress':   i,
                            'total':      total,
                            'set_number': set_number,
                            'status':     'error',
                            'message':    err,
                        })
                    else:
                        imported += 1
                        yield _sse({
                            'progress':   i,
                            'total':      total,
                            'set_number': set_number,
                            'status':     'cached' if cached else 'ok',
                        })

                except Exception as e:
                    errors += 1
                    yield _sse({
                        'progress':   i,
                        'total':      total,
                        'set_number': set_number,
                        'status':     'error',
                        'message':    str(e),
                    })

            yield _sse({'done': True, 'imported': imported, 'errors': errors})

        finally:
            os.unlink(tmp_path)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':       'no-cache',
            'X-Accel-Buffering':   'no',  # disable nginx buffering if proxied
        },
    )


def _sse(data: dict) -> str:
    return f'data: {json.dumps(data)}\n\n'