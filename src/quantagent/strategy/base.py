from abc import ABC, abstractmethod
import pandas as pd


class Strategy(ABC):
    """Turns a day's scored symbols into target portfolio weights (0..1 each,
    summing to <=1). Kept as an interface so a second strategy can be added
    later without touching the backtest engine or execution layer."""

    @abstractmethod
    def target_weights(self, day_scores: pd.DataFrame) -> dict[str, float]:
        """day_scores: rows for ONE date, columns symbol, score."""
        raise NotImplementedError
