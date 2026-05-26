import csv
from datetime import date
from pathlib import Path

from pse_data_scraper.models import Company, HistoricalPrice
from pse_data_scraper.downloader import write_company_history_csv


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows[0], rows[1:]


def test_write_company_history_csv_includes_company_column(tmp_path: Path):
    company = Company(company_id="1", security_id="2", company_name="BDO Unibank, Inc.", stock_symbol="BDO")
    rows = [
        HistoricalPrice(date=date(2024, 1, 2), symbol="BDO", value="100", open="10", close="11", high="12", low="9"),
        HistoricalPrice(date=date(2024, 1, 3), symbol="BDO", value="200", open="11", close="12", high="13", low="10"),
    ]

    output_path = tmp_path / "BDO_BDO_Unibank,_Inc.csv"
    write_company_history_csv(output_path, company, rows)

    header, data = _read_csv(output_path)
    assert header == ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"]
    assert data[0][1] == "BDO Unibank, Inc."
    assert data[1][1] == "BDO Unibank, Inc."
    assert data[0][0] == "BDO"


def test_write_company_history_csv_creates_parent_dirs(tmp_path: Path):
    company = Company(company_id="1", security_id="2", company_name="Test", stock_symbol="TST")
    output_path = tmp_path / "nested" / "dir" / "TST_Test.csv"

    write_company_history_csv(output_path, company, [])

    header, data = _read_csv(output_path)
    assert header == ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"]
    assert data == []
