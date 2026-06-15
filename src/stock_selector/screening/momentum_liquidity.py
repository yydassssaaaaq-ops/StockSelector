from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from stock_selector.data.models import AShareQuote


BASE_FACTOR_WEIGHTS = {
    "momentum": 25.0,
    "liquidity_amount": 15.0,
    "liquidity_turnover": 10.0,
    "capital_flow_pct": 20.0,
    "capital_flow_amount": 10.0,
    "valuation_guard": 10.0,
    "volatility_guard": 10.0,
}
TOTAL_FACTOR_WEIGHT = sum(BASE_FACTOR_WEIGHTS.values())


@dataclass(frozen=True)
class ScreenConfig:
    top_n: int = 30
    min_price: float = 2.0
    max_price: float = 250.0
    min_amount: float = 200_000_000.0
    min_turnover_rate: float = 0.8
    max_turnover_rate: float = 18.0
    min_pct_change: float = -3.0
    max_pct_change: float = 9.8
    max_amplitude: float = 18.0
    max_pe_ttm: float = 120.0
    allow_missing_turnover_rate: bool = False
    exclude_new_listing_prefixes: tuple[str, ...] = ("N", "C")
    exclude_name_tokens: tuple[str, ...] = ("ST", "*ST", "退")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["exclude_new_listing_prefixes"] = list(self.exclude_new_listing_prefixes)
        data["exclude_name_tokens"] = list(self.exclude_name_tokens)
        return data


@dataclass(frozen=True)
class ScreenedStock:
    rank: int
    score: float
    quote: AShareQuote
    score_parts: dict[str, float]
    raw_factor_scores: dict[str, float]
    effective_weights: dict[str, float]
    missing_factors: list[str]
    data_completeness: float
    cross_source_comparable: bool
    decision_notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        data = {
            "rank": self.rank,
            "score": self.score,
            "score_parts": self.score_parts,
            "raw_factor_scores": self.raw_factor_scores,
            "effective_weights": self.effective_weights,
            "missing_factors": self.missing_factors,
            "data_completeness": self.data_completeness,
            "cross_source_comparable": self.cross_source_comparable,
            "decision_notes": self.decision_notes,
        }
        data.update(self.quote.as_dict())
        return data


@dataclass(frozen=True)
class ScreenResult:
    config: ScreenConfig
    total_quotes: int
    accepted_before_top_n: int
    rejected_quotes: int
    rejection_counts: dict[str, int]
    candidates: list[ScreenedStock]

    def as_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.as_dict(),
            "total_quotes": self.total_quotes,
            "accepted_before_top_n": self.accepted_before_top_n,
            "rejected_quotes": self.rejected_quotes,
            "rejection_counts": self.rejection_counts,
            "candidates": [item.as_dict() for item in self.candidates],
        }


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def scale(value: float | None, low: float, high: float) -> float:
    if value is None or high == low:
        return 0.0
    return clamp((value - low) / (high - low))


def log_scale(value: float | None, low: float, high: float) -> float:
    if value is None or value <= 0 or low <= 0 or high <= low:
        return 0.0
    return clamp((math.log10(value) - math.log10(low)) / (math.log10(high) - math.log10(low)))


def is_excluded_name(name: str, config: ScreenConfig) -> bool:
    upper = name.upper()
    if any(token in upper for token in config.exclude_name_tokens):
        return True
    return any(upper.startswith(prefix) for prefix in config.exclude_new_listing_prefixes)


def reject_reasons(quote: AShareQuote, config: ScreenConfig) -> list[str]:
    reasons: list[str] = []
    if not quote.code or len(quote.code) != 6:
        reasons.append("invalid_code")
    if is_excluded_name(quote.name, config):
        reasons.append("excluded_name")
    if quote.latest_price is None or quote.latest_price <= 0:
        reasons.append("missing_price")
    elif quote.latest_price < config.min_price or quote.latest_price > config.max_price:
        reasons.append("price_out_of_range")
    if quote.amount is None or quote.amount < config.min_amount:
        reasons.append("amount_too_low")
    if quote.turnover_rate is None:
        if not config.allow_missing_turnover_rate:
            reasons.append("missing_turnover_rate")
    elif quote.turnover_rate < config.min_turnover_rate:
        reasons.append("turnover_too_low")
    elif quote.turnover_rate > config.max_turnover_rate:
        reasons.append("turnover_too_high")
    if quote.pct_change is None:
        reasons.append("missing_pct_change")
    elif quote.pct_change < config.min_pct_change or quote.pct_change > config.max_pct_change:
        reasons.append("pct_change_out_of_range")
    if quote.amplitude is None:
        reasons.append("missing_amplitude")
    elif quote.amplitude > config.max_amplitude:
        reasons.append("amplitude_too_high")
    return reasons


def score_quote(quote: AShareQuote, config: ScreenConfig) -> tuple[float, dict[str, float], list[str]]:
    details = score_quote_detailed(quote, config)
    return details["score"], details["score_parts"], details["decision_notes"]


