"""
Status helpers for local datasets.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

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


def _combined_date_range(path: Path) -> Optional[Tuple[str, str]]:
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
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

    if min_date is None or max_date is None:
        return None
    return (min_date.date().isoformat(), max_date.date().isoformat())


def collect_status(
    companies_csv: Path,
    history_dir: Path,
    combined_csv: Path,
) -> Dict[str, Dict[str, object]]:
    companies_exists = companies_csv.exists()
    history_exists = history_dir.exists()
    combined_exists = combined_csv.exists()

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
            "rows": _count_csv_rows(combined_csv) if combined_exists else None,
            "updated": _format_mtime(combined_csv) if combined_exists else None,
            "date_range": _combined_date_range(combined_csv) if combined_exists else None,
        },
    }
    return status
