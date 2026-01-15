# PSE Data Scraper

PSE Data Scraper pulls company lists and historical price data from PSE EDGE,
then exports them to CSV for analysis. It includes a CLI, retry logic, optional
caching, and a small Python API.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the full pipeline:

```bash
python -m pse_data_scraper sync
```

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
pse prices --symbols BDO,ALI --from 2020-01-01 --to 2024-01-01
pse export --format csv
pse status
```

Common options:

- `--rate-limit` sets the delay between requests.
- `--symbols` limits downloads to specific tickers.
- `--max-companies` is useful for quick test runs.
- `--refresh` forces re-downloads even if files exist.
- `--no-cache` disables cached API responses.
- Dates accept `MM-DD-YYYY` or `YYYY-MM-DD`.

Legacy commands (still supported): `scrape`, `download`, `combine`, `all`.

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
cache_dir = ".cache"

[network]
rate_limit = 0.8

[download]
start_date = "2020-01-01"
symbols = ["BDO", "ALI"]
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
download_historical_data(client, input_csv="data/companies.csv", output_dir="data/history")
combine_csvs("data/history", "data/combined.csv")
```

## Output Files

- `data/companies.csv` - company list with IDs and symbols
- `data/history/` - one CSV per company
- `data/combined.csv` - consolidated price dataset
- `.cache/` - optional cached API responses

## API Notes

The scraper uses endpoints observed from PSE EDGE. See `docs/API.md` for
payload and response details.

## Structure

```
pse-data-scraper/
├── main.py
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── pse_data_scraper/
│   ├── cli.py
│   ├── client.py
│   ├── config.py
│   ├── downloader.py
│   ├── models.py
│   ├── pipeline.py
│   ├── scraper.py
│   ├── status.py
│   └── utils.py
├── utils/               # compatibility wrappers
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
