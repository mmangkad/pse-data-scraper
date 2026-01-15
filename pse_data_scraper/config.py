"""
Configuration loading and defaults for the PSE Data Scraper CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover - fallback for Python <3.11
    import tomli as tomllib  # type: ignore

DEFAULT_CONFIG_NAME = "pse.toml"
DEFAULT_DATA_DIR = "data"
DEFAULT_CACHE_DIR = ".cache"

DEFAULT_CONFIG_TEXT = """# PSE Data Scraper configuration

[paths]
# Root data directory (derived files live below this).
data_dir = "data"

# Optional explicit paths (override data_dir defaults).
# companies_csv = "data/companies.csv"
# history_dir = "data/history"
# combined_csv = "data/combined.csv"
cache_dir = ".cache"

[network]
rate_limit = 0.6

[download]
# start_date = "1900-01-01"
# end_date = ""
# symbols = ["BDO", "ALI"]
# max_companies = 0
"""


def _resolve_path(value: Optional[object], base_dir: Path) -> Optional[Path]:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        return base_dir / path
    return path


def _parse_symbols(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        return []
    return [item.upper() for item in items if item]


def _normalize_positive_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@dataclass
class Config:
    data_dir: Path = Path(DEFAULT_DATA_DIR)
    companies_csv: Optional[Path] = None
    history_dir: Optional[Path] = None
    combined_csv: Optional[Path] = None
    cache_dir: Optional[Path] = Path(DEFAULT_CACHE_DIR)
    rate_limit: float = 0.6
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    max_companies: Optional[int] = None

    def resolve_paths(self) -> None:
        data_dir = Path(self.data_dir)
        self.companies_csv = (
            Path(self.companies_csv)
            if self.companies_csv is not None
            else data_dir / "companies.csv"
        )
        self.history_dir = (
            Path(self.history_dir)
            if self.history_dir is not None
            else data_dir / "history"
        )
        self.combined_csv = (
            Path(self.combined_csv)
            if self.combined_csv is not None
            else data_dir / "combined.csv"
        )


def _read_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def find_config(path: Optional[str] = None) -> Optional[Path]:
    if path is None:
        candidate = Path(DEFAULT_CONFIG_NAME)
        return candidate if candidate.exists() else None
    candidate = Path(path)
    if not candidate.exists():
        raise FileNotFoundError(f"Config file not found: {candidate}")
    return candidate


def load_config(path: Optional[str] = None) -> Config:
    config_path = find_config(path)
    if config_path is None:
        config = Config()
        config.resolve_paths()
        return config

    base_dir = config_path.parent
    data: dict = _read_toml(config_path)

    paths = data.get("paths", {})
    network = data.get("network", {})
    download = data.get("download", {})

    config = Config()
    config.data_dir = _resolve_path(paths.get("data_dir", config.data_dir), base_dir) or config.data_dir
    config.companies_csv = _resolve_path(paths.get("companies_csv"), base_dir)
    config.history_dir = _resolve_path(paths.get("history_dir"), base_dir)
    config.combined_csv = _resolve_path(paths.get("combined_csv"), base_dir)

    cache_value = paths.get("cache_dir", config.cache_dir)
    if cache_value in (None, "", False):
        config.cache_dir = None
    else:
        config.cache_dir = _resolve_path(cache_value, base_dir)

    rate_limit = network.get("rate_limit", data.get("rate_limit"))
    if rate_limit is not None:
        config.rate_limit = float(rate_limit)

    if "start_date" in download:
        config.start_date = str(download["start_date"])
    if "end_date" in download and download["end_date"]:
        config.end_date = str(download["end_date"])
    if "symbols" in download:
        config.symbols = _parse_symbols(download["symbols"])
    if "max_companies" in download:
        config.max_companies = _normalize_positive_int(download["max_companies"])

    config.resolve_paths()
    return config


def write_default_config(path: Path, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return True
