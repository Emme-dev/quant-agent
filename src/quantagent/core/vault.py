"""The ONLY place that touches exchange secrets.
Today: env vars. Later: per-account encrypted storage / KMS."""
import os


def get_api_keys(account_id: int | None = None) -> dict:
    return {
        "apiKey": os.getenv("EXCHANGE_API_KEY", ""),
        "secret": os.getenv("EXCHANGE_API_SECRET", ""),
    }
