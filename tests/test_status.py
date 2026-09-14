import csv
from pathlib import Path

from pse_data_scraper.status import collect_status

HISTORY_HEADER = ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"]


def _write_companies_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["companyId", "securityId", "companyName", "stockSymbol", "sector", "subsector", "listingDate"]
        )
        writer.writerow(["1", "2", "Test Corp", "TST", "Services", "Media", "2024-01-02"])


def _write_combined_csv(path: Path, *date_values: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HISTORY_HEADER)
        for value in date_values:
            writer.writerow(["TST", "Test Corp", value, "100", "10", "11", "12", "9"])


def test_collect_status_reports_all_sections(tmp_path):
    companies_csv = tmp_path / "companies.csv"
    history_dir = tmp_path / "history"
    combined_csv = tmp_path / "combined.csv"
    _write_companies_csv(companies_csv)
    history_dir.mkdir()
    (history_dir / "TST_Test_Corp.csv").touch()
    _write_combined_csv(combined_csv, "2024-01-02", "2024-01-05")

    status = collect_status(companies_csv, history_dir, combined_csv)

    assert status["companies"]["exists"] is True
    assert status["companies"]["rows"] == 1
    assert status["companies"]["updated"] is not None
    assert status["history"] == {"path": str(history_dir), "exists": True, "files": 1}
    assert status["combined"]["rows"] == 2
    assert status["combined"]["date_range"] == ("2024-01-02", "2024-01-05")


def test_collect_status_uses_latest_valid_dates(tmp_path):
    combined_csv = tmp_path / "combined.csv"
    _write_combined_csv(combined_csv, "2024-01-05", "not-a-date", "2024-01-02")

    status = collect_status(tmp_path / "missing.csv", tmp_path / "missing_dir", combined_csv)

    assert status["combined"]["rows"] == 3
    assert status["combined"]["date_range"] == ("2024-01-02", "2024-01-05")


def test_collect_status_with_no_parseable_dates(tmp_path):
    combined_csv = tmp_path / "combined.csv"
    _write_combined_csv(combined_csv, "not-a-date")

    status = collect_status(tmp_path / "missing.csv", tmp_path / "missing_dir", combined_csv)

    assert status["combined"]["rows"] == 1
    assert status["combined"]["date_range"] is None


def test_collect_status_missing_artifacts(tmp_path):
    status = collect_status(tmp_path / "c.csv", tmp_path / "h", tmp_path / "comb.csv")

    assert status["companies"]["exists"] is False
    assert status["companies"]["rows"] is None
    assert status["history"]["exists"] is False
    assert status["history"]["files"] == 0
    assert status["combined"]["exists"] is False
    assert status["combined"]["rows"] is None
    assert status["combined"]["date_range"] is None
