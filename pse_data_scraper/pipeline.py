"""
High-level pipeline helpers.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

from pse_data_scraper.client import PSEClient
from pse_data_scraper.combiner import combine_csvs
from pse_data_scraper.downloader import download_historical_data
from pse_data_scraper.models import Company
from pse_data_scraper.scraper import (
    load_companies_from_csv,
    save_companies_to_csv,
    scrape_companies,
)

logger = logging.getLogger(__name__)


def ensure_companies_csv(
    client: PSEClient,
    companies_csv: str,
    refresh: bool = False,
    max_pages: Optional[int] = None,
) -> List[Company]:
    path = Path(companies_csv)
    if path.exists() and not refresh:
        logger.info("Using existing company list: %s", path)
        return load_companies_from_csv(str(path))

    logger.info("Scraping company list...")
    companies = scrape_companies(client, max_pages=max_pages)
    save_companies_to_csv(companies, str(path))
    return companies


def download_prices(
    client: PSEClient,
    companies: Optional[Sequence[Company]] = None,
    companies_csv: Optional[str] = None,
    history_dir: str = "data/history",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbols: Optional[Sequence[str]] = None,
    max_companies: Optional[int] = None,
    cache_dir: Optional[str] = ".cache",
    refresh: bool = False,
) -> None:
    download_historical_data(
        client=client,
        input_csv=companies_csv,
        companies=companies,
        output_dir=history_dir,
        start_date=start_date,
        end_date=end_date or date.today(),
        symbols=symbols,
        max_companies=max_companies,
        cache_dir=cache_dir,
        refresh=refresh,
    )


def export_prices(history_dir: str = "data/history", combined_csv: str = "data/combined.csv") -> None:
    combine_csvs(history_dir, combined_csv)


def sync_data(
    companies_csv: str = "data/companies.csv",
    history_dir: str = "data/history",
    combined_csv: str = "data/combined.csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rate_limit_seconds: float = 0.6,
    symbols: Optional[Sequence[str]] = None,
    max_companies: Optional[int] = None,
    cache_dir: Optional[str] = ".cache",
    refresh: bool = False,
    max_pages: Optional[int] = None,
) -> None:
    client = PSEClient(rate_limit_seconds=rate_limit_seconds)

    logger.info("Step 1: Preparing company list...")
    companies = ensure_companies_csv(
        client=client,
        companies_csv=companies_csv,
        refresh=refresh,
        max_pages=max_pages,
    )

    logger.info("Step 2: Downloading historical data...")
    download_prices(
        client=client,
        companies=companies,
        companies_csv=companies_csv,
        history_dir=history_dir,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        max_companies=max_companies,
        cache_dir=cache_dir,
        refresh=refresh,
    )

    logger.info("Step 3: Exporting combined CSV...")
    export_prices(history_dir, combined_csv)


def run_all(
    output_companies_csv: str = "finalstocks.csv",
    output_data_dir: str = "historicaldata",
    output_combined_csv: str = "combined.csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rate_limit_seconds: float = 0.6,
    symbols: Optional[Sequence[str]] = None,
    max_companies: Optional[int] = None,
    cache_dir: Optional[str] = ".cache",
    refresh: bool = False,
) -> None:
    client = PSEClient(rate_limit_seconds=rate_limit_seconds)

    logger.info("Step 1: Scraping company list...")
    companies = scrape_companies(client)
    save_companies_to_csv(companies, output_companies_csv)

    logger.info("Step 2: Downloading historical data...")
    download_historical_data(
        client=client,
        input_csv=output_companies_csv,
        output_dir=output_data_dir,
        start_date=start_date,
        end_date=end_date or date.today(),
        symbols=symbols,
        max_companies=max_companies,
        cache_dir=cache_dir,
        refresh=refresh,
    )

    logger.info("Step 3: Combining CSV files...")
    combine_csvs(output_data_dir, output_combined_csv)
