from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from stock_selector.backtest.execution import ExecutionOutcome, execute_holding_return
from stock_selector.backtest.metrics import PerformanceMetrics, calculate_metrics, compound_returns
from stock_selector.data.models import DataFetchFailure, DailyBar, HistoricalSeries
from stock_selector.features.historical_factors import (
    HistoricalCandidate,
    HistoricalScoringResult,
    HistoricalStrategyConfig,
    default_historical_strategy,
    score_historical_universe,
)


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str
    end_date: str
    top_n: int = 10
    rebalance_frequency: str = "weekly"
    execution_timing: str = "next_open"
    transaction_cost_rate: float = 0.001
    slippage_rate: float = 0.0005
    adjustment: str = "qfq"
    data_source: str = "eastmoney"
    benchmark_code: str = "000300"
    benchmark_name: str = "沪深300"
    universe_size: int = 0
    universe_construction: str = ""
    universe_mode: str = "current_listed_broad"
    fixed_current_universe: bool = True
    survivorship_bias: str = "current-listed A-share universe; historical delisted stocks are not included"
    periods_per_year: int = 52
    max_exit_delay_days: int = 5
    market_constraint_model: str = "daily_open_limit_approx_v1"
    strategy: HistoricalStrategyConfig = field(default_factory=default_historical_strategy)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["strategy"] = self.strategy.as_dict()
        return data


@dataclass(frozen=True)
class HoldingReturn:
    code: str
    name: str
    rank: int
    score: float
    weight: float
    signal_date: str
    planned_entry_date: str
    planned_exit_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    gross_return: float
    score_parts: dict[str, float]
    raw_factor_values: dict[str, float]
    normalized_factor_scores: dict[str, float]
    factor_weights: dict[str, float]
    missing_factors: list[str]
    data_completeness: float
    entry_status: str
    exit_status: str
    execution_notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioExecution:
    gross_return: float
    net_return: float
    turnover: float
    trade_count: int
    held_count: int
    target_count: int
    cash_weight: float
    new_weights: dict[str, float]
    outcomes: dict[str, ExecutionOutcome]
    blocked_entries: list[str]
    blocked_exits: list[str]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outcomes"] = {code: outcome.as_dict() for code, outcome in self.outcomes.items()}
        return data


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
    universe_equal_weight_return: float | None
    single_factor_baseline_return: float | None
    turnover: float
    trade_count: int
    cash_weight: float
    missing_signal_bars: int
    blocked_entries: list[str]
    blocked_exits: list[str]
    candidates: list[dict[str, Any]]
    holdings: list[HoldingReturn]
    factor_audit: dict[str, Any]

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
    baseline_metrics: dict[str, PerformanceMetrics]
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
            "baseline_metrics": {key: value.as_dict() for key, value in self.baseline_metrics.items()},
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
    for trade_date in trading_dates:
        year, week, _ = __import__("datetime").date.fromisoformat(trade_date).isocalendar()
        week_key = (year, week)
        if current_week is not None and week_key != current_week and last_date:
            signals.append(last_date)
        current_week = week_key
        last_date = trade_date
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
    index_by_date = {trade_date: i for i, trade_date in enumerate(trading_dates)}
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


def price_return_between(series_map: dict[str, DailyBar], entry_date: str, exit_date: str, timing: str) -> float | None:
    outcome = execute_holding_return(
        code="benchmark",
        series_map=series_map,
        planned_entry_date=entry_date,
        planned_exit_date=exit_date,
        timing=timing,
        max_exit_delay_days=0,
    )
    return outcome.gross_return


def calculate_turnover(old_weights: dict[str, float], new_weights: dict[str, float]) -> tuple[float, int]:
    all_codes = set(old_weights) | set(new_weights)
    turnover = sum(abs(new_weights.get(code, 0.0) - old_weights.get(code, 0.0)) for code in all_codes)
    trade_count = sum(1 for code in all_codes if abs(new_weights.get(code, 0.0) - old_weights.get(code, 0.0)) > 1e-12)
    return turnover, trade_count


