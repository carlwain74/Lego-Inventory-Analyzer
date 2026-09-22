"""
brickset.py — Thin wrapper around the BrickSet API (via the `brickse`
library) for retrieving the official LEGO.com US retail price for a set.
"""

import configparser
import json
import logging

logging.basicConfig(
format='%(asctime)s %(levelname)-8s %(message)s',
level=logging.INFO,
datefmt='%Y-%m-%d %H:%M:%S')


class BrickSetAPI:

    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        self.api_key = None
        if config.has_option('bricklink', 'api_key'):
            self.api_key = config['bricklink']['api_key'].strip() or None

    """
    Look up the official LEGO.com US retail price for a set number.
    Returns a float, or None if unavailable (no API key, no match, or the
    request failed) — a missing retail price should never break the
    Bricklink price fetch it accompanies.
    """
    def get_retail_price_usd(self, set_number):
        if not self.api_key:
            logging.warning('No BrickSet API key configured — skipping retail price lookup')
            return None

        try:
            import brickse
        except ImportError:
            logging.warning('brickse package not installed — skipping retail price lookup')
            return None

        try:
            brickse.init(self.api_key)
            response = brickse.lego.get_set(set_number=set_number, extended_data=True)
            payload = json.loads(response.read())
        except Exception as e:
            logging.exception(f'Could not fetch retail price for {set_number}: {str(e)}')
            return None

        matches = payload.get('sets') or []
        if not matches:
            return None

        price = matches[0].get('LEGOCom', {}).get('US', {}).get('retailPrice')
        if price in (None, ''):
            return None

        try:
            return float(price)
        except (TypeError, ValueError):
            return None
