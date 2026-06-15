from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from stock_selector.backtest.metrics import PerformanceMetrics, calculate_metrics, compound_returns
from stock_selector.data.models import DataFetchFailure, DailyBar, HistoricalSeries
from stock_selector.screening.momentum_liquidity import ScreenConfig, ScreenedStock, screen_quotes


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str
    end_date: str
    top_n: int = 10
    rebalance_frequency: str = "weekly"
    execution_timing: str = "next_close"
    transaction_cost_rate: float = 0.001
    slippage_rate: float = 0.0005
    adjustment: str = "qfq"
    data_source: str = "eastmoney"
    benchmark_code: str = "000300"
    benchmark_name: str = "沪深300"
    universe_size: int = 0
    universe_construction: str = ""
    periods_per_year: int = 52
    allow_missing_turnover_rate: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HoldingReturn:
    code: str
    name: str
    rank: int
    score: float
    weight: float
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    gross_return: float
    score_parts: dict[str, float]
    effective_weights: dict[str, float]
    missing_factors: list[str]
    data_completeness: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestPeriod:
    signal_date: str
    entry_date: str
    exit_date: str
    selected_count: int
    held_count: int
    gross_return: float | None
    cost_impact: float
    net_return: float | None
    benchmark_return: float | None
    turnover: float
    trade_count: int
    missing_signal_bars: int
    missing_execution_bars: list[str]
    candidates: list[dict[str, Any]]
    holdings: list[HoldingReturn]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["holdings"] = [holding.as_dict() for holding in self.holdings]
        return data


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    periods: list[BacktestPeriod]
    strategy_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    equity_curve: list[dict[str, Any]]
    data_failures: list[DataFetchFailure]
    data_audit: dict[str, Any]
    warnings: list[str]
    conclusion: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.as_dict(),
            "periods": [period.as_dict() for period in self.periods],
            "strategy_metrics": self.strategy_metrics.as_dict(),
            "benchmark_metrics": self.benchmark_metrics.as_dict(),
            "equity_curve": self.equity_curve,
            "data_failures": [failure.as_dict() for failure in self.data_failures],
            "data_audit": self.data_audit,
            "warnings": self.warnings,
            "conclusion": self.conclusion,
        }


def bars_by_date(series: HistoricalSeries) -> dict[str, DailyBar]:
    return {bar.date: bar for bar in series.bars}


def weekly_signal_dates(trading_dates: list[str]) -> list[str]:
    signals: list[str] = []
    current_week: tuple[int, int] | None = None
    last_date = ""
    for date in trading_dates:
        year, week, _ = __import__("datetime").date.fromisoformat(date).isocalendar()
        week_key = (year, week)
        if current_week is not None and week_key != current_week and last_date:
            signals.append(last_date)
        current_week = week_key
        last_date = date
    if last_date:
        signals.append(last_date)
    return signals


def signal_dates_for_frequency(trading_dates: list[str], frequency: str) -> list[str]:
    if frequency == "daily":
        return trading_dates
    if frequency == "weekly":
        return weekly_signal_dates(trading_dates)
    raise ValueError(f"unsupported rebalance frequency: {frequency}")


def build_rebalance_windows(trading_dates: list[str], frequency: str) -> list[tuple[str, str, str]]:
    index_by_date = {date: i for i, date in enumerate(trading_dates)}
    signal_dates = signal_dates_for_frequency(trading_dates, frequency)
    windows: list[tuple[str, str, str]] = []
    for signal_date, next_signal_date in zip(signal_dates, signal_dates[1:]):
        signal_index = index_by_date[signal_date]
        next_signal_index = index_by_date[next_signal_date]
        entry_index = signal_index + 1
        exit_index = next_signal_index + 1
        if entry_index >= len(trading_dates) or exit_index >= len(trading_dates):
            continue
        windows.append((signal_date, trading_dates[entry_index], trading_dates[exit_index]))
    return windows


