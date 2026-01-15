"""
Compatibility wrappers for the updated downloader implementation.
"""

import logging

from pse_data_scraper.client import PSEClient
from pse_data_scraper.downloader import download_historical_data


def run_downloader(input_csv: str = "finalstocks.csv", output_dir: str = "historicaldata") -> None:
    """
    Fetches and stores historical data for each stock listed in the input CSV.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = PSEClient()
    download_historical_data(client=client, input_csv=input_csv, output_dir=output_dir)
