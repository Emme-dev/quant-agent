"""Standard backtest metrics, computed the same way for the strategy and the
buy-and-hold benchmark so the comparison is apples-to-apples."""
import numpy as np
import pandas as pd


def sharpe_ratio(daily_returns: pd.Series, periods_per_year: int = 365) -> float:
    r = daily_returns.dropna()
    if r.std(ddof=0) == 0 or len(r) < 2:
        return 0.0
    return float(r.mean() / r.std(ddof=0) * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return float(drawdown.min())


def cagr(equity_curve: pd.Series, periods_per_year: int = 365) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] <= 0:
        return 0.0
    n_periods = len(equity_curve) - 1
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    if total_return <= 0:
        return -1.0
    return float(total_return ** (periods_per_year / n_periods) - 1)


def summarize(equity_curve: pd.Series, daily_returns: pd.Series,
             turnover: pd.Series | None = None) -> dict:
    out = {
        "sharpe": sharpe_ratio(daily_returns),
        "cagr": cagr(equity_curve),
        "max_drawdown": max_drawdown(equity_curve),
        "final_equity": float(equity_curve.iloc[-1]),
        "n_days": int(len(equity_curve)),
    }
    if turnover is not None:
        out["avg_turnover"] = float(turnover.mean())
    return out
