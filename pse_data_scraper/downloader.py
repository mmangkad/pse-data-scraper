"""
Download historical stock data from PSE EDGE.
"""

from __future__ import annotations

import csv
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company, HistoricalPrice
from pse_data_scraper.utils import (
    OUTPUT_DATE_FORMAT,
    ensure_payload_date,
    format_output_date,
    log_cache_deprecation_once,
    sanitize_filename,
)
from pse_data_scraper.scraper import load_companies_from_csv

logger = logging.getLogger(__name__)

HISTORICAL_DATA_URL = "https://edge.pse.com.ph/common/DisclosureCht.ax"
HISTORICAL_DATA_REFERER = "https://edge.pse.com.ph/companyPage/stockData.do"


def _build_history_payload(
    company: Company,
    start_date: str,
    end_date: str,
) -> dict:
    return {
        "cmpy_id": company.company_id,
        "security_id": company.security_id,
        "startDate": start_date,
        "endDate": end_date,
    }


def fetch_historical_data(
    client: PSEClient,
    company: Company,
    start_date: str,
    end_date: str,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
) -> List[HistoricalPrice]:
    """Fetch daily OHLC rows for one company.

    ``cache_dir`` and ``refresh`` are deprecated no-ops kept for one release
    so documented API callers keep working; per-company CSVs are the source
    of truth now.
    """
    if cache_dir is not None:
        log_cache_deprecation_once()

    payload = _build_history_payload(company, start_date, end_date)
    response = client.post(
        HISTORICAL_DATA_URL,
        json=payload,
        headers={
            "Referer": HISTORICAL_DATA_REFERER,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    response.raise_for_status()
    response_payload = response.json()

    chart_data = response_payload.get("chartData", [])
    # The API occasionally repeats a date (observed live: the same record
    # returned up to 22 times for one date) — keep one row per date, the
    # last record seen.
    by_date: Dict[date, HistoricalPrice] = {}
    for item in chart_data:
        parsed = HistoricalPrice.from_api(item, company.stock_symbol)
        if parsed is not None:
            by_date[parsed.date] = parsed
    return [by_date[key] for key in sorted(by_date)]


def read_last_csv_date(path: Path) -> Optional[date]:
    """Return the max Date (ISO) in a history CSV, or None if unreadable/empty.

    Files are written sorted, but a max-scan is safer than tail-reading. An
    unreadable or fully unparseable file yields None, which callers treat as
    "full re-fetch" — the self-healing path.
    """
    max_date: Optional[date] = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                value = row.get("Date")
                if not value:
                    continue
                try:
                    parsed = datetime.strptime(value, OUTPUT_DATE_FORMAT).date()
                except ValueError:
                    continue
                if max_date is None or parsed > max_date:
                    max_date = parsed
    except OSError:
        return None
    return max_date


def read_company_history_csv(input_path: Path) -> List[HistoricalPrice]:
    """Read a history CSV back into rows (malformed rows are skipped)."""
    rows: List[HistoricalPrice] = []
    with input_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(
                    HistoricalPrice(
                        date=datetime.strptime(row["Date"], OUTPUT_DATE_FORMAT).date(),
                        symbol=row["Symbol"],
                        value=Decimal(row["Value"]),
                        open=Decimal(row["Open"]),
                        close=Decimal(row["Close"]),
                        high=Decimal(row["High"]),
                        low=Decimal(row["Low"]),
                    )
                )
            except (KeyError, ValueError, InvalidOperation):
                logger.warning("Skipping malformed history row in %s", input_path)
    return rows


def merge_history_rows(
    existing_rows: Iterable[HistoricalPrice],
    new_rows: Iterable[HistoricalPrice],
) -> List[HistoricalPrice]:
    """Merge two row sets, deduplicating on date (the newer fetch wins)."""
    merged: Dict[date, HistoricalPrice] = {}
    for row in existing_rows:
        merged[row.date] = row
    for row in new_rows:
        merged[row.date] = row
    return [merged[key] for key in sorted(merged)]


def write_company_history_csv(
    output_path: Path, company: Company, rows: Iterable[HistoricalPrice]
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file and rename so a crash mid-write can never leave a
    # truncated history CSV behind.
    tmp_path = output_path.with_suffix(".csv.tmp")
    try:
        with tmp_path.open("w", newline="", encoding="utf-8") as company_file:
            writer = csv.writer(company_file)
            writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])
            for item in rows:
                writer.writerow(
                    [
                        item.symbol,
                        company.company_name,
                        format_output_date(item.date),
                        item.value,
                        item.open,
                        item.close,
                        item.high,
                        item.low,
                    ]
                )
        os.replace(tmp_path, output_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def download_historical_data(
    client: PSEClient,
    companies: Optional[Sequence[Company]] = None,
    input_csv: Optional[str] = None,
    output_dir: str = "data/history",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbols: Optional[Sequence[str]] = None,
    max_companies: Optional[int] = None,
    cache_dir: Optional[str] = ".cache",
    refresh: bool = False,
) -> List[Path]:
    if companies is None and input_csv is None:
        raise ValueError("Either 'companies' or 'input_csv' must be provided")
    if companies is None:
        companies = load_companies_from_csv(input_csv)

    symbol_set = {symbol.strip().upper() for symbol in symbols} if symbols else None
    output_root = Path(output_dir)

    start_payload = ensure_payload_date(start_date or "01-01-1900")
    end_payload = ensure_payload_date(end_date or date.today())

    saved_paths: List[Path] = []
    # Per-company outcomes (saved_full / saved_incremental / up_to_date /
    # no_data / failed), surfaced by future run summaries.
    status_counts: Counter = Counter()
    processed = 0

    for company in companies:
        if symbol_set and company.stock_symbol.upper() not in symbol_set:
            continue

        if max_companies is not None and processed >= max_companies:
            break

        processed += 1
        safe_name = sanitize_filename(company.company_name)
        filename = f"{company.stock_symbol}_{safe_name}.csv"
        output_path = output_root / filename

        # An existing file (without --refresh) means an incremental update:
        # fetch only what is missing and merge into the file. With an explicit
        # --from, the requested range is fetched and merged (backfill or
        # extension). An unreadable file self-heals via a full fetch.
        existing_rows: Optional[List[HistoricalPrice]] = None
        if not refresh and output_path.exists():
            last_date = read_last_csv_date(output_path)
            if last_date is not None:
                fetch_start = (
                    start_payload
                    if start_date is not None
                    else ensure_payload_date(last_date + timedelta(days=1))
                )
                existing_rows = read_company_history_csv(output_path)
            else:
                fetch_start = start_payload
        else:
            fetch_start = start_payload

        logger.info("[%s] %s %s %s", processed, company.stock_symbol, company.company_id, company.company_name)

        try:
            rows = fetch_historical_data(
                client=client,
                company=company,
                start_date=fetch_start,
                end_date=end_payload,
            )
            if existing_rows is not None:
                if rows:
                    merged_rows = merge_history_rows(existing_rows, rows)
                    new_count = len({row.date for row in rows} - {row.date for row in existing_rows})
                    write_company_history_csv(output_path, company, merged_rows)
                    saved_paths.append(output_path)
                    status_counts["saved_incremental"] += 1
                    logger.info("Updated: %s (+%s new rows)", output_path, new_count)
                else:
                    # Nothing new is normal (weekend, ~1 trading day API lag).
                    saved_paths.append(output_path)
                    status_counts["up_to_date"] += 1
                    logger.debug("No new data for %s (already up to date)", company.company_name)
            elif rows:
                write_company_history_csv(output_path, company, rows)
                saved_paths.append(output_path)
                status_counts["saved_full"] += 1
                logger.info("Saved: %s", output_path)
            else:
                status_counts["no_data"] += 1
                logger.info("No data for %s", company.company_name)
        except requests.RequestException as exc:
            status_counts["failed"] += 1
            logger.warning("Request failed for %s: %s", company.company_name, exc)
        except (ValueError, KeyError) as exc:
            status_counts["failed"] += 1
            logger.warning("Unexpected payload for %s: %s", company.company_name, exc)

    logger.debug("Download tally: %s", dict(status_counts))
    return saved_paths
