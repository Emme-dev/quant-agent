from datetime import datetime, timezone
from sqlalchemy import (BigInteger, DateTime, Float, ForeignKey, Integer,
                        String, UniqueConstraint, Index, JSON)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Account(Base):
    """One row for now. Multi-user later without a schema rewrite."""
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    mode: Mapped[str] = mapped_column(String(8), default="paper")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Candle(Base):
    """Market data is shared across accounts, so no account_id here."""
    __tablename__ = "candles"
    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    ts: Mapped[int] = mapped_column(BigInteger)  # candle open, ms UTC
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "ts", name="uq_candle"),
        Index("ix_candle_lookup", "exchange", "symbol", "timeframe", "ts"),
    )


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String(16), default="running")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32))
    ts: Mapped[int] = mapped_column(BigInteger)
    score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64))


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(4))
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new")
    is_paper: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(32))
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_position"),)
