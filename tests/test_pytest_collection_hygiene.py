from __future__ import annotations

import configparser
from pathlib import Path


def _pytest_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().parents[1] / "pytest.ini")
    return config



