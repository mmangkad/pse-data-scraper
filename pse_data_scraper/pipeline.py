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
    ScrapeIncompleteError,
    load_companies_from_csv,
    save_companies_to_csv,
    scrape_companies,
)

logger = logging.getLogger(__name__)


def _existing_company_count(path: Path) -> Optional[int]:
    """Best-effort row count of an existing companies CSV (None if unreadable)."""
    try:
        return len(load_companies_from_csv(str(path)))
    except Exception:  # pragma: no cover - only enriches the error messages below
        return None


def ensure_companies_csv(
    client: PSEClient,
    companies_csv: str,
    refresh: bool = False,
    max_pages: Optional[int] = None,
    keyword: Optional[str] = None,
    sector: Optional[str] = None,
) -> List[Company]:
    path = Path(companies_csv)
    if path.exists() and not refresh:
        logger.info("Using existing company list: %s", path)
        return load_companies_from_csv(str(path))

    logger.info("Scraping company list...")
    try:
        companies = scrape_companies(client, max_pages=max_pages, keyword=keyword, sector=sector)
    except ScrapeIncompleteError as exc:
        if path.exists():
            existing_count = _existing_company_count(path)
            kept = f"{existing_count} companies" if existing_count is not None else "existing companies"
            raise ScrapeIncompleteError(
                f"{exc} Kept the existing company list ({kept}) at {path}; "
                "re-run with --refresh to retry the scrape."
            ) from exc
        raise

    if path.exists() and max_pages is not None:
        existing_count = _existing_company_count(path)
        if existing_count is not None and existing_count > len(companies):
            raise ScrapeIncompleteError(
                f"Refusing to overwrite {path} ({existing_count} companies) with a smaller, "
                f"page-limited scrape ({len(companies)} companies, --max-pages={max_pages}); "
                "re-run without --max-pages to refresh the full list."
            )

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
    keyword: Optional[str] = None,
    sector: Optional[str] = None,
) -> None:
    client = PSEClient(rate_limit_seconds=rate_limit_seconds)

    logger.info("Step 1: Preparing company list...")
    companies = ensure_companies_csv(
        client=client,
        companies_csv=companies_csv,
        refresh=refresh,
        max_pages=max_pages,
        keyword=keyword,
        sector=sector,
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
