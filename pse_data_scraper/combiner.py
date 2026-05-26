"""
Combine per-company CSVs into a single dataset.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, List

logger = logging.getLogger(__name__)


def _iter_csv_files(data_folder: Path) -> Iterable[Path]:
    return data_folder.glob("*.csv")


def combine_csvs(data_folder: str = "data/history", output_file: str = "data/combined.csv") -> Path:
    input_folder = Path(data_folder)
    output_path = Path(output_file)
    csv_files: List[Path] = sorted(_iter_csv_files(input_folder))

    if not csv_files:
        logger.warning("No CSV files found in %s", data_folder)
        return output_path

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["Symbol", "Company", "Date", "Value", "Open", "Close", "High", "Low"])

        for file_path in csv_files:
            with file_path.open("r", encoding="utf-8") as infile:
                reader = csv.DictReader(infile)
                if not reader.fieldnames or "Symbol" not in reader.fieldnames:
                    logger.warning("Skipping file with unexpected format: %s", file_path.name)
                    continue
                for row in reader:
                    writer.writerow(
                        [
                            row.get("Symbol", ""),
                            row.get("Company", ""),
                            row.get("Date", ""),
                            row.get("Value", ""),
                            row.get("Open", ""),
                            row.get("Close", ""),
                            row.get("High", ""),
                            row.get("Low", ""),
                        ]
                    )

    logger.info("All files combined into: %s", output_path)
    return output_path
