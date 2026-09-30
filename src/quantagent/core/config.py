from functools import lru_cache
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def _load(name: str) -> dict:
    with open(ROOT / "config" / name) as f:
        return yaml.safe_load(f) or {}


@lru_cache
def settings() -> dict:
    return _load("settings.yaml")


@lru_cache
def risk() -> dict:
    return _load("risk.yaml")


def database_url() -> str:
    return os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'quant.db'}")
