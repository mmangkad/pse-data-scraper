from datetime import date

from pse_data_scraper.utils import ensure_payload_date, sanitize_filename


def test_sanitize_filename_basic():
    assert sanitize_filename("ACME/Corp & Co") == "ACME-Corp_and_Co"


def test_ensure_payload_date_for_date():
    assert ensure_payload_date(date(2024, 1, 2)) == "01-02-2024"


def test_ensure_payload_date_for_iso_string():
    assert ensure_payload_date("2024-01-02") == "01-02-2024"
