"""Every saved model gets a version = timestamp string. predict.py and
backtest/ always load by explicit version (or "latest"), so a Signal or Order
row can always be traced back to the exact model that produced it."""
import json
from datetime import datetime, timezone
from pathlib import Path

MODELS_DIR = Path("data/models")


def _new_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_model(model, feature_columns: list[str], fold_metrics: list[dict],
              extra_meta: dict | None = None) -> str:
    version = _new_version()
    d = MODELS_DIR / version
    d.mkdir(parents=True, exist_ok=True)
    model.save_model(str(d / "model.txt"))
    meta = {
        "version": version,
        "feature_columns": feature_columns,
        "fold_metrics": fold_metrics,
        **(extra_meta or {}),
    }
    with open(d / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    _write_latest_pointer(version)
    return version


def _write_latest_pointer(version: str):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELS_DIR / "LATEST", "w") as f:
        f.write(version)


def latest_version() -> str | None:
    p = MODELS_DIR / "LATEST"
    if not p.exists():
        return None
    return p.read_text().strip()


def load_model(version: str | None = None):
    import lightgbm as lgb
    version = version or latest_version()
    if version is None:
        raise FileNotFoundError("No trained model found. Run scripts/train_model.py first.")
    d = MODELS_DIR / version
    model = lgb.Booster(model_file=str(d / "model.txt"))
    meta = json.loads((d / "meta.json").read_text())
    return model, meta
