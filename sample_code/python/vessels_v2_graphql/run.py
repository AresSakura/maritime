import yaml
import json
import csv
from loguru import logger
from utilities import paging, helpers
from gql import gql


logger.add('demo_client.log', rotation="500 MB", retention="10 days", level='DEBUG')

rows_written_to_raw_log: int = 0
rows_written_to_csv: int = 0
pages_processed: int = 0
wrote_csv_header = False


def get_settings():
    """Reads the settings.yaml file and returns the variables and values
    :returns data: setting variables and values
    :rtype data: dict
    """
    with open('settings.yaml') as f:
        data: dict = yaml.load(f, Loader=yaml.FullLoader)
    return data


def read_query_file():
    settings = get_settings()
    file_name = settings['name_of_gql_query_file']
    with open(file_name, 'r') as f:
        return f.read()


def write_raw(data: dict):
    settings = get_settings()
    name_of_raw_output_file = settings['name_of_raw_output_file']
    if not name_of_raw_output_file:
        return
    with open(name_of_raw_output_file, 'a+') as f:
        f.write(json.dumps(data, indent=4))


def write_csv(data: dict):
    global rows_written_to_csv, wrote_csv_header
    settings = get_settings()
    name_of_csv_file = settings['name_of_csv_file']
    if not name_of_csv_file:
        return

    members = helpers.get_vessels_v2_members()
    # get just the keys
    csv_columns: list = [i[0] for i in members]
    try:
        with open(name_of_csv_file, 'a+') as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            logger.debug(f"WROTE HEADER: {wrote_csv_header}")
            if not wrote_csv_header:
                writer.writeheader()
                wrote_csv_header = True
            item: dict
            for item in data:
                writer.writerow(item)
                rows_written_to_csv += 1
    except Exception:
        raise



def get_info():
    info = f"""
            TOTAL PAGES WRITTEN TO RAW LOG: {rows_written_to_raw_log}
            TOTAL ROWS WRITTEN TO CSV: {rows_written_to_csv}
            TOTAL PAGES PROCESSED: {pages_processed}"""
    return info


def run():
    global pages_processed
    settings = get_settings()
    test_name = settings['test_name']
    pages_to_process = settings['pages_to_process']
    # make a client connection
    client = helpers.get_gql_client()
    # read file
    query = read_query_file()
    if not "pageInfo" or not "endCursor" or not "hasNextPage" in query:
        logger.error("Please include pageInfo in the query, it is required for paging.  See the README.md")
        return
    response: dict = dict()
    try:
        response = client.execute(gql(query))
    except BaseException as e:
        logger.error(e)
        raise

    # initialize paging
    pg = paging.Paging(response=response)
    schema_members = helpers.get_vessels_v2_members()

    # page, write, util complete
    logger.info("Paging started")
    while True:
        response, hasNextPage = pg.page_and_get_response(client, query)
        logger.debug(f"hasNextPage: {hasNextPage}")
        if response:
            write_raw(response)
            csv_data = helpers.transform_response_for_loading(response=response, schema=schema_members, test_name=test_name)
            if csv_data:
                write_csv(csv_data)
                pages_processed += 1
                logger.info(f"Page: {pages_processed}")
                if pages_to_process == 1:
                    break
                elif pages_to_process:
                    if not hasNextPage or not response:
                        break
                    if pages_processed >= pages_to_process:
                        break
                elif not hasNextPage or not response:
                    break
            else:
                logger.info("Did not get data for csv, either because there are no more pages, or did not get a response")
                break
        else:
            logger.info("No response or no more responses")
            break
        logger.info(get_info())


if __name__ == '__main__':
    run()
    logger.info("Done")
