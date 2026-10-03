# quant-agent

ML-driven crypto trading with a daily/intraday rebalance, built incrementally
over 7 days. Paper trading by default, personal use first, structured so a
second account could be added later without a rewrite.

**Status as of Day 7:** fully wired end-to-end (data → features → model →
backtest → risk → paper execution → daily report → scheduler → status API).
**Not yet profitable after costs** on the data tested so far — see
[Honest results](#honest-results-so-far) below. Still paper-only; see
[Going live](#going-live-not-automatic).

---

## Setup

```powershell
cd quant-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
pytest
```

`.env` holds exchange API keys for **live** trading only — leave it blank
for paper trading, which is the default and the only mode actually wired up
right now (see [Going live](#going-live-not-automatic)).

## Configuration

- **`config/settings.yaml`** — exchange, quote currency, timeframe, universe
  filters (top-N by liquidity), default account name.
- **`config/risk.yaml`** — starting paper capital, position/exposure caps,
  daily loss limit, kill switch, fee/slippage assumptions, strategy top-K.

`timeframe` supports `1m, 5m, 15m, 1h, 4h, 1d` — changing it is a one-line
edit; every downstream calculation (feature windows, walk-forward splits,
Sharpe/CAGR annualization, the scheduler's cron) adapts automatically. See
[core/timeframes.py](#how-the-pieces-fit-together). Switching timeframes
means a different dataset, not an extension of the current one — rerun the
pipeline from `backfill.py` onward after changing it.

## The pipeline, in order

Each step has its own script and reads what the previous one wrote. Run them
in this order the first time; after that, most are re-run independently as
new data arrives.

| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `scripts/backfill.py` | Builds the liquid-pair universe, downloads history | `data/quant.db` |
| 2 | `scripts/build_dataset.py` | Builds leakage-checked features + targets | `data/training_table.parquet` |
| 3 | `scripts/train_model.py` | Walk-forward trains a LightGBM model | `data/models/<version>/` |
| 4 | `scripts/run_backtest.py` | Backtests on out-of-sample predictions, with costs | `data/backtest_daily.csv` |
| 5 | `scripts/tune_backtest.py` | Compares top-K / rebalance-frequency variants (optional) | console only |
| 6 | `scripts/run_daily_agent.py` | Runs one full trading day, paper-executes, saves a report | `data/reports/<timestamp>.md` |
| 7 | `scripts/run_scheduler.py` | Runs step 6 automatically, forever, on a schedule | — |

Re-run 1→2→3→4 whenever you want to retrain (e.g. weekly, or after
accumulating meaningfully more history). Step 6 (or 7) is the one you run
— or schedule — every trading day.

**Other utilities:**
- `scripts/run_paper_day.py` — same as step 6 but concise console-only output, no saved report.
- `scripts/reset_killswitch.py` — clears a tripped kill switch after you've reviewed why it tripped. Requires typing `reset`.

## Status API (read-only)

```powershell
uvicorn quantagent.api.main:app --port 8000
```

Then visit `http://127.0.0.1:8000/docs`. Endpoints: `/health`, `/status`
(positions, kill switch, last run), `/runs` (recent run history),
`/killswitch`. **Deliberately has no endpoint that places an order, changes
a risk limit, or resets the kill switch** — those stay CLI-only, so an
unauthenticated local API can't be used to move money or bypass a halt.

## Running unattended

```powershell
python scripts/run_scheduler.py
```

Fires once per bar (a few minutes after each bar closes), matching
whatever `timeframe` is set in `config/settings.yaml`. Runs in the
foreground — for real unattended operation (surviving a reboot, running
without a logged-in session), run this under a process manager: Task
Scheduler on Windows, `systemd` or `pm2` on Linux. The scheduler itself
doesn't daemonize or auto-restart on crash; a process manager is what
provides that.

## Honest results so far

On the data tested, the model's directional accuracy sits close to a coin
flip (~0.45–0.53), and the backtest showed the strategy **losing** money
relative to simply holding the basket, mostly because near-daily full
portfolio rotation makes fees and slippage add up fast (see
`scripts/tune_backtest.py` for the top-K/rebalance-frequency comparison).
This is the backtest and risk layer doing their job — catching a model
that isn't ready, before any real capital was at risk — not a failure of
the pipeline. Treat current output as infrastructure validation, not a
trading signal to act on yet.

## Safety layers (in order they'd stop a bad day)

1. **Risk rules** (`risk/rules.py`) — caps any single position, caps total
   exposure, and halts all trading outright if the daily loss limit is hit.
2. **Kill switch** (`risk/killswitch.py`) — a file on disk, not just an
   in-memory flag. Once tripped by a real breach, it stays tripped across
   restarts until a human reviews it and runs `scripts/reset_killswitch.py`.
3. **Paper broker only** — see below. Nothing here can place a real order
   yet, regardless of config.
4. **Data-quality warnings** (`agent/data_quality.py`) — flagged in every
   report, separately from the risk halt decision, so a feed problem is
   visible even on a day that still traded normally.

## Going live (not automatic)

`execution/live.py` exists and refuses to even construct unless
`config/settings.yaml` has `mode: live` **and** real API keys are in
`.env`. But `agent/orchestrator.py` — the thing that actually runs every
day — **always constructs the paper broker**, regardless of that config
value. Going live requires editing that line in the code, not flipping a
config flag, deliberately: a config value is too easy to change by
accident or copy from an example; a code edit is not.

Before making that edit yourself:
1. Run on paper for long enough to trust the model's recent behavior, not
   just one backtest.
2. If your exchange offers a sandbox/testnet, run there first with fake
   funds hitting real order-placement code paths. (Kraken, this project's
   default, does not currently offer a public spot testnet — Binance and
   some others do, if you want to test against a sandbox before using
   real funds on any exchange.)
3. Use an API key scoped to **trading only** — withdrawals disabled, IP
   whitelisted if your exchange supports it.
4. Start with an amount you could fully lose without it mattering.

## Known limitations / honest scope cuts

- **Long-only.** No shorting — that adds borrow costs and margin risk
  deliberately left out of this scope.
- **Daily-loss-limit tracking is calendar-day**, independent of the
  trading timeframe, on purpose — a true daily circuit breaker regardless
  of how often the model trades within a day.
- **No authentication** anywhere (API, scheduler). This is built for
  single-user local/personal use. Multi-user structure exists in the
  schema (`account_id` on every table) but auth, billing, and a UI were
  explicitly not built — see the original 7-day plan's scope cuts.
- **The "AI agent" here is orchestration + deterministic reporting, not an
  LLM with trading authority.** `agent/report.py` formats a day's results
  into plain English with a template, not a model call — sizing and risk
  decisions live entirely in `risk/` and `strategy/`, and nothing in
  `agent/tools.py` can place an order or change a limit. This was a
  deliberate design choice from the start, not a missing feature.

## How the pieces fit together

```
quant-agent/
├── config/                  settings.yaml, risk.yaml
├── data/                    quant.db, training_table.parquet, models/,
│                            reports/, paper_state.json, kill_switch.flag
│                            (all gitignored except .gitkeep)
├── scripts/                 one script per pipeline step (see table above)
├── tests/                   pytest; pure-logic tests need no network/DB
└── src/quantagent/
    ├── core/                config loading, DB session, logging,
    │                        timeframe<->calendar conversion, vault (API keys)
    ├── data/                exchange wrapper (ccxt), universe builder
    │                        (with same-day fallback), candle ingestion
    ├── features/             leakage-checked feature + target engineering
    ├── ml/                  walk-forward training, prediction, model registry
    ├── backtest/             cost model, Sharpe/CAGR/drawdown, simulation engine
    ├── strategy/             Strategy interface + the daily-rank strategy
    ├── risk/                position/exposure caps, daily loss limit,
    │                        kill switch, order sizing
    ├── execution/            Broker interface, PaperBroker (JSON ledger),
    │                        LiveBroker (built, not wired in -- see above)
    ├── agent/                orchestrator (ties the daily job together),
    │                        plain-English report, data-quality checks,
    │                        read-only status helpers
    ├── jobs/                 what the daily job does + the scheduler
    └── api/                  read-only FastAPI status endpoints
```

Run `pytest` any time — it's the fastest way to confirm nothing's broken
after a config or code change, and most of it needs neither a network
connection nor the database.
