import generate_sheets as sheets
from bricklink import BrickLinkAPI
import logging
import json
from os.path import exists
from os import stat


logging.basicConfig(
format='%(asctime)s %(levelname)-8s %(message)s',
level=logging.INFO,
datefmt='%Y-%m-%d %H:%M:%S')


class SetHandler():


    def __init__(self, set_num, set_list, multi_sheet, output_file = 'Sets.xlsx', config_file = 'config.ini'):
        self.set_number = set_num
        self.set_list = set_list
        self.multi_sheet = multi_sheet
        self.output_file = output_file
        self.config_file = config_file

        logging.info('Setup API session')
        self.bricklink_session = BrickLinkAPI(self.config_file)

        if not self.bricklink_session:
            logging.error('Could not create an API session')
            sys.exit(1)

    """
    The main handler routine.
    """
    def set_handler(self):
        
        if self.set_number:
            logging.info('Processing single set')
            try:
                self.bricklink_session.processSet(self.set_number)
            except Exception as e:
                logging.exception("Could not get set details" + str(e))
                return None

            sets = self.bricklink_session.getSets()
            for key in sets:
                self.bricklink_session.print_details(sets[key], key)
            return sets
        elif self.set_list:
            logging.info('Processing multiple sets')

            if exists(self.set_list):
                logging.info(f"Processing sets in {self.set_list}")

                if stat(self.set_list).st_size == 0:
                    logging.error("File is empty!!")
                    sys.exit()
                else:
                    with open(self.set_list, "r") as file_handler:
                        for line in file_handler:
                            self.bricklink_session.processSet(line.strip())

                    sets = self.bricklink_session.getSets()
                    
                    logging.info("Creating workbook")
                    if self.multi_sheet:
                        logging.info("Multi Sheet")
                        workbook = sheets.create_wookbook(self.output_file)
                        sheets.generate_multi_sheet(sets, workbook)
                    else:
                        logging.info("Single Sheet")
                        (workbook, worksheet) = sheets.create_wookbook_and_sheet(self.output_file)
                        sheets.generate_single_sheet(sets, workbook, worksheet)

                workbook.save(filename=self.output_file)
                return sets

    def test_config(self, config_file = 'config.ini'):
        res = self.bricklink_session.getDetails("75105-1")

        if res:
            return True
        else:
            return False
