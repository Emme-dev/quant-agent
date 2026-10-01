"""A breach during one run must stay tripped for every future run until a
human clears it -- otherwise tomorrow's job just retries and can lose money
the same way again. This is deliberately a file on disk, not a DB row or an
in-memory flag, so it survives a crash, a redeploy, or a config reload."""
from pathlib import Path

FLAG_PATH = Path("data/kill_switch.flag")


def is_tripped() -> bool:
    return FLAG_PATH.exists()


def trip(reason: str):
    FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLAG_PATH.write_text(reason)


def reset():
    if FLAG_PATH.exists():
        FLAG_PATH.unlink()


def reason() -> str | None:
    if FLAG_PATH.exists():
        return FLAG_PATH.read_text()
    return None
