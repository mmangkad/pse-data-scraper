"""
Helper utilities for formatting and filenames.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime
from typing import Union

logger = logging.getLogger(__name__)

PAYLOAD_DATE_FORMAT = "%m-%d-%Y"
OUTPUT_DATE_FORMAT = "%Y-%m-%d"

_cache_deprecation_logged = False


def log_cache_deprecation_once() -> None:
    """Log the one-release deprecation notice for the removed response cache."""
    global _cache_deprecation_logged
    if _cache_deprecation_logged:
        return
    _cache_deprecation_logged = True
    logger.warning(
        "The response cache is deprecated and no longer used; "
        "per-company CSVs are the source of truth."
    )


def ensure_payload_date(value: Union[str, date, datetime]) -> str:
    if isinstance(value, datetime):
        return value.strftime(PAYLOAD_DATE_FORMAT)
    if isinstance(value, date):
        return value.strftime(PAYLOAD_DATE_FORMAT)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime(PAYLOAD_DATE_FORMAT)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {text!r} (expected YYYY-MM-DD or MM-DD-YYYY)")


def format_output_date(value: date) -> str:
    return value.strftime(OUTPUT_DATE_FORMAT)


def sanitize_filename(value: str, max_length: int = 140) -> str:
    cleaned = html.unescape(value).strip()
    cleaned = cleaned.replace("&", "and")
    cleaned = re.sub(r"[\\/:\*\?\"<>\|]", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return "unknown"
    return cleaned[:max_length]
