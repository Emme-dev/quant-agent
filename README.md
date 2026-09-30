# quant-agent
ML + agent-driven daily crypto trading. Personal use first, multi-user ready.

## Setup
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    cp .env.example .env

## Day 1: data
    python scripts/backfill.py      # builds universe, stores ~365d daily candles
    pytest                          # ingest idempotency test

Paper mode is the default. Do not add live keys before Day 7.
