from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class PerformanceMetrics:
    cumulative_return: float
    annualized_return: float
    max_drawdown: float
    annualized_volatility: float
    sharpe_ratio: float | None
    win_rate: float
    average_period_return: float
    best_period_return: float
    worst_period_return: float
    turnover_rate: float
    trade_count: int
    effective_periods: int
    excess_cumulative_return: float | None = None

    def as_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def compound_returns(returns: list[float]) -> list[float]:
    equity = 1.0
    curve: list[float] = []
    for value in returns:
        equity *= 1.0 + value
        curve.append(equity - 1.0)
    return curve


def cumulative_return(returns: list[float]) -> float:
    curve = compound_returns(returns)
    return curve[-1] if curve else 0.0


def annualized_return(returns: list[float], periods_per_year: int) -> float:
    if not returns:
        return 0.0
    cumulative = cumulative_return(returns)
    if cumulative <= -1.0:
        return -1.0
    return (1.0 + cumulative) ** (periods_per_year / len(returns)) - 1.0


def annualized_volatility(returns: list[float], periods_per_year: int) -> float:
    if len(returns) < 2:
        return 0.0
    return pstdev(returns) * math.sqrt(periods_per_year)


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        worst = min(worst, drawdown)
    return abs(worst)


def sharpe_ratio(returns: list[float], periods_per_year: int, risk_free_rate: float = 0.0) -> float | None:
    if len(returns) < 2:
        return None
    periodic_rf = risk_free_rate / periods_per_year
    excess = [value - periodic_rf for value in returns]
    volatility = pstdev(excess)
    if volatility == 0:
        return None
    return mean(excess) / volatility * math.sqrt(periods_per_year)


def win_rate(returns: list[float]) -> float:
    if not returns:
        return 0.0
    return sum(1 for value in returns if value > 0) / len(returns)


def calculate_metrics(
    returns: list[float],
    *,
    periods_per_year: int,
    turnovers: list[float] | None = None,
    trade_count: int = 0,
    benchmark_returns: list[float] | None = None,
) -> PerformanceMetrics:
    clean_returns = [value for value in returns if value is not None]
    clean_benchmark = [value for value in (benchmark_returns or []) if value is not None]
    cumulative = cumulative_return(clean_returns)
    benchmark_cumulative = cumulative_return(clean_benchmark) if clean_benchmark else None
    return PerformanceMetrics(
        cumulative_return=cumulative,
        annualized_return=annualized_return(clean_returns, periods_per_year),
        max_drawdown=max_drawdown(clean_returns),
        annualized_volatility=annualized_volatility(clean_returns, periods_per_year),
        sharpe_ratio=sharpe_ratio(clean_returns, periods_per_year),
        win_rate=win_rate(clean_returns),
        average_period_return=mean(clean_returns) if clean_returns else 0.0,
        best_period_return=max(clean_returns) if clean_returns else 0.0,
        worst_period_return=min(clean_returns) if clean_returns else 0.0,
        turnover_rate=mean(turnovers or []) if turnovers else 0.0,
        trade_count=trade_count,
        effective_periods=len(clean_returns),
        excess_cumulative_return=(cumulative - benchmark_cumulative) if benchmark_cumulative is not None else None,
    )
