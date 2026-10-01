from abc import ABC, abstractmethod


class Broker(ABC):
    """Same interface for paper and live, so the daily job code never
    branches on mode -- only which Broker instance gets constructed does."""

    @abstractmethod
    def get_cash(self) -> float: ...

    @abstractmethod
    def get_positions(self) -> dict[str, float]: ...

    @abstractmethod
    def equity(self, prices: dict[str, float]) -> float: ...

    @abstractmethod
    def execute_orders(self, orders: list[dict], run_id: int | None = None) -> list[dict]: ...