def _execute_weighted_codes(
    *,
    codes: list[str],
    target_weight: float,
    stock_maps: dict[str, dict[str, DailyBar]],
    previous_weights: dict[str, float],
    entry_date: str,
    exit_date: str,
    config: BacktestConfig,
) -> PortfolioExecution:
    outcomes: dict[str, ExecutionOutcome] = {}
    new_weights: dict[str, float] = {}
    blocked_entries: list[str] = []
    blocked_exits: list[str] = []
    gross_return = 0.0
    for code in codes:
        outcome = execute_holding_return(
            code=code,
            series_map=stock_maps.get(code, {}),
            planned_entry_date=entry_date,
            planned_exit_date=exit_date,
            timing=config.execution_timing,
            max_exit_delay_days=config.max_exit_delay_days,
        )
        outcomes[code] = outcome
        if outcome.is_executed:
            new_weights[code] = target_weight
            gross_return += target_weight * (outcome.gross_return or 0.0)
            continue
        if outcome.entry_status != "entry_filled":
            blocked_entries.append(code)
        elif outcome.exit_status != "exit_filled":
            blocked_exits.append(code)
    turnover, trade_count = calculate_turnover(previous_weights, new_weights)
    cost = turnover * (config.transaction_cost_rate + config.slippage_rate)
    cash_weight = max(0.0, 1.0 - sum(new_weights.values()))
    return PortfolioExecution(
        gross_return=gross_return,
        net_return=gross_return - cost,
        turnover=turnover,
        trade_count=trade_count,
        held_count=len(new_weights),
        target_count=len(codes),
        cash_weight=round(cash_weight, 8),
        new_weights=new_weights,
        outcomes=outcomes,
        blocked_entries=blocked_entries,
        blocked_exits=blocked_exits,
    )


def _holdings_from_execution(
    *,
    signal_date: str,
    candidates: list[HistoricalCandidate],
    execution: PortfolioExecution,
) -> list[HoldingReturn]:
    candidate_by_code = {item.code: item for item in candidates}
    holdings: list[HoldingReturn] = []
    for code, outcome in execution.outcomes.items():
        if not outcome.is_executed:
            continue
        candidate = candidate_by_code[code]
        holdings.append(
            HoldingReturn(
                code=code,
                name=candidate.name,
                rank=candidate.rank,
                score=candidate.score,
                weight=execution.new_weights[code],
                signal_date=signal_date,
                planned_entry_date=outcome.planned_entry_date,
                planned_exit_date=outcome.planned_exit_date,
                entry_date=outcome.entry_date or "",
                exit_date=outcome.exit_date or "",
                entry_price=outcome.entry_price or 0.0,
                exit_price=outcome.exit_price or 0.0,
                gross_return=outcome.gross_return or 0.0,
                score_parts=candidate.score_parts,
                raw_factor_values=candidate.raw_factor_values,
                normalized_factor_scores=candidate.normalized_factor_scores,
                factor_weights=candidate.factor_weights,
                missing_factors=candidate.missing_factors,
                data_completeness=candidate.data_completeness,
                entry_status=outcome.entry_status,
                exit_status=outcome.exit_status,
                execution_notes=outcome.notes,
            )
        )
    return holdings


def _single_factor_codes(scoring: HistoricalScoringResult, factor_name: str, top_n: int) -> list[str]:
    eligible = [
        snapshot for snapshot in scoring.snapshots
        if snapshot.is_eligible and factor_name in snapshot.raw_values
    ]
    eligible.sort(key=lambda item: (item.raw_values[factor_name], item.code), reverse=True)
    return [item.code for item in eligible[:top_n]]


def _eligible_universe_codes(scoring: HistoricalScoringResult) -> list[str]:
    return sorted(snapshot.code for snapshot in scoring.snapshots if snapshot.is_eligible)


