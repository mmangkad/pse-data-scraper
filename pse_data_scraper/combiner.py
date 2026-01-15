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


def combine_csvs(data_folder: str = "historicaldata", output_file: str = "combined.csv") -> Path:
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
            filename = file_path.stem
            if "_" not in filename:
                logger.warning("Skipping malformed filename: %s", filename)
                continue
            symbol, company = filename.split("_", 1)

            with file_path.open("r", encoding="utf-8") as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    writer.writerow(
                        [
                            row.get("Symbol") or symbol,
                            company,
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