def score_quote_detailed(quote: AShareQuote, config: ScreenConfig) -> dict[str, Any]:
    raw_scores: dict[str, float | None] = {}

    momentum = scale(quote.pct_change, -1.0, 6.0) if quote.pct_change is not None else None
    if quote.pct_change is not None and quote.pct_change > 7.0:
        momentum = (momentum or 0.0) - min(0.4, (quote.pct_change - 7.0) * 0.12)
    raw_scores["momentum"] = momentum

    raw_scores["liquidity_amount"] = (
        log_scale(quote.amount, config.min_amount, 3_000_000_000.0) if quote.amount is not None else None
    )
    turnover_score = scale(quote.turnover_rate, config.min_turnover_rate, 8.0) if quote.turnover_rate is not None else None
    if quote.turnover_rate is not None and quote.turnover_rate > 12.0:
        turnover_score = (turnover_score or 0.0) - min(0.6, (quote.turnover_rate - 12.0) * 0.08)
    raw_scores["liquidity_turnover"] = turnover_score

    raw_scores["capital_flow_pct"] = (
        scale(quote.main_net_inflow_pct, 0.0, 12.0) if quote.main_net_inflow_pct is not None else None
    )
    flow_amount_score = (
        log_scale(quote.main_net_inflow, 10_000_000.0, 400_000_000.0)
        if quote.main_net_inflow is not None
        else None
    )
    if quote.main_net_inflow is not None and quote.main_net_inflow < 0:
        flow_amount_score = (flow_amount_score or 0.0) - 0.5
    raw_scores["capital_flow_amount"] = flow_amount_score

    valuation_components: list[float] = []
    if quote.pe_ttm is not None and 0 < quote.pe_ttm <= config.max_pe_ttm:
        valuation_components.append(0.6 * (1.0 - quote.pe_ttm / config.max_pe_ttm))
    if quote.pb is not None and 0 < quote.pb <= 10.0:
        valuation_components.append(0.4 * (1.0 - quote.pb / 10.0))
    raw_scores["valuation_guard"] = sum(valuation_components) if valuation_components else None

    volatility_score = 1.0 - scale(quote.amplitude, 6.0, config.max_amplitude) if quote.amplitude is not None else None
    if quote.volume_ratio is not None and quote.volume_ratio > 5.0:
        volatility_score = (volatility_score or 0.0) - min(0.5, (quote.volume_ratio - 5.0) * 0.1)
    raw_scores["volatility_guard"] = volatility_score

    available = {key: clamp(value or 0.0) for key, value in raw_scores.items() if value is not None}
    missing_factors = [key for key in BASE_FACTOR_WEIGHTS if key not in available]
    available_base_weight = sum(BASE_FACTOR_WEIGHTS[key] for key in available)
    effective_weights = {
        key: (BASE_FACTOR_WEIGHTS[key] / available_base_weight * TOTAL_FACTOR_WEIGHT if available_base_weight else 0.0)
        for key in available
    }
    parts = {
        key: round(available[key] * effective_weights[key], 3)
        for key in available
    }
    for key in missing_factors:
        parts[key] = 0.0
    parts = dict(sorted(parts.items()))
    score = round(sum(parts.values()), 3)
    notes = [
        f"pct_change={quote.pct_change}%",
        f"amount={quote.amount}",
        f"turnover_rate={quote.turnover_rate}%",
        f"main_net_inflow={quote.main_net_inflow}",
        f"main_net_inflow_pct={quote.main_net_inflow_pct}%",
        f"missing_factors={','.join(missing_factors) if missing_factors else 'none'}",
        f"available_base_weight={available_base_weight:.1f}/{TOTAL_FACTOR_WEIGHT:.1f}",
    ]
    return {
        "score": score,
        "score_parts": parts,
        "raw_factor_scores": {key: round(value, 6) for key, value in sorted(available.items())},
        "effective_weights": {key: round(value, 3) for key, value in sorted(effective_weights.items())},
        "missing_factors": missing_factors,
        "data_completeness": round(available_base_weight / TOTAL_FACTOR_WEIGHT, 4) if TOTAL_FACTOR_WEIGHT else 0.0,
        "cross_source_comparable": not missing_factors,
        "decision_notes": notes,
    }


def screen_quotes(quotes: list[AShareQuote], config: ScreenConfig | None = None) -> ScreenResult:
    config = config or ScreenConfig()
    rejected = Counter()
    accepted: list[tuple[float, dict[str, Any], AShareQuote]] = []
    for quote in quotes:
        reasons = reject_reasons(quote, config)
        if reasons:
            for reason in reasons:
                rejected[reason] += 1
            continue
        details = score_quote_detailed(quote, config)
        accepted.append((details["score"], details, quote))
    accepted.sort(
        key=lambda item: (
            item[0],
            item[2].main_net_inflow_pct or -999.0,
            item[2].amount or 0.0,
            item[2].pct_change or -999.0,
        ),
        reverse=True,
    )
    candidates = [
        ScreenedStock(
            rank=i + 1,
            score=score,
            quote=quote,
            score_parts=details["score_parts"],
            raw_factor_scores=details["raw_factor_scores"],
            effective_weights=details["effective_weights"],
            missing_factors=details["missing_factors"],
            data_completeness=details["data_completeness"],
            cross_source_comparable=details["cross_source_comparable"],
            decision_notes=details["decision_notes"],
        )
        for i, (score, details, quote) in enumerate(accepted[: config.top_n])
    ]
    return ScreenResult(
        config=config,
        total_quotes=len(quotes),
        accepted_before_top_n=len(accepted),
        rejected_quotes=len(quotes) - len(accepted),
        rejection_counts=dict(sorted(rejected.items())),
        candidates=candidates,
    )
