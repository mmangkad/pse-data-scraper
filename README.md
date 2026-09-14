# PSE Data Scraper

PSE Data Scraper pulls company lists and historical price data from PSE EDGE,
then exports them to CSV for analysis. It includes a CLI, retry logic, and a
small Python API.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the full pipeline:

```bash
python -m pse_data_scraper sync
```

The first run scrapes the company directory, downloads the full price
history for every company, and exports `data/combined.csv`. Re-running
`sync` is cheap: existing per-company files are updated **incrementally**
(only dates after the last one on disk are fetched and merged). Use
`--refresh` to re-download from scratch.

You can also run the direct entry point (same defaults as `pse sync`):

```bash
python main.py
```

## CLI Usage

Install locally for the `pse` command:

```bash
pip install -e .
```

Examples:

```bash
pse sync
pse companies --refresh
pse companies --sector "Mining and Oil" --list
pse prices --symbols BDO,ALI --from 2020-01-01 --to 2024-01-01
pse export --format csv
pse status
pse status --json
```

Common options:

- `--rate-limit` sets the delay between requests.
- `--symbols` limits downloads to specific tickers. Symbols missing from the
  directory warn (EDGE lists primary securities only — no preferreds,
  warrants, or delisted names); if none match, the command exits 1.
- `--sector` / `--keyword` filter by sector or company name. They apply
  server-side when the directory is scraped and locally when
  `companies.csv` already exists. The SME board's sector value is the
  literal string `Small, Medium & Emerging Board`.
- `--max-companies` is useful for quick test runs.
- `--refresh` re-downloads price history (`prices`), re-scrapes the
  directory (`companies`), or both (`sync`).
- `--cache-dir` / `--no-cache` are deprecated no-ops; per-company CSVs are the source of truth.
- Dates accept `MM-DD-YYYY` or `YYYY-MM-DD`.
- PSE EDGE data lags ~1 trading day: a run today includes data through the
  most recent completed trading day.

## Configuration

Generate a starter config:

```bash
pse init
```

By default, the CLI reads `pse.toml` from the current directory. You can
override it with `--config path/to/pse.toml`.

Example `pse.toml`:

```toml
[paths]
data_dir = "data"

[network]
rate_limit = 0.6

[download]
start_date = "2020-01-01"
symbols = ["BDO", "ALI"]
# sector = "Mining and Oil"
# keyword = "Ayala"
```

## Python API

```python
from pse_data_scraper.client import PSEClient
from pse_data_scraper.scraper import scrape_companies, save_companies_to_csv
from pse_data_scraper.downloader import download_historical_data
from pse_data_scraper.combiner import combine_csvs

client = PSEClient(rate_limit_seconds=0.6)
companies = scrape_companies(client)
save_companies_to_csv(companies, "data/companies.csv")
report = download_historical_data(client, companies=companies, output_dir="data/history")
# report.status_counts, e.g. {"saved_full": 282, "up_to_date": 0, ...}
combine_csvs("data/history", "data/combined.csv")
```

## Output Files

- `data/companies.csv` - company list:
  `companyId,securityId,companyName,stockSymbol,sector,subsector,listingDate`
  (dates as ISO `YYYY-MM-DD`; legacy 4-column files still load)
- `data/history/` - one CSV per company:
  `Symbol,Company,Date,Value,Open,Close,High,Low` with ISO dates.
  `Value` is **PHP turnover, not share volume** — the API provides no volume
  field (see `docs/API.md`).
- `data/combined.csv` - consolidated price dataset

## API Notes

The scraper uses endpoints observed from PSE EDGE. See `docs/API.md` for the
full behavioral reference (formats, strictness, quirks, and coverage limits,
verified 2026-09-15).

## Structure

```
pse-data-scraper/
├── main.py
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── pse_data_scraper/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── client.py
│   ├── combiner.py
│   ├── config.py
│   ├── downloader.py
│   ├── models.py
│   ├── pipeline.py
│   ├── scraper.py
│   ├── status.py
│   └── utils.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_cli.py
│   ├── test_client.py
│   ├── test_combiner.py
│   ├── test_config.py
│   ├── test_downloader.py
│   ├── test_models.py
│   ├── test_pipeline.py
│   ├── test_scraper.py
│   ├── test_sort.py
│   ├── test_status.py
│   └── test_utils.py
└── docs/
    └── API.md
```

## Development

```bash
pip install -e .
pip install -r requirements-dev.txt
pytest
```

## License

MIT. See `LICENSE`.