def return_between(series_map: dict[str, DailyBar], entry_date: str, exit_date: str) -> tuple[float, float, float] | None:
    entry = series_map.get(entry_date)
    exit_ = series_map.get(exit_date)
    if entry is None or exit_ is None:
        return None
    if entry.close <= 0 or exit_.close <= 0:
        return None
    return entry.close, exit_.close, exit_.close / entry.close - 1.0


def calculate_turnover(old_weights: dict[str, float], new_weights: dict[str, float]) -> tuple[float, int]:
    all_codes = set(old_weights) | set(new_weights)
    turnover = sum(abs(new_weights.get(code, 0.0) - old_weights.get(code, 0.0)) for code in all_codes)
    trade_count = sum(1 for code in all_codes if abs(new_weights.get(code, 0.0) - old_weights.get(code, 0.0)) > 1e-12)
    return turnover, trade_count


def period_conclusion(strategy_metrics: PerformanceMetrics, benchmark_metrics: PerformanceMetrics) -> str:
    excess = strategy_metrics.cumulative_return - benchmark_metrics.cumulative_return
    if strategy_metrics.effective_periods == 0:
        return "没有形成有效持仓期，无法判断当前规则的历史价值。"
    if excess > 0 and strategy_metrics.max_drawdown <= benchmark_metrics.max_drawdown * 1.2:
        return "本次有限样本回测中策略累计收益高于基准，且回撤未明显劣于基准；只能视为初步正向线索。"
    if excess > 0:
        return "本次有限样本回测中策略累计收益高于基准，但回撤风险需要继续检查。"
    return "本次有限样本回测中策略未跑赢基准，当前规则尚不能证明具备初步历史价值。"


