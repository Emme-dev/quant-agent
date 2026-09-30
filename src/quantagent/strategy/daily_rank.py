"""Simplest possible strategy: go long the top-K highest-scored symbols,
equal weight. Long-only on purpose for Day 4 -- shorting adds borrow costs
and margin risk that belong in a later, explicit risk-review pass."""
import pandas as pd
from .base import Strategy


class DailyRankStrategy(Strategy):
    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def target_weights(self, day_scores: pd.DataFrame) -> dict[str, float]:
        top = day_scores.sort_values("score", ascending=False).head(self.top_k)
        if top.empty:
            return {}
        w = 1.0 / len(top)
        return {row.symbol: w for row in top.itertuples()}
