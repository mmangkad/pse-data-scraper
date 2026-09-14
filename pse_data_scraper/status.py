"""
Status helpers for local datasets.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pse_data_scraper.downloader import read_last_csv_date
from pse_data_scraper.utils import OUTPUT_DATE_FORMAT

STATUS_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_mtime(path: Path) -> Optional[str]:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp).strftime(STATUS_TIME_FORMAT)


def _count_csv_rows(path: Path) -> Optional[int]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _ in reader)
    except OSError:
        return None


def _combined_stats(path: Path) -> Optional[Tuple[int, Optional[Tuple[str, str]]]]:
    """Single pass over combined.csv: (row count, (min date, max date)).

    Returns None when the file is unreadable; the date range is None when
    no row has a parseable Date.
    """
    rows = 0
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows += 1
                value = row.get("Date")
                if not value:
                    continue
                try:
                    parsed = datetime.strptime(value, OUTPUT_DATE_FORMAT)
                except ValueError:
                    continue
                if min_date is None or parsed < min_date:
                    min_date = parsed
                if max_date is None or parsed > max_date:
                    max_date = parsed
    except OSError:
        return None

    date_range = (
        (min_date.date().isoformat(), max_date.date().isoformat())
        if min_date is not None and max_date is not None
        else None
    )
    return rows, date_range


def latest_price_dates(history_dir: Path) -> List[Tuple[str, Optional[str]]]:
    """Latest price date per history file, stalest first (None = no dates)."""
    entries: List[Tuple[str, Optional[str]]] = []
    for path in sorted(history_dir.glob("*.csv")):
        latest = read_last_csv_date(path)
        entries.append((path.name, latest.isoformat() if latest is not None else None))
    entries.sort(key=lambda entry: (entry[1] is not None, entry[1] or "", entry[0]))
    return entries


def collect_status(
    companies_csv: Path,
    history_dir: Path,
    combined_csv: Path,
) -> Dict[str, Dict[str, object]]:
    companies_exists = companies_csv.exists()
    history_exists = history_dir.exists()
    combined_exists = combined_csv.exists()
    combined_stats = _combined_stats(combined_csv) if combined_exists else None

    status = {
        "companies": {
            "path": str(companies_csv),
            "exists": companies_exists,
            "rows": _count_csv_rows(companies_csv) if companies_exists else None,
            "updated": _format_mtime(companies_csv) if companies_exists else None,
        },
        "history": {
            "path": str(history_dir),
            "exists": history_exists,
            "files": sum(1 for _ in history_dir.glob("*.csv")) if history_exists else 0,
        },
        "combined": {
            "path": str(combined_csv),
            "exists": combined_exists,
            "rows": combined_stats[0] if combined_stats is not None else None,
            "updated": _format_mtime(combined_csv) if combined_exists else None,
            "date_range": combined_stats[1] if combined_stats is not None else None,
        },
    }
    return status