def _coverage_summary(scoring_results: list[HistoricalScoringResult]) -> dict[str, Any]:
    if not scoring_results:
        return {}
    factor_names = scoring_results[0].factor_coverage.keys()
    return {
        factor_name: {
            "average_coverage": round(
                sum(item.factor_coverage.get(factor_name, 0.0) for item in scoring_results) / len(scoring_results),
                4,
            ),
            "min_coverage": min(item.factor_coverage.get(factor_name, 0.0) for item in scoring_results),
            "max_coverage": max(item.factor_coverage.get(factor_name, 0.0) for item in scoring_results),
        }
        for factor_name in factor_names
    }


def period_conclusion(
    strategy_metrics: PerformanceMetrics,
    benchmark_metrics: PerformanceMetrics,
    baseline_metrics: dict[str, PerformanceMetrics],
) -> str:
    if strategy_metrics.effective_periods == 0:
        return "没有形成有效持仓期，无法判断当前历史策略。"
    equal_weight = baseline_metrics.get("universe_equal_weight")
    single_factor = baseline_metrics.get("single_factor_trend_20d")
    comparisons = []
    comparisons.append(strategy_metrics.cumulative_return - benchmark_metrics.cumulative_return)
    if equal_weight:
        comparisons.append(strategy_metrics.cumulative_return - equal_weight.cumulative_return)
    if single_factor:
        comparisons.append(strategy_metrics.cumulative_return - single_factor.cumulative_return)
    if comparisons and all(value > 0 for value in comparisons):
        return "本次有限样本中，历史 OHLCV 固定因子策略高于基准和已实现的简单基线；这只是可继续研究的线索，不足以证明策略有效。"
    return "本次有限样本未能同时优于基准和简单基线；当前结果主要证明可信回测链路可运行，不证明策略有效。"


