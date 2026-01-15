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
