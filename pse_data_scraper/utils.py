"""
Helper utilities for formatting and filenames.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Union

PAYLOAD_DATE_FORMAT = "%m-%d-%Y"
OUTPUT_DATE_FORMAT = "%d/%m/%Y"


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
    return text


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
