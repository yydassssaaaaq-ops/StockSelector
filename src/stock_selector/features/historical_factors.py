from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import median, pstdev
from typing import Any

from stock_selector.data.models import HistoricalSeries


@dataclass(frozen=True)
class FactorSpec:
    name: str
    weight: float
    description: str
    required_fields: tuple[str, ...]
    available_at: str
    window: int
    direction: str
    missing_policy: str
    standardization: str
    data_risk: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_fields"] = list(self.required_fields)
        return data


@dataclass(frozen=True)
class HistoricalStrategyConfig:
    strategy_id: str = "historical_ohlcv_v1"
    display_name: str = "历史 OHLCV 趋势质量策略 V1"
    description: str = (
        "只使用信号日收盘时可见的前复权日线 OHLCV 派生因子，"
        "用固定因子集合和横截面百分位评分形成候选。"
    )
    factor_specs: tuple[FactorSpec, ...] = field(default_factory=tuple)
    min_history_bars: int = 61
    min_amount_valid_ratio: float = 0.8

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "description": self.description,
            "factor_specs": [item.as_dict() for item in self.factor_specs],
            "min_history_bars": self.min_history_bars,
            "min_amount_valid_ratio": self.min_amount_valid_ratio,
        }


@dataclass(frozen=True)
class FactorSnapshot:
    code: str
    name: str
    signal_date: str
    latest_bar_date: str | None
    available_bar_count: int
    required_bar_count: int
    raw_values: dict[str, float]
    missing_factors: list[str]
    missing_reasons: dict[str, str]
    amount_valid_ratio_20d: float | None

    @property
    def has_signal_bar(self) -> bool:
        return self.latest_bar_date == self.signal_date

    @property
    def is_eligible(self) -> bool:
        return self.has_signal_bar and not self.missing_factors

    @property
    def data_completeness(self) -> float:
        factor_count = len(self.raw_values) + len(self.missing_factors)
        factor_ratio = len(self.raw_values) / factor_count if factor_count else 0.0
        bar_ratio = min(1.0, self.available_bar_count / self.required_bar_count) if self.required_bar_count else 1.0
        return round(min(factor_ratio, bar_ratio), 4)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["has_signal_bar"] = self.has_signal_bar
        data["is_eligible"] = self.is_eligible
        data["data_completeness"] = self.data_completeness
        return data


@dataclass(frozen=True)
class HistoricalCandidate:
    rank: int
    code: str
    name: str
    score: float
    raw_factor_values: dict[str, float]
    normalized_factor_scores: dict[str, float]
    score_parts: dict[str, float]
    factor_weights: dict[str, float]
    missing_factors: list[str]
    data_completeness: float
    available_bar_count: int
    decision_notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HistoricalScoringResult:
    strategy: HistoricalStrategyConfig
    signal_date: str
    total_series: int
    with_signal_bar: int
    eligible_count: int
    excluded_count: int
    missing_signal_bars: int
    missing_factor_counts: dict[str, int]
    factor_coverage: dict[str, float]
    snapshots: list[FactorSnapshot]
    candidates: list[HistoricalCandidate]

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.as_dict(),
            "signal_date": self.signal_date,
            "total_series": self.total_series,
            "with_signal_bar": self.with_signal_bar,
            "eligible_count": self.eligible_count,
            "excluded_count": self.excluded_count,
            "missing_signal_bars": self.missing_signal_bars,
            "missing_factor_counts": self.missing_factor_counts,
            "factor_coverage": self.factor_coverage,
            "snapshots": [item.as_dict() for item in self.snapshots],
            "candidates": [item.as_dict() for item in self.candidates],
        }


