"""
Command-line interface for the PSE Data Scraper.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import List, Optional

from pse_data_scraper import __version__
from pse_data_scraper.client import PSEClient
from pse_data_scraper.config import DEFAULT_CONFIG_NAME, load_config, write_default_config
from pse_data_scraper.downloader import SymbolNotFoundError, download_historical_data
from pse_data_scraper.pipeline import ensure_companies_csv, export_prices, sync_data
from pse_data_scraper.scraper import ScrapeIncompleteError
from pse_data_scraper.status import collect_status, latest_price_dates
from pse_data_scraper.utils import log_cache_deprecation_once


def _parse_symbols(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    items = [item.strip().upper() for item in value.split(",") if item.strip()]
    return items or None


def _setup_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        level = logging.WARNING
    else:
        level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _load_config(path: Optional[str]):
    try:
        return load_config(path)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        raise SystemExit(2) from exc
    except Exception as exc:  # pragma: no cover - unexpected config errors
        logging.error("Failed to load config: %s", exc)
        raise SystemExit(2) from exc


def _apply_overrides(config, args):
    cfg = replace(config)

    data_dir = getattr(args, "data_dir", None)
    if data_dir:
        cfg.data_dir = Path(data_dir)
        if getattr(args, "companies", None) is None:
            cfg.companies_csv = None
        if getattr(args, "history_dir", None) is None:
            cfg.history_dir = None
        if getattr(args, "combined", None) is None:
            cfg.combined_csv = None

    companies = getattr(args, "companies", None)
    if companies:
        cfg.companies_csv = Path(companies)

    history_dir = getattr(args, "history_dir", None)
    if history_dir:
        cfg.history_dir = Path(history_dir)

    combined = getattr(args, "combined", None)
    if combined:
        cfg.combined_csv = Path(combined)

    cache_dir = getattr(args, "cache_dir", None)
    if cache_dir:
        cfg.cache_dir = Path(cache_dir)
        log_cache_deprecation_once()

    if getattr(args, "no_cache", False):
        cfg.cache_dir = None
        log_cache_deprecation_once()

    rate_limit = getattr(args, "rate_limit", None)
    if rate_limit is not None:
        cfg.rate_limit = rate_limit

    timeout = getattr(args, "timeout", None)
    if timeout is not None and timeout > 0:
        cfg.timeout_seconds = timeout

    start_date = getattr(args, "start_date", None)
    if start_date:
        cfg.start_date = start_date

    end_date = getattr(args, "end_date", None)
    if end_date:
        cfg.end_date = end_date

    symbols = getattr(args, "symbols", None)
    if symbols is not None:
        cfg.symbols = _parse_symbols(symbols) or []

    max_companies = getattr(args, "max_companies", None)
    if max_companies is not None:
        cfg.max_companies = max_companies if max_companies > 0 else None

    sector = getattr(args, "sector", None)
    if sector:
        cfg.sector = sector

    keyword = getattr(args, "keyword", None)
    if keyword:
        cfg.keyword = keyword

    cfg.resolve_paths()
    return cfg


def _resolve_config(args):
    config = _load_config(getattr(args, "config", None))
    return _apply_overrides(config, args)


def _print_status(status: dict) -> None:
    companies = status["companies"]
    history = status["history"]
    combined = status["combined"]

    if companies["exists"]:
        print(
            f"Companies CSV: {companies['path']} (rows={companies['rows']}, updated={companies['updated']})"
        )
    else:
        print(f"Companies CSV: missing ({companies['path']})")

    if history["exists"]:
        print(f"History dir: {history['path']} (files={history['files']})")
    else:
        print(f"History dir: missing ({history['path']})")

    if combined["exists"]:
        range_text = combined["date_range"] or "unknown"
        print(
            f"Combined CSV: {combined['path']} (rows={combined['rows']}, updated={combined['updated']}, range={range_text})"
        )
        if combined["date_range"]:
            print(f"Latest price date: {combined['date_range'][1]} (EDGE data lags ~1 trading day)")
    else:
        print(f"Combined CSV: missing ({combined['path']})")


def handle_init(args) -> None:
    path = Path(args.path)
    created = write_default_config(path, force=args.force)
    if created:
        print(f"Created config at {path}")
    else:
        print(f"Config already exists: {path}")


def handle_companies(args) -> None:
    cfg = _resolve_config(args)
    client = PSEClient(rate_limit_seconds=cfg.rate_limit, timeout_seconds=cfg.timeout_seconds)
    companies = ensure_companies_csv(
        client=client,
        companies_csv=str(cfg.companies_csv),
        refresh=getattr(args, "refresh", False),
        max_pages=getattr(args, "max_pages", None),
        keyword=cfg.keyword,
        sector=cfg.sector,
    )
    if getattr(args, "list", False):
        for company in companies:
            print(f"{company.stock_symbol}\t{company.company_name}")


def handle_prices(args) -> None:
    cfg = _resolve_config(args)
    client = PSEClient(rate_limit_seconds=cfg.rate_limit, timeout_seconds=cfg.timeout_seconds)
    # --refresh applies to price history only; the company directory is
    # re-scraped by `pse companies --refresh` / `pse sync --refresh`.
    companies = ensure_companies_csv(
        client=client,
        companies_csv=str(cfg.companies_csv),
        max_pages=getattr(args, "max_pages", None),
        keyword=cfg.keyword,
        sector=cfg.sector,
    )
    download_historical_data(
        client=client,
        companies=companies,
        output_dir=str(cfg.history_dir),
        start_date=cfg.start_date,
        end_date=cfg.end_date or date.today(),
        symbols=cfg.symbols or None,
        max_companies=cfg.max_companies,
        cache_dir=str(cfg.cache_dir) if cfg.cache_dir else None,
        refresh=getattr(args, "refresh", False),
    )


def handle_export(args) -> None:
    cfg = _resolve_config(args)
    if args.format.lower() != "csv":
        logging.error("Only CSV export is supported right now.")
        raise SystemExit(2)
    export_prices(str(cfg.history_dir), str(cfg.combined_csv))


def handle_sync(args) -> None:
    cfg = _resolve_config(args)
    sync_data(
        companies_csv=str(cfg.companies_csv),
        history_dir=str(cfg.history_dir),
        combined_csv=str(cfg.combined_csv),
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        rate_limit_seconds=cfg.rate_limit,
        symbols=cfg.symbols or None,
        max_companies=cfg.max_companies,
        cache_dir=str(cfg.cache_dir) if cfg.cache_dir else None,
        refresh=getattr(args, "refresh", False),
        max_pages=getattr(args, "max_pages", None),
        keyword=cfg.keyword,
        sector=cfg.sector,
        timeout_seconds=cfg.timeout_seconds,
    )


def handle_status(args) -> None:
    cfg = _resolve_config(args)
    status = collect_status(cfg.companies_csv, cfg.history_dir, cfg.combined_csv)
    if getattr(args, "json", False):
        print(json.dumps(status, indent=2))
    else:
        _print_status(status)
        if getattr(args, "status_verbose", False):
            print("Latest price date per company (stalest first):")
            for name, latest in latest_price_dates(cfg.history_dir):
                print(f"  {name}: {latest or 'no dates'}")


SECTOR_HELP = (
    'Filter by sector, e.g. "Mining and Oil" (the SME board is the literal '
    'string "Small, Medium & Emerging Board"); applies server-side when '
    "scraping the directory and locally when a company list already exists"
)
KEYWORD_HELP = (
    "Company name substring (case-insensitive); applies server-side when "
    "scraping the directory and locally when a company list already exists"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pse", description="PSE EDGE data scraper")
    parser.add_argument("--version", action="version", version=f"pse {__version__}")
    parser.add_argument("--config", help="Path to pse.toml (default: ./pse.toml)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Only show warnings and errors")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a default config file")
    init_parser.add_argument("--path", default=DEFAULT_CONFIG_NAME, help="Config file path")
    init_parser.add_argument("--force", action="store_true", help="Overwrite if it exists")
    init_parser.set_defaults(func=handle_init)

    sync_parser = subparsers.add_parser("sync", help="Refresh companies, prices, and export")
    sync_parser.add_argument("--data-dir", help="Root data directory")
    sync_parser.add_argument("--companies", "--output", dest="companies", help="Companies CSV path")
    sync_parser.add_argument(
        "--history-dir", "--output-dir", dest="history_dir", help="History data directory"
    )
    sync_parser.add_argument("--combined", help="Combined CSV path")
    sync_parser.add_argument("--cache-dir", help="Cache folder")
    sync_parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    sync_parser.add_argument("--rate-limit", type=float, help="Seconds between requests")
    sync_parser.add_argument("--timeout", type=int, help="Request timeout in seconds")
    sync_parser.add_argument("--symbols", help="Comma-separated stock symbols to download")
    sync_parser.add_argument(
        "--from",
        "--start-date",
        dest="start_date",
        help="Start date (YYYY-MM-DD or MM-DD-YYYY)",
    )
    sync_parser.add_argument(
        "--to",
        "--end-date",
        dest="end_date",
        help="End date (YYYY-MM-DD or MM-DD-YYYY)",
    )
    sync_parser.add_argument("--max-companies", type=int, help="Limit number of companies")
    sync_parser.add_argument("--max-pages", type=int, help="Limit number of company pages")
    sync_parser.add_argument("--sector", help=SECTOR_HELP)
    sync_parser.add_argument("--keyword", help=KEYWORD_HELP)
    sync_parser.add_argument("--refresh", action="store_true", help="Refresh companies and prices")
    sync_parser.set_defaults(func=handle_sync)

    companies_parser = subparsers.add_parser("companies", help="Refresh or list companies")
    companies_parser.add_argument("--data-dir", help="Root data directory")
    companies_parser.add_argument("--companies", "--output", dest="companies", help="Companies CSV path")
    companies_parser.add_argument("--rate-limit", type=float, help="Seconds between requests")
    companies_parser.add_argument("--timeout", type=int, help="Request timeout in seconds")
    companies_parser.add_argument("--max-pages", type=int, help="Limit number of pages")
    companies_parser.add_argument("--sector", help=SECTOR_HELP)
    companies_parser.add_argument("--keyword", help=KEYWORD_HELP)
    companies_parser.add_argument("--refresh", action="store_true", help="Re-scrape companies")
    companies_parser.add_argument("--list", action="store_true", help="Print the company list")
    companies_parser.set_defaults(func=handle_companies)

    prices_parser = subparsers.add_parser("prices", help="Download historical prices")
    prices_parser.add_argument("--data-dir", help="Root data directory")
    prices_parser.add_argument("--companies", "--input", dest="companies", help="Companies CSV path")
    prices_parser.add_argument(
        "--history-dir", "--output-dir", dest="history_dir", help="History data directory"
    )
    prices_parser.add_argument("--cache-dir", help="Cache folder")
    prices_parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    prices_parser.add_argument("--rate-limit", type=float, help="Seconds between requests")
    prices_parser.add_argument("--timeout", type=int, help="Request timeout in seconds")
    prices_parser.add_argument("--symbols", help="Comma-separated stock symbols to download")
    prices_parser.add_argument(
        "--from",
        "--start-date",
        dest="start_date",
        help="Start date (YYYY-MM-DD or MM-DD-YYYY)",
    )
    prices_parser.add_argument(
        "--to",
        "--end-date",
        dest="end_date",
        help="End date (YYYY-MM-DD or MM-DD-YYYY)",
    )
    prices_parser.add_argument("--max-companies", type=int, help="Limit number of companies")
    prices_parser.add_argument("--max-pages", type=int, help="Limit number of company pages")
    prices_parser.add_argument("--sector", help=SECTOR_HELP)
    prices_parser.add_argument("--keyword", help=KEYWORD_HELP)
    prices_parser.add_argument(
        "--refresh", action="store_true", help="Re-download price history even if files exist"
    )
    prices_parser.set_defaults(func=handle_prices)

    export_parser = subparsers.add_parser("export", help="Export combined dataset")
    export_parser.add_argument("--data-dir", help="Root data directory")
    export_parser.add_argument("--history-dir", dest="history_dir", help="History data directory")
    export_parser.add_argument("--combined", "--output", dest="combined", help="Combined CSV path")
    export_parser.add_argument("--format", default="csv", help="Export format (csv)")
    export_parser.set_defaults(func=handle_export)

    status_parser = subparsers.add_parser("status", help="Show local dataset status")
    status_parser.add_argument("--data-dir", help="Root data directory")
    status_parser.add_argument("--companies", help="Companies CSV path")
    status_parser.add_argument("--history-dir", help="History data directory")
    status_parser.add_argument("--combined", help="Combined CSV path")
    status_parser.add_argument("--json", action="store_true", help="Output the status as JSON")
    status_parser.add_argument(
        # Own dest: the global --verbose (debug logging) must keep working
        # for `pse --verbose status`, and this flag must not turn DEBUG on.
        "--verbose",
        dest="status_verbose",
        action="store_true",
        help="Also list the latest price date per company (text output only)",
    )
    status_parser.set_defaults(func=handle_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose, args.quiet)
    try:
        args.func(args)
    except (ScrapeIncompleteError, SymbolNotFoundError) as exc:
        logging.error("%s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