def run_cross_sectional_backtest(
    *,
    series_by_code: dict[str, HistoricalSeries],
    benchmark: HistoricalSeries,
    config: BacktestConfig,
    data_failures: list[DataFetchFailure] | None = None,
) -> BacktestResult:
    if config.execution_timing not in {"next_open", "next_close"}:
        raise ValueError(f"unsupported execution timing: {config.execution_timing}")

    benchmark_map = bars_by_date(benchmark)
    trading_dates = [bar.date for bar in benchmark.bars if config.start_date <= bar.date <= config.end_date]
    windows = build_rebalance_windows(trading_dates, config.rebalance_frequency)
    stock_maps = {code: bars_by_date(series) for code, series in series_by_code.items()}

    previous_weights: dict[str, float] = {}
    previous_equal_weights: dict[str, float] = {}
    previous_single_factor_weights: dict[str, float] = {}
    periods: list[BacktestPeriod] = []
    scoring_results: list[HistoricalScoringResult] = []
    equal_weight_returns: list[float] = []
    single_factor_returns: list[float] = []

    for signal_date, entry_date, exit_date in windows:
        scoring = score_historical_universe(
            series_by_code,
            signal_date,
            strategy=config.strategy,
            top_n=config.top_n,
        )
        scoring_results.append(scoring)
        selected = scoring.candidates
        selected_codes = [item.code for item in selected]
        target_weight = 1.0 / len(selected_codes) if selected_codes else 0.0
        execution = _execute_weighted_codes(
            codes=selected_codes,
            target_weight=target_weight,
            stock_maps=stock_maps,
            previous_weights=previous_weights,
            entry_date=entry_date,
            exit_date=exit_date,
            config=config,
        )
        previous_weights = execution.new_weights

        eligible_codes = _eligible_universe_codes(scoring)
        equal_target_weight = 1.0 / len(eligible_codes) if eligible_codes else 0.0
        equal_execution = _execute_weighted_codes(
            codes=eligible_codes,
            target_weight=equal_target_weight,
            stock_maps=stock_maps,
            previous_weights=previous_equal_weights,
            entry_date=entry_date,
            exit_date=exit_date,
            config=config,
        )
        previous_equal_weights = equal_execution.new_weights
        equal_weight_returns.append(equal_execution.net_return)

        single_codes = _single_factor_codes(scoring, "trend_20d_return", config.top_n)
        single_target_weight = 1.0 / len(single_codes) if single_codes else 0.0
        single_execution = _execute_weighted_codes(
            codes=single_codes,
            target_weight=single_target_weight,
            stock_maps=stock_maps,
            previous_weights=previous_single_factor_weights,
            entry_date=entry_date,
            exit_date=exit_date,
            config=config,
        )
        previous_single_factor_weights = single_execution.new_weights
        single_factor_returns.append(single_execution.net_return)

        benchmark_return = price_return_between(benchmark_map, entry_date, exit_date, config.execution_timing)
        periods.append(
            BacktestPeriod(
                signal_date=signal_date,
                entry_date=entry_date,
                exit_date=exit_date,
                selected_count=len(selected),
                held_count=execution.held_count,
                gross_return=execution.gross_return,
                cost_impact=execution.turnover * (config.transaction_cost_rate + config.slippage_rate),
                net_return=execution.net_return,
                benchmark_return=benchmark_return,
                universe_equal_weight_return=equal_execution.net_return,
                single_factor_baseline_return=single_execution.net_return,
                turnover=execution.turnover,
                trade_count=execution.trade_count,
                cash_weight=execution.cash_weight,
                missing_signal_bars=scoring.missing_signal_bars,
                blocked_entries=execution.blocked_entries,
                blocked_exits=execution.blocked_exits,
                candidates=[item.as_dict() for item in selected],
                holdings=_holdings_from_execution(
                    signal_date=signal_date,
                    candidates=selected,
                    execution=execution,
                ),
                factor_audit={
                    "with_signal_bar": scoring.with_signal_bar,
                    "eligible_count": scoring.eligible_count,
                    "excluded_count": scoring.excluded_count,
                    "factor_coverage": scoring.factor_coverage,
                    "missing_factor_counts": scoring.missing_factor_counts,
                },
            )
        )

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
    baseline_metrics = {
        "universe_equal_weight": calculate_metrics(
            equal_weight_returns,
            periods_per_year=config.periods_per_year,
            turnovers=[],
            trade_count=0,
            benchmark_returns=benchmark_returns,
        ),
        "single_factor_trend_20d": calculate_metrics(
            single_factor_returns,
            periods_per_year=config.periods_per_year,
            turnovers=[],
            trade_count=0,
            benchmark_returns=benchmark_returns,
        ),
    }

    strategy_curve = compound_returns(strategy_returns)
    benchmark_curve = compound_returns(benchmark_returns)
    equal_curve = compound_returns(equal_weight_returns)
    single_curve = compound_returns(single_factor_returns)
    equity_curve = []
    for index, period in enumerate(periods):
        equity_curve.append(
            {
                "date": period.exit_date,
                "strategy_cumulative_return": strategy_curve[index] if index < len(strategy_curve) else None,
                "benchmark_cumulative_return": benchmark_curve[index] if index < len(benchmark_curve) else None,
                "universe_equal_weight_cumulative_return": equal_curve[index] if index < len(equal_curve) else None,
                "single_factor_trend_20d_cumulative_return": single_curve[index] if index < len(single_curve) else None,
                "strategy_period_return": period.net_return,
                "benchmark_period_return": period.benchmark_return,
                "universe_equal_weight_period_return": period.universe_equal_weight_return,
                "single_factor_trend_20d_period_return": period.single_factor_baseline_return,
            }
        )

    data_failures = data_failures or []
    benchmark_failure_count = sum(
        1
        for failure in data_failures
        if failure.code == config.benchmark_code and failure.name == config.benchmark_name
    )
    stock_failure_count = len(data_failures) - benchmark_failure_count
    cache_hits = sum(1 for series in series_by_code.values() if series.cache_hit)
    blocked_entry_count = sum(len(period.blocked_entries) for period in periods)
    blocked_exit_count = sum(len(period.blocked_exits) for period in periods)
    warnings = [
        "历史验证策略与实时快照扫描策略已分离；本报告验证 historical_ohlcv_v1，不验证实时主力资金/估值扫描模型。",
        "股票池为当前仍可获取代码池的过渡方案，历史退市股票和历史成分变化未完整纳入，仍存在幸存者偏差。",
        "历史信号只读取信号日及以前日线；窗口不足、信号日缺失或因子缺失的股票不会被伪造成正常样本。",
        "涨跌停、停牌和无量成交只基于日线开盘价与成交量近似判断，不等同于逐笔盘口可成交性。",
        "当前结果用于研究链路验证，不构成投资建议、收益承诺或交易信号。",
    ]
    if config.universe_mode == "csv_debug":
        warnings.insert(
            1,
            "本次使用显式 CSV 股票池调试模式；它不是默认策略验证路径，不能作为历史选股能力证据。",
        )
    data_audit = {
        "requested_universe_size": config.universe_size,
        "loaded_series": len(series_by_code),
        "failed_series": stock_failure_count,
        "failed_benchmark_requests": benchmark_failure_count,
        "failed_data_requests": len(data_failures),
        "cache_hits": cache_hits,
        "cache_misses": len(series_by_code) - cache_hits,
        "benchmark_rows": len(benchmark.bars),
        "rebalance_windows": len(windows),
        "effective_periods": len(strategy_returns),
        "benchmark_source": benchmark.source,
        "benchmark_adjustment": benchmark.adjustment,
        "universe_mode": config.universe_mode,
        "fixed_current_universe": config.fixed_current_universe,
        "survivorship_bias": config.survivorship_bias,
        "point_in_time_controls": {
            "signal_cutoff": "signal day close",
            "factor_windows": "bars are truncated at signal_date before factor calculation",
            "future_data_isolation": "covered by automated tests that mutate future bars after the signal date",
            "missing_data_policy": "missing signal bars or required factor windows exclude that stock for the period",
        },
        "strategy_identity": config.strategy.as_dict(),
        "factor_coverage_summary": _coverage_summary(scoring_results),
        "execution_model": {
            "timing": config.execution_timing,
            "planned_entry": "next benchmark trading day after signal",
            "planned_exit": "next benchmark trading day after next signal",
            "constraint_model": config.market_constraint_model,
            "max_exit_delay_days": config.max_exit_delay_days,
            "transaction_cost_rate": config.transaction_cost_rate,
            "slippage_rate": config.slippage_rate,
        },
        "execution_quality": {
            "blocked_entry_count": blocked_entry_count,
            "blocked_exit_count": blocked_exit_count,
            "average_cash_weight": (
                round(sum(period.cash_weight for period in periods) / len(periods), 6)
                if periods
                else 0.0
            ),
        },
        "baselines": {
            "benchmark": config.benchmark_name,
            "universe_equal_weight": "eligible universe equal weight with same daily-bar execution approximation",
            "single_factor_trend_20d": "top N by trend_20d_return only",
        },
        "can_prove": [
            "程序可以在固定历史策略身份下完成 point-in-time 因子、排名、执行和审计输出。",
            "在当前数据范围内，未来 K 线不会参与信号日因子计算。",
        ],
        "cannot_prove": [
            "不能证明策略长期有效或可实盘盈利。",
            "不能消除当前仍上市代码池带来的幸存者偏差。",
            "不能证明日线涨跌停近似等同真实盘口可成交性。",
        ],
    }
    return BacktestResult(
        config=config,
        periods=periods,
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        baseline_metrics=baseline_metrics,
        equity_curve=equity_curve,
        data_failures=data_failures,
        data_audit=data_audit,
        warnings=warnings,
        conclusion=period_conclusion(strategy_metrics, benchmark_metrics, baseline_metrics),
    )
