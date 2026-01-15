"""
Compatibility wrappers for the updated scraper implementation.
"""

import logging
from typing import List, Tuple

from pse_data_scraper.client import PSEClient
from pse_data_scraper.scraper import parse_companies_from_html, scrape_companies, save_companies_to_csv

OUTPUT_FILE = "finalstocks.csv"


def extract_rows_from_page(page_html: str) -> List[Tuple[str, str, str, str]]:
    """
    Extracts company and stock data rows from a page's HTML content.
    """
    companies = parse_companies_from_html(page_html)
    return [
        (company.company_id, company.security_id, company.company_name, company.stock_symbol)
        for company in companies
    ]


def run_scraper() -> None:
    """
    Runs the scraper to fetch all pages and save data to a CSV file.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = PSEClient()
    companies = scrape_companies(client)
    save_companies_to_csv(companies, OUTPUT_FILE)
