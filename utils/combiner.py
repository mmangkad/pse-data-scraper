"""
Compatibility wrappers for the updated combiner implementation.
"""

import logging

from pse_data_scraper.combiner import combine_csvs


def run_combiner(data_folder: str = "historicaldata", output_file: str = "combined.csv") -> None:
    """
    Combines all CSV files in a folder into one output file.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    combine_csvs(data_folder, output_file)
