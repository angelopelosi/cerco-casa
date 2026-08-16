# tests/test_config.py
from pathlib import Path
import yaml

def test_config_has_required_keys():
    config = yaml.safe_load(Path("config.yaml").read_text())
    assert "centro" in config
    assert "nome" in config["centro"]
    assert "lat" in config["centro"]
    assert "lon" in config["centro"]
    assert "raggio_km" in config
    assert isinstance(config["portali_attivi"], list)
    assert "email" in config and "destinatari" in config["email"]
