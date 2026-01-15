"""
Download historical stock data from PSE EDGE.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import requests

from pse_data_scraper.client import PSEClient
from pse_data_scraper.models import Company, HistoricalPrice
from pse_data_scraper.utils import ensure_payload_date, format_output_date, sanitize_filename
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


def _cache_key(company: Company, start_date: str, end_date: str) -> str:
    return f"{company.company_id}_{company.security_id}_{start_date}_{end_date}.json"


def _load_cached_json(cache_path: Path) -> Optional[dict]:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _save_cached_json(cache_path: Path, payload: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError:
        logger.warning("Failed to write cache file: %s", cache_path)


def fetch_historical_data(
    client: PSEClient,
    company: Company,
    start_date: str,
    end_date: str,
    cache_dir: Optional[Path] = None,
    refresh: bool = False,
) -> List[HistoricalPrice]:
    cache_payload: Optional[dict] = None
    cache_path: Optional[Path] = None

    if cache_dir is not None:
        cache_path = cache_dir / _cache_key(company, start_date, end_date)
        if not refresh:
            cache_payload = _load_cached_json(cache_path)

    if cache_payload is None:
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
        cache_payload = response.json()
        if cache_path is not None:
            _save_cached_json(cache_path, cache_payload)

    chart_data = cache_payload.get("chartData", [])
    results: List[HistoricalPrice] = []
    for item in chart_data:
        parsed = HistoricalPrice.from_api(item, company.stock_symbol)
        if parsed is not None:
            results.append(parsed)
    return results


def write_company_history_csv(
    output_path: Path, company: Company, rows: Iterable[HistoricalPrice]
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as company_file:
        writer = csv.writer(company_file)
        writer.writerow(["Date", "Symbol", "Value", "Open", "Close", "High", "Low"])
        for item in rows:
            writer.writerow(
                [
                    format_output_date(item.date),
                    item.symbol,
                    item.value,
                    item.open,
                    item.close,
                    item.high,
                    item.low,
                ]
            )


def download_historical_data(
    client: PSEClient,
    input_csv: Optional[str] = "finalstocks.csv",
    companies: Optional[Sequence[Company]] = None,
    output_dir: str = "historicaldata",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbols: Optional[Sequence[str]] = None,
    max_companies: Optional[int] = None,
    cache_dir: Optional[str] = ".cache",
    refresh: bool = False,
) -> List[Path]:
    if companies is None:
        if input_csv is None:
            raise ValueError("input_csv is required when companies is not provided")
        companies = load_companies_from_csv(input_csv)

    symbol_set = {symbol.strip().upper() for symbol in symbols} if symbols else None
    output_root = Path(output_dir)
    cache_root = Path(cache_dir) if cache_dir else None

    start_payload = ensure_payload_date(start_date or "01-01-1900")
    end_payload = ensure_payload_date(end_date or date.today())

    saved_paths: List[Path] = []
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

        if output_path.exists() and not refresh:
            logger.info("Skipping %s (already exists)", output_path)
            saved_paths.append(output_path)
            continue

        logger.info("[%s] %s %s %s", processed, company.stock_symbol, company.company_id, company.company_name)

        try:
            rows = fetch_historical_data(
                client=client,
                company=company,
                start_date=start_payload,
                end_date=end_payload,
                cache_dir=cache_root,
                refresh=refresh,
            )
            if not rows:
                logger.info("No data for %s", company.company_name)
                continue
            write_company_history_csv(output_path, company, rows)
            saved_paths.append(output_path)
            logger.info("Saved: %s", output_path)
        except requests.RequestException as exc:
            logger.warning("Request failed for %s: %s", company.company_name, exc)
        except (ValueError, KeyError) as exc:
            logger.warning("Unexpected payload for %s: %s", company.company_name, exc)

    return saved_paths
