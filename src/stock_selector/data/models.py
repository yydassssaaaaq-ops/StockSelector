from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AShareQuote:
    code: str
    name: str
    exchange: str
    board: str
    latest_price: float | None
    pct_change: float | None
    volume: int | None
    amount: float | None
    amplitude: float | None
    turnover_rate: float | None
    pe_ttm: float | None
    volume_ratio: float | None
    high: float | None
    low: float | None
    open: float | None
    previous_close: float | None
    total_market_cap: float | None
    float_market_cap: float | None
    pb: float | None
    main_net_inflow: float | None
    main_net_inflow_pct: float | None
    quote_time: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DailyBar:
    code: str
    name: str
    exchange: str
    board: str
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float
    amplitude: float | None
    pct_change: float | None
    change_amount: float | None
    turnover_rate: float | None
    adjustment: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_quote(self) -> AShareQuote:
        previous_close = None
        if self.pct_change not in (None, -100.0):
            previous_close = self.close / (1.0 + self.pct_change / 100.0)
        return AShareQuote(
            code=self.code,
            name=self.name,
            exchange=self.exchange,
            board=self.board,
            latest_price=self.close,
            pct_change=self.pct_change,
            volume=self.volume,
            amount=self.amount,
            amplitude=self.amplitude,
            turnover_rate=self.turnover_rate,
            pe_ttm=None,
            volume_ratio=None,
            high=self.high,
            low=self.low,
            open=self.open,
            previous_close=previous_close,
            total_market_cap=None,
            float_market_cap=None,
            pb=None,
            main_net_inflow=None,
            main_net_inflow_pct=None,
            quote_time=f"{self.date}T15:00:00+08:00",
        )


@dataclass(frozen=True)
class HistoricalSeries:
    code: str
    name: str
    exchange: str
    board: str
    source: str
    adjustment: str
    requested_start: str
    requested_end: str
    fetched_at: str
    bars: list[DailyBar]
    cache_hit: bool
    completeness: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["bars"] = [bar.as_dict() for bar in self.bars]
        return data


@dataclass(frozen=True)
class DataFetchFailure:
    code: str
    name: str
    source: str
    requested_start: str
    requested_end: str
    error: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
