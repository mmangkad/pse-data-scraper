from datetime import date, datetime

import pytest

from pse_data_scraper.utils import ensure_payload_date, format_output_date, sanitize_filename


def test_sanitize_filename_basic():
    assert sanitize_filename("ACME/Corp & Co") == "ACME-Corp_and_Co"


def test_sanitize_filename_strips_special_chars():
    assert sanitize_filename('A:B?C"D|E') == "A-B-C-D-E"


def test_sanitize_filename_collapses_underscores():
    assert sanitize_filename("A   B") == "A_B"


def test_ensure_payload_date_for_date():
    assert ensure_payload_date(date(2024, 1, 2)) == "01-02-2024"


def test_ensure_payload_date_for_datetime():
    assert ensure_payload_date(datetime(2024, 6, 15, 10, 30)) == "06-15-2024"


def test_ensure_payload_date_for_iso_string():
    assert ensure_payload_date("2024-01-02") == "01-02-2024"


def test_ensure_payload_date_for_us_format_string():
    assert ensure_payload_date("01-02-2024") == "01-02-2024"


def test_ensure_payload_date_raises_on_garbage():
    with pytest.raises(ValueError, match="Cannot parse date"):
        ensure_payload_date("not-a-date")


def test_ensure_payload_date_raises_on_empty():
    with pytest.raises(ValueError, match="Cannot parse date"):
        ensure_payload_date("")


def test_format_output_date_iso8601():
    assert format_output_date(date(2024, 1, 2)) == "2024-01-02"
    assert format_output_date(date(2023, 12, 31)) == "2023-12-31"
