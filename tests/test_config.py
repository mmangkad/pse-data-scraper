import logging

from pse_data_scraper.config import load_config


def test_load_config_resolves_paths(tmp_path):
    config_text = """
[paths]
data_dir = "data"

[download]
symbols = ["bdo", "ALI"]
max_companies = 5
"""
    config_path = tmp_path / "pse.toml"
    config_path.write_text(config_text, encoding="utf-8")

    config = load_config(str(config_path))

    assert config.data_dir == tmp_path / "data"
    assert config.companies_csv == tmp_path / "data" / "companies.csv"
    assert config.history_dir == tmp_path / "data" / "history"
    assert config.combined_csv == tmp_path / "data" / "combined.csv"
    assert config.symbols == ["BDO", "ALI"]
    assert config.max_companies == 5


def test_load_config_reads_sector_and_keyword(tmp_path):
    config_text = """
[paths]
data_dir = "data"

[download]
sector = "Mining and Oil"
keyword = "Ayala"
"""
    config_path = tmp_path / "pse.toml"
    config_path.write_text(config_text, encoding="utf-8")

    config = load_config(str(config_path))

    assert config.sector == "Mining and Oil"
    assert config.keyword == "Ayala"


def test_load_config_cache_dir_is_deprecated_but_parsed(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr("pse_data_scraper.utils._cache_deprecation_logged", False)
    config_text = """
[paths]
data_dir = "data"
cache_dir = ".cache"
"""
    config_path = tmp_path / "pse.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        config = load_config(str(config_path))

    assert config.cache_dir == tmp_path / ".cache"
    assert "no longer used" in caplog.text
