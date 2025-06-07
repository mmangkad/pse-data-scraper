"""
Main entry point to run PSE stock scraping, downloading, and combining.
"""

from utils.scraper import run_scraper
from utils.downloader import run_downloader
from utils.combiner import run_combiner


def main():
    """
    Executes the full ETL process for PSE stock data.
    """
    print("Step 1: Scraping company list...")
    run_scraper()

    print("Step 2: Downloading historical data...")
    run_downloader()

    print("Step 3: Combining CSV files...")
    run_combiner()


if __name__ == "__main__":
    main()