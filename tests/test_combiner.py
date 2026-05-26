import csv
from pathlib import Path

from pse_data_scraper.combiner import combine_csvs


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def _read_combined(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_combine_reads_company_from_csv(tmp_path: Path):
    """Company name should come from the CSV data, not the filename."""
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    _write_csv(
        input_dir / "BDO_something.csv",
        ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"],
        [["BDO", "BDO Unibank, Inc.", "2024-01-01", "100", "10", "11", "12", "9"]],
    )

    output = tmp_path / "combined.csv"
    combine_csvs(str(input_dir), str(output))

    rows = _read_combined(output)
    assert len(rows) == 1
    assert rows[0]["Symbol"] == "BDO"
    assert rows[0]["Company"] == "BDO Unibank, Inc."


def test_combine_multiple_files(tmp_path: Path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    _write_csv(
        input_dir / "a.csv",
        ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"],
        [["AC", "Ayala Corporation", "2024-01-02", "50", "700", "710", "715", "695"]],
    )
    _write_csv(
        input_dir / "b.csv",
        ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"],
        [["BDO", "BDO Unibank, Inc.", "2024-01-02", "200", "129", "130", "131", "128"]],
    )

    output = tmp_path / "combined.csv"
    combine_csvs(str(input_dir), str(output))

    rows = _read_combined(output)
    assert len(rows) == 2
    assert rows[0]["Symbol"] == "AC"
    assert rows[1]["Symbol"] == "BDO"


def test_combine_skips_files_without_symbol_column(tmp_path: Path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    _write_csv(
        input_dir / "good.csv",
        ["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"],
        [["AC", "Ayala Corp", "2024-01-02", "50", "700", "710", "715", "695"]],
    )
    _write_csv(
        input_dir / "bad.csv",
        ["Date", "Price"],
        [["2024-01-02", "710"]],
    )

    output = tmp_path / "combined.csv"
    combine_csvs(str(input_dir), str(output))

    rows = _read_combined(output)
    assert len(rows) == 1
    assert rows[0]["Symbol"] == "AC"


def test_combine_empty_directory(tmp_path: Path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    output = tmp_path / "combined.csv"

    combine_csvs(str(input_dir), str(output))

    assert not output.exists() or output.stat().st_size == 0 or _read_combined(output) == []
