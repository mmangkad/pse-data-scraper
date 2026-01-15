"""
Main entry point to run PSE stock scraping, downloading, and combining.
"""

import logging

from pse_data_scraper.pipeline import sync_data


def main() -> None:
    """
    Executes the full ETL process for PSE stock data.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sync_data()


if __name__ == "__main__":
    main()