def run_cross_sectional_backtest(
    *,
    series_by_code: dict[str, HistoricalSeries],
    benchmark: HistoricalSeries,
    config: BacktestConfig,
    data_failures: list[DataFetchFailure] | None = None,
) -> BacktestResult:
    benchmark_map = bars_by_date(benchmark)
    trading_dates = [bar.date for bar in benchmark.bars if config.start_date <= bar.date <= config.end_date]
    windows = build_rebalance_windows(trading_dates, config.rebalance_frequency)
    if config.execution_timing != "next_close":
        raise ValueError("only next_close execution is supported")

    stock_maps = {code: bars_by_date(series) for code, series in series_by_code.items()}
    screen_config = ScreenConfig(
        top_n=config.top_n,
        allow_missing_turnover_rate=config.allow_missing_turnover_rate,
    )
    previous_weights: dict[str, float] = {}
    periods: list[BacktestPeriod] = []

    for signal_date, entry_date, exit_date in windows:
        signal_quotes = []
        missing_signal = 0
        for code, series_map in stock_maps.items():
            bar = series_map.get(signal_date)
            if bar is None:
                missing_signal += 1
                continue
            signal_quotes.append(bar.to_quote())

        screen_result = screen_quotes(signal_quotes, screen_config)
        selected: list[ScreenedStock] = screen_result.candidates
        missing_execution: list[str] = []
        raw_holding_returns: list[tuple[ScreenedStock, float, float, float]] = []
        for item in selected:
            result = return_between(stock_maps.get(item.quote.code, {}), entry_date, exit_date)
            if result is None:
                missing_execution.append(item.quote.code)
                continue
            entry_price, exit_price, gross_return = result
            raw_holding_returns.append((item, entry_price, exit_price, gross_return))

        held_count = len(raw_holding_returns)
        new_weights = {
            item.quote.code: 1.0 / held_count
            for item, _, _, _ in raw_holding_returns
        } if held_count else {}
        turnover, trade_count = calculate_turnover(previous_weights, new_weights)
        period_cost = turnover * (config.transaction_cost_rate + config.slippage_rate)

        holdings: list[HoldingReturn] = []
        weighted_returns: list[float] = []
        for item, entry_price, exit_price, gross_return in raw_holding_returns:
            weight = new_weights[item.quote.code]
            weighted_returns.append(weight * gross_return)
            holdings.append(
                HoldingReturn(
                    code=item.quote.code,
                    name=item.quote.name,
                    rank=item.rank,
                    score=item.score,
                    weight=weight,
                    signal_date=signal_date,
                    entry_date=entry_date,
                    exit_date=exit_date,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_return=gross_return,
                    score_parts=item.score_parts,
                    effective_weights=item.effective_weights,
                    missing_factors=item.missing_factors,
                    data_completeness=item.data_completeness,
                )
            )

        gross_return = sum(weighted_returns) if weighted_returns else 0.0
        net_return = gross_return - period_cost
        benchmark_result = return_between(benchmark_map, entry_date, exit_date)
        benchmark_return = benchmark_result[2] if benchmark_result else None
        periods.append(
            BacktestPeriod(
                signal_date=signal_date,
                entry_date=entry_date,
                exit_date=exit_date,
                selected_count=len(selected),
                held_count=held_count,
                gross_return=gross_return,
                cost_impact=period_cost,
                net_return=net_return,
                benchmark_return=benchmark_return,
                turnover=turnover,
                trade_count=trade_count,
                missing_signal_bars=missing_signal,
                missing_execution_bars=missing_execution,
                candidates=[item.as_dict() for item in selected],
                holdings=holdings,
            )
        )
        previous_weights = new_weights

    strategy_returns = [period.net_return for period in periods if period.net_return is not None]
    benchmark_returns = [period.benchmark_return for period in periods if period.benchmark_return is not None]
    turnovers = [period.turnover for period in periods]
    trade_count = sum(period.trade_count for period in periods)
    strategy_metrics = calculate_metrics(
        strategy_returns,
        periods_per_year=config.periods_per_year,
        turnovers=turnovers,
        trade_count=trade_count,
        benchmark_returns=benchmark_returns,
    )
    benchmark_metrics = calculate_metrics(
        benchmark_returns,
        periods_per_year=config.periods_per_year,
        turnovers=[0.0 for _ in benchmark_returns],
        trade_count=0,
    )

    strategy_curve = compound_returns(strategy_returns)
    benchmark_curve = compound_returns(benchmark_returns)
    equity_curve = []
    for index, period in enumerate(periods):
        equity_curve.append(
            {
                "date": period.exit_date,
                "strategy_cumulative_return": strategy_curve[index] if index < len(strategy_curve) else None,
                "benchmark_cumulative_return": benchmark_curve[index] if index < len(benchmark_curve) else None,
                "strategy_period_return": period.net_return,
                "benchmark_period_return": period.benchmark_return,
            }
        )

    data_failures = data_failures or []
    cache_hits = sum(1 for series in series_by_code.values() if series.cache_hit)
    missing_factor_samples = []
    for period in periods:
        for holding in period.holdings:
            missing_factor_samples.extend(holding.missing_factors)
    warnings = [
        "股票池来自当前可获取股票列表，历史上已退市或当时不可交易股票未完整纳入，存在幸存者偏差。",
        "历史日线不包含逐笔成交、真实涨跌停可成交性和停牌细节；缺失执行价的持仓已记录并跳过。",
        "信号使用信号日收盘后的日线字段，默认下一交易日收盘成交，避免同日收盘信号同日成交。",
        "东财日线缺少主力资金与估值字段，评分使用动态可用因子权重，跨数据源总分不可直接比较。",
    ]
    data_audit = {
        "requested_universe_size": config.universe_size,
        "loaded_series": len(series_by_code),
        "failed_series": len(data_failures),
        "cache_hits": cache_hits,
        "cache_misses": len(series_by_code) - cache_hits,
        "benchmark_rows": len(benchmark.bars),
        "rebalance_windows": len(windows),
        "effective_periods": len(strategy_returns),
        "missing_factor_occurrences_in_holdings": dict(sorted({name: missing_factor_samples.count(name) for name in set(missing_factor_samples)}.items())),
        "benchmark_source": benchmark.source,
        "benchmark_adjustment": benchmark.adjustment,
    }
    return BacktestResult(
        config=config,
        periods=periods,
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        equity_curve=equity_curve,
        data_failures=data_failures,
        data_audit=data_audit,
        warnings=warnings,
        conclusion=period_conclusion(strategy_metrics, benchmark_metrics),
    )