def default_historical_strategy() -> HistoricalStrategyConfig:
    return HistoricalStrategyConfig(
        factor_specs=(
            FactorSpec(
                name="trend_20d_return",
                weight=0.25,
                description="衡量约一个月的中短期价格趋势。",
                required_fields=("date", "close"),
                available_at="信号日收盘后",
                window=20,
                direction="higher_better",
                missing_policy="窗口不足或价格缺失时剔除该股票的本期历史评分。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="前复权口径会随复权因子更新，需保留数据源和复权方式。",
            ),
            FactorSpec(
                name="trend_60d_return",
                weight=0.20,
                description="衡量约一个季度的趋势持续性，降低单日涨跌幅主导程度。",
                required_fields=("date", "close"),
                available_at="信号日收盘后",
                window=60,
                direction="higher_better",
                missing_policy="上市时间或窗口不足时剔除该股票的本期历史评分。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="长窗口减少噪声但会降低早期样本覆盖率。",
            ),
            FactorSpec(
                name="price_vs_ma20",
                weight=0.15,
                description="衡量当前价格相对 20 日均线的位置。",
                required_fields=("date", "close"),
                available_at="信号日收盘后",
                window=20,
                direction="higher_better",
                missing_policy="窗口不足时剔除。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="强趋势票可能同时伴随高波动，需与风险因子共同解释。",
            ),
            FactorSpec(
                name="liquidity_20d_median_amount",
                weight=0.20,
                description="衡量过去 20 个交易日的成交活跃程度。",
                required_fields=("date", "amount", "volume", "close"),
                available_at="信号日收盘后",
                window=20,
                direction="higher_better",
                missing_policy="20 日内有效成交额样本不足 80% 时剔除。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="腾讯源成交额由成交手数乘收盘价派生，报告中必须披露。",
            ),
            FactorSpec(
                name="volatility_20d",
                weight=0.10,
                description="衡量过去 20 日收益波动，偏好较低波动。",
                required_fields=("date", "close"),
                available_at="信号日收盘后",
                window=20,
                direction="lower_better",
                missing_policy="窗口不足时剔除。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="日线波动无法反映盘中流动性冲击。",
            ),
            FactorSpec(
                name="max_drawdown_20d",
                weight=0.10,
                description="衡量过去 20 日局部回撤风险，偏好较小回撤。",
                required_fields=("date", "close"),
                available_at="信号日收盘后",
                window=20,
                direction="lower_better",
                missing_policy="窗口不足时剔除。",
                standardization="同一信号日横截面百分位排名。",
                data_risk="只能描述窗口内历史风险，不代表未来回撤上限。",
            ),
        ),
        min_history_bars=61,
        min_amount_valid_ratio=0.8,
    )


