from generate_sheets import sheet_handler
import argparse
import logging

logging.basicConfig(
format='%(asctime)s %(levelname)-8s %(message)s',
level=logging.DEBUG,
datefmt='%Y-%m-%d %H:%M:%S')

def main():

	logging.info('Lego Inventory Generator')

	parser = argparse.ArgumentParser()
	parser.add_argument('-s', '--set', type=str)
	parser.add_argument('-f', '--file', type=str)
	parser.add_argument('-m', '--multi', type=str)
	parser.add_argument('-o', '--output', type=str)
	args = parser.parse_args()

	set_num = args.set
	set_list = args.file
	output_file = args.output
	multi_sheet = args.multi

	try:
		sheet_handler(set_num, set_list, multi_sheet, output_file)
	except Exception as e:
		logging.exception("Failed to call sheet_handler" + str(e))

if __name__ == '__main__':
    main()