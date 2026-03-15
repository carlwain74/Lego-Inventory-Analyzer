from bricklink_py import Bricklink
import configparser
import html
from html.parser import HTMLParser
from datetime import datetime
import logging
import json

logging.basicConfig(
format='%(asctime)s %(levelname)-8s %(message)s',
level=logging.INFO,
datefmt='%Y-%m-%d %H:%M:%S')


class BrickLinkAPI:

    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        # fill in with your data from https://www.bricklink.com/v2/api/register_consumer.page
        consumer_key = config['secrets']['consumer_key']
        consumer_secret = config['secrets']['consumer_secret']
        token_value = config['secrets']['token_value']
        token_secret = config['secrets']['token_secret']

        try:
            session = Bricklink(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                token=token_value,
                token_secret=token_secret
            )
        except Exception as e:
            logging.error('Could not get auth token - ', str(e))

        self.session = session
        self.sets = {}

    @staticmethod
    def get_last_sale_date(sales: dict) -> str | None:
        """
        Given an unordered dictionary of past sales (keyed by any value),
        return the ISO 8601 date string of the most recent sale.

        Each sale entry is expected to contain a 'date_ordered' field in
        ISO 8601 format, e.g. '2023-05-27T01:09:39.493Z'.

        Returns the raw ISO string of the most recent sale, or None if the
        dictionary is empty or no valid dates are found.

        Example
        -------
        sales = {
            1: {"date_ordered": "2023-05-27T01:09:39.493Z", "unit_price": "197.42"},
            2: {"date_ordered": "2023-12-11T18:44:02.100Z", "unit_price": "210.00"},
            3: {"date_ordered": "2022-08-03T09:15:55.000Z", "unit_price": "185.00"},
        }
        get_last_sale_date(sales)
        # → '2023-12-11T18:44:02.100Z'
        """
        latest_dt  = None
        latest_raw = None

        items = sales.values() if isinstance(sales, dict) else sales
        for sale in items:
            raw = sale.get('date_ordered', '')
            if not raw:
                continue
            try:
                # Replace trailing Z with +00:00 for fromisoformat compatibility
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except ValueError:
                continue

            if latest_dt is None or dt > latest_dt:
                latest_dt  = dt
                latest_raw = raw

        return latest_raw


    def getSetInfo(self, set_number, item_type):
        logging.info(f"Getting set info for {set_number}")
        h_parse = html.parser

        type_data = self.session.catalog_item.get_item(item_type, set_number)

        logging.debug(json.dumps(type_data, indent=4, sort_keys=True))

        self.sets[set_number] = {}
        self.sets[set_number]['name'] = h_parse.unescape(type_data['name'])
        self.sets[set_number]['year'] = type_data['year_released']
        self.sets[set_number]['image'] = type_data['image_url']
        self.sets[set_number]['thumbnail'] = type_data['thumbnail_url']
        self.sets[set_number]['category_id'] = type_data['category_id']

    def getSetPastSales(self, set_number, item_type):
        logging.info(f"Getting set past sales for {set_number}")
        h_parse = html.parser

        past_sales = self.session.catalog_item.get_price_guide(item_type, set_number, new_or_used="N", \
                                                               guide_type="sold", country_code="US", region="north_america")

        logging.debug(json.dumps(past_sales, indent=4, sort_keys=True))

        self.sets[set_number]['past'] = {}
        self.sets[set_number]['past']['avg'] = round(int(float(past_sales['avg_price'])))
        self.sets[set_number]['past']['max'] = round(int(float(past_sales['max_price'])))
        self.sets[set_number]['past']['min'] = round(int(float(past_sales['min_price'])))
        self.sets[set_number]['past']['quantity'] = past_sales['unit_quantity']
        self.sets[set_number]['past']['currency'] = past_sales['currency_code']

        self.sets[set_number]['past']['last_sale_date'] = BrickLinkAPI.get_last_sale_date(past_sales['price_detail'])      


    def getSetCurrentSales(self, set_number, item_type):
        logging.info(f"Getting set current sales for {set_number}")
        h_parse = html.parser

        current_items = self.session.catalog_item.get_price_guide(item_type, set_number, new_or_used="N",
                                                                  country_code="US", region="north_america")

        logging.debug(json.dumps(current_items, indent=4, sort_keys=True))

        self.sets[set_number]['current'] = {}
        self.sets[set_number]['current']['avg'] = round(int(float(current_items['avg_price'])))
        self.sets[set_number]['current']['max'] = round(int(float(current_items['max_price'])))
        self.sets[set_number]['current']['min'] = round(int(float(current_items['min_price'])))
        self.sets[set_number]['current']['quantity'] = current_items['unit_quantity']
        self.sets[set_number]['current']['currency'] = current_items['currency_code']


    def getSetCatalogInfo(self, set_number):
        logging.info(f"Getting set category details for {set_number}")
        h_parse = html.parser

        category_data = self.session.category.get_category(self.sets[set_number]['category_id'])

        logging.debug(json.dumps(category_data, indent=4, sort_keys=True))

        self.sets[set_number]['category'] = h_parse.unescape(category_data['category_name'])


    """
    This calls the API functions to get the data for a set.
    """
    def processSet(self, set_number):
        logging.info("Getting Set details for " + str(set_number))

        if set_number == "40158":
            item_type = "GEAR"
        else:
            item_type = "SET"

        try:
            self.getSetInfo(set_number, item_type)
            self.getSetCatalogInfo(set_number)
            self.getSetPastSales(set_number, item_type)
            self.getSetCurrentSales(set_number, item_type)      

        except Exception as e:
            logging.exception(f"Failed to get price guide for item [{set_number}] {str(e)}")
            return {}

        return self.sets

    def getSets(self):
        return self.sets

    """
    This prints stuff to the screen.
    """
    def print_details(self, element_data, number):
        logging.debug("Item: " + number)
        logging.debug("  Name: " + element_data['name'])
        logging.debug("  Category: " + element_data['category'])
        logging.debug("  Current Sales: ")
        logging.debug("     Average: " + str(element_data['current']['avg']) + " " + element_data['current']['currency'])
        logging.debug("     Max: " + str(element_data['current']['max']) + " " + element_data['current']['currency'])
        logging.debug("     Min: " + str(element_data['current']['min']) + " " + element_data['current']['currency'])
        logging.debug("     Quantity avail: " + str(element_data['current']['quantity']))
        logging.debug("  Previous Sales: ")
        logging.debug("     Average: " + str(element_data['past']['avg']) + " " + element_data['past']['currency'])
        logging.debug("     Max: " + str(element_data['past']['max']) + " " + element_data['past']['currency'])
        logging.debug("     Min: " + str(element_data['past']['min']) + " " + element_data['past']['currency'])
        logging.debug("     Quantity avail: " + str(element_data['past']['quantity']))
        logging.debug("     Last Sale Date: " + str(element_data['past']['last_sale_date']))
        logging.debug("  Year Released: " + str(element_data['year']))
        logging.debug("  Image: " + str(element_data['image']))
        logging.debug("  Thumbnail: " + str(element_data['thumbnail']))