def _daily_returns(closes: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0 or current <= 0:
            continue
        returns.append(current / previous - 1.0)
    return returns


def _max_drawdown(closes: list[float]) -> float | None:
    if not closes:
        return None
    peak = closes[0]
    worst = 0.0
    for close in closes:
        if close <= 0:
            return None
        peak = max(peak, close)
        worst = min(worst, close / peak - 1.0)
    return abs(worst)


def _factor_value(
    name: str,
    *,
    closes: list[float],
    amounts: list[float],
    amount_valid_ratio: float,
    strategy: HistoricalStrategyConfig,
) -> tuple[float | None, str | None]:
    if name == "trend_20d_return":
        if len(closes) < 21:
            return None, "insufficient_20d_window"
        return closes[-1] / closes[-21] - 1.0, None
    if name == "trend_60d_return":
        if len(closes) < 61:
            return None, "insufficient_60d_window"
        return closes[-1] / closes[-61] - 1.0, None
    if name == "price_vs_ma20":
        if len(closes) < 20:
            return None, "insufficient_20d_window"
        average = sum(closes[-20:]) / 20
        if average <= 0:
            return None, "non_positive_ma20"
        return closes[-1] / average - 1.0, None
    if name == "liquidity_20d_median_amount":
        if len(amounts) < 20:
            return None, "insufficient_20d_amount_window"
        valid_amounts = [value for value in amounts[-20:] if value > 0]
        if len(valid_amounts) / 20 < strategy.min_amount_valid_ratio:
            return None, "insufficient_valid_amount_rows"
        return float(median(valid_amounts)), None
    if name == "volatility_20d":
        if len(closes) < 21:
            return None, "insufficient_20d_return_window"
        returns = _daily_returns(closes[-21:])
        if len(returns) < 20:
            return None, "missing_return_observation"
        return pstdev(returns), None
    if name == "max_drawdown_20d":
        if len(closes) < 20:
            return None, "insufficient_20d_window"
        value = _max_drawdown(closes[-20:])
        return value, None if value is not None else "invalid_drawdown_window"
    return None, f"unsupported_factor:{name}"


def factor_snapshot_for_series(
    series: HistoricalSeries,
    signal_date: str,
    strategy: HistoricalStrategyConfig | None = None,
) -> FactorSnapshot:
    strategy = strategy or default_historical_strategy()
    bars = [bar for bar in series.bars if bar.date <= signal_date]
    latest_bar_date = bars[-1].date if bars else None
    required_bars = max([strategy.min_history_bars, *[spec.window + 1 for spec in strategy.factor_specs]])
    raw_values: dict[str, float] = {}
    missing_factors: list[str] = []
    missing_reasons: dict[str, str] = {}
    closes = [bar.close for bar in bars]
    amounts = [bar.amount for bar in bars]
    amount_window = amounts[-20:] if len(amounts) >= 20 else amounts
    amount_valid_ratio = (
        round(sum(1 for value in amount_window if value > 0) / len(amount_window), 4)
        if amount_window
        else None
    )

    if latest_bar_date != signal_date:
        for spec in strategy.factor_specs:
            missing_factors.append(spec.name)
            missing_reasons[spec.name] = "missing_signal_day_bar"
    else:
        for spec in strategy.factor_specs:
            value, reason = _factor_value(
                spec.name,
                closes=closes,
                amounts=amounts,
                amount_valid_ratio=amount_valid_ratio or 0.0,
                strategy=strategy,
            )
            if value is None:
                missing_factors.append(spec.name)
                missing_reasons[spec.name] = reason or "missing_factor_value"
            else:
                raw_values[spec.name] = value

    return FactorSnapshot(
        code=series.code,
        name=series.name,
        signal_date=signal_date,
        latest_bar_date=latest_bar_date,
        available_bar_count=len(bars),
        required_bar_count=required_bars,
        raw_values=raw_values,
        missing_factors=missing_factors,
        missing_reasons=missing_reasons,
        amount_valid_ratio_20d=amount_valid_ratio,
    )


def _percentile_scores(values: dict[str, float], *, higher_better: bool) -> dict[str, float]:
    if not values:
        return {}
    if len(values) == 1:
        return {next(iter(values)): 1.0}
    sorted_items = sorted(values.items(), key=lambda item: (item[1], item[0]))
    denominator = len(sorted_items) - 1
    scores: dict[str, float] = {}
    index = 0
    while index < len(sorted_items):
        next_index = index + 1
        while next_index < len(sorted_items) and sorted_items[next_index][1] == sorted_items[index][1]:
            next_index += 1
        average_rank = (index + next_index - 1) / 2
        percentile = average_rank / denominator
        score = percentile if higher_better else 1.0 - percentile
        for item_index in range(index, next_index):
            scores[sorted_items[item_index][0]] = score
        index = next_index
    return scores


def score_historical_universe(
    series_by_code: dict[str, HistoricalSeries],
    signal_date: str,
    *,
    strategy: HistoricalStrategyConfig | None = None,
    top_n: int | None = None,
) -> HistoricalScoringResult:
    strategy = strategy or default_historical_strategy()
    snapshots = [
        factor_snapshot_for_series(series, signal_date, strategy)
        for series in series_by_code.values()
    ]
    eligible = [snapshot for snapshot in snapshots if snapshot.is_eligible]
    missing_factor_counts: dict[str, int] = {}
    for snapshot in snapshots:
        for factor_name in snapshot.missing_factors:
            missing_factor_counts[factor_name] = missing_factor_counts.get(factor_name, 0) + 1

    normalized_by_factor: dict[str, dict[str, float]] = {}
    for spec in strategy.factor_specs:
        values = {
            snapshot.code: snapshot.raw_values[spec.name]
            for snapshot in eligible
            if spec.name in snapshot.raw_values
        }
        normalized_by_factor[spec.name] = _percentile_scores(
            values,
            higher_better=spec.direction == "higher_better",
        )

    candidates: list[HistoricalCandidate] = []
    spec_by_name = {spec.name: spec for spec in strategy.factor_specs}
    for snapshot in eligible:
        score_parts: dict[str, float] = {}
        normalized: dict[str, float] = {}
        factor_weights: dict[str, float] = {}
        for spec in strategy.factor_specs:
            factor_score = normalized_by_factor.get(spec.name, {}).get(snapshot.code)
            if factor_score is None:
                continue
            normalized[spec.name] = round(factor_score, 6)
            factor_weights[spec.name] = spec.weight
            score_parts[spec.name] = round(factor_score * spec.weight * 100.0, 3)
        score = round(sum(score_parts.values()), 3)
        notes = [
            f"strategy_id={strategy.strategy_id}",
            f"latest_bar_date={snapshot.latest_bar_date}",
            f"available_bars={snapshot.available_bar_count}",
            "weights_are_fixed=true",
            "standardization=cross_sectional_percentile",
        ]
        candidates.append(
            HistoricalCandidate(
                rank=0,
                code=snapshot.code,
                name=snapshot.name,
                score=score,
                raw_factor_values={key: round(value, 8) for key, value in snapshot.raw_values.items()},
                normalized_factor_scores=normalized,
                score_parts=score_parts,
                factor_weights=factor_weights,
                missing_factors=[],
                data_completeness=snapshot.data_completeness,
                available_bar_count=snapshot.available_bar_count,
                decision_notes=notes,
            )
        )
    candidates.sort(
        key=lambda item: (
            item.score,
            item.normalized_factor_scores.get("trend_20d_return", 0.0),
            item.normalized_factor_scores.get("liquidity_20d_median_amount", 0.0),
            item.code,
        ),
        reverse=True,
    )
    ranked = [
        HistoricalCandidate(
            rank=index + 1,
            code=item.code,
            name=item.name,
            score=item.score,
            raw_factor_values=item.raw_factor_values,
            normalized_factor_scores=item.normalized_factor_scores,
            score_parts=item.score_parts,
            factor_weights={key: spec_by_name[key].weight for key in item.score_parts},
            missing_factors=item.missing_factors,
            data_completeness=item.data_completeness,
            available_bar_count=item.available_bar_count,
            decision_notes=item.decision_notes,
        )
        for index, item in enumerate(candidates[:top_n] if top_n else candidates)
    ]
    with_signal_bar = sum(1 for snapshot in snapshots if snapshot.has_signal_bar)
    factor_coverage = {
        spec.name: (
            round(sum(1 for snapshot in snapshots if spec.name in snapshot.raw_values) / with_signal_bar, 4)
            if with_signal_bar
            else 0.0
        )
        for spec in strategy.factor_specs
    }
    return HistoricalScoringResult(
        strategy=strategy,
        signal_date=signal_date,
        total_series=len(series_by_code),
        with_signal_bar=with_signal_bar,
        eligible_count=len(eligible),
        excluded_count=len(snapshots) - len(eligible),
        missing_signal_bars=len(snapshots) - with_signal_bar,
        missing_factor_counts=dict(sorted(missing_factor_counts.items())),
        factor_coverage=factor_coverage,
        snapshots=snapshots,
        candidates=ranked,
    )
