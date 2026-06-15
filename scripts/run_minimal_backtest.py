from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.backtest.engine import BacktestConfig, run_cross_sectional_backtest  # noqa: E402
from stock_selector.data.eastmoney import fetch_a_share_quotes  # noqa: E402
from stock_selector.data.eastmoney_history import (  # noqa: E402
    SOURCE_NAME as EASTMONEY_HISTORY_SOURCE,
    fetch_benchmark_series,
    fetch_many_historical_series,
)
from stock_selector.data.models import AShareQuote, DataFetchFailure  # noqa: E402
from stock_selector.data.sina import fetch_sina_a_share_quotes  # noqa: E402
from stock_selector.data.tencent_history import (  # noqa: E402
    SOURCE_NAME as TENCENT_HISTORY_SOURCE,
    fetch_many_tencent_series,
)
from stock_selector.data.yahoo_history import fetch_yahoo_index_series  # noqa: E402
from stock_selector.reports.backtest_report import write_backtest_outputs  # noqa: E402
from stock_selector.screening.momentum_liquidity import is_excluded_name, ScreenConfig  # noqa: E402


def default_start_end() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=365)
    return start.isoformat(), end.isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    start_date, end_date = default_start_end()
    parser = argparse.ArgumentParser(description="运行 point-in-time 历史行情驱动的可信 A 股研究回测。")
    parser.add_argument("--start-date", default=start_date, help="回测开始日期，YYYY-MM-DD。")
    parser.add_argument("--end-date", default=end_date, help="回测结束日期，YYYY-MM-DD。")
    parser.add_argument("--top-n", type=int, default=10, help="每期持仓数量。")
    parser.add_argument("--rebalance-frequency", choices=["daily", "weekly"], default="weekly", help="调仓频率。")
    parser.add_argument("--execution-timing", choices=["next_open", "next_close"], default="next_open", help="信号日后的执行价格口径，默认下一交易日开盘。")
    parser.add_argument("--transaction-cost", type=float, default=0.001, help="单边交易成本率。")
    parser.add_argument("--slippage", type=float, default=0.0005, help="单边滑点率。")
    parser.add_argument("--data-source", choices=["auto", "eastmoney", "tencent"], default="tencent", help="历史行情数据源；当前默认腾讯前复权日线，auto 会先试东财再回退腾讯。")
    parser.add_argument("--universe-source", choices=["auto", "sina", "eastmoney", "csv"], default="sina", help="股票池代码来源。csv 为显式调试模式。")
    parser.add_argument(
        "--universe-filter-mode",
        choices=["broad_current_listed", "snapshot_liquidity"],
        default="broad_current_listed",
        help="股票池过滤方式。默认只使用当前仍上市代码与名称，不用今天成交额/涨跌幅/评分过滤过去。",
    )
    parser.add_argument("--universe-csv", default="", help="可复用股票池 CSV，需包含 code/name/exchange/board。")
    parser.add_argument("--universe-limit", type=int, default=80, help="股票池最多保留多少只，默认控制真实请求成本。")
    parser.add_argument("--universe-min-amount", type=float, default=500_000_000.0, help="仅在 snapshot_liquidity 模式下使用的实时最低成交额。")
    parser.add_argument("--adjustment", choices=["qfq", "none", "hfq"], default="qfq", help="股票历史价格复权方式。")
    parser.add_argument("--timeout", type=float, default=20.0, help="外部请求超时时间。")
    parser.add_argument("--retries", type=int, default=2, help="历史行情请求失败后的重试次数。")
    parser.add_argument("--cache-root", default=str(ROOT / "data" / "cache" / "historical_quotes"), help="历史行情缓存目录。")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "minimal_backtest"), help="报告输出目录。")
    return parser.parse_args(argv)


def fetch_snapshot_quotes(source: str, timeout: float) -> tuple[list[AShareQuote], dict[str, Any]]:
    if source == "eastmoney":
        quotes, metadata = fetch_a_share_quotes(page_size=2000, timeout=timeout)
        metadata["provider"] = "eastmoney"
        return quotes, metadata
    if source == "sina":
        quotes, metadata = fetch_sina_a_share_quotes(page_size=100, timeout=timeout)
        metadata["provider"] = "sina"
        return quotes, metadata
    try:
        quotes, metadata = fetch_a_share_quotes(page_size=2000, timeout=timeout)
        metadata["provider"] = "eastmoney"
        return quotes, metadata
    except Exception as exc:
        quotes, metadata = fetch_sina_a_share_quotes(page_size=100, timeout=timeout)
        metadata["provider"] = "sina"
        metadata["fallback_from"] = "eastmoney"
        metadata["fallback_error"] = f"{type(exc).__name__}: {exc}"
        return quotes, metadata


def select_universe_from_quotes(
    quotes: list[AShareQuote],
    *,
    limit: int,
    min_amount: float,
) -> list[dict[str, str]]:
    config = ScreenConfig()
    accepted = []
    for quote in quotes:
        if not quote.code or len(quote.code) != 6:
            continue
        if quote.exchange not in {"SH", "SZ", "BJ"}:
            continue
        if is_excluded_name(quote.name, config):
            continue
        if quote.latest_price is None or quote.latest_price <= 0:
            continue
        if quote.amount is None or quote.amount < min_amount:
            continue
        accepted.append(quote)
    accepted.sort(key=lambda item: (item.amount or 0.0, item.turnover_rate or 0.0), reverse=True)
    return [
        {
            "code": quote.code,
            "name": quote.name,
            "exchange": quote.exchange,
            "board": quote.board,
            "snapshot_amount": str(quote.amount or ""),
            "snapshot_turnover_rate": str(quote.turnover_rate or ""),
        }
        for quote in accepted[:limit]
    ]


def select_broad_current_listed_universe(
    quotes: list[AShareQuote],
    *,
    limit: int,
) -> list[dict[str, str]]:
    config = ScreenConfig()
    accepted: dict[str, AShareQuote] = {}
    for quote in quotes:
        if not quote.code or len(quote.code) != 6:
            continue
        if quote.exchange not in {"SH", "SZ", "BJ"}:
            continue
        if is_excluded_name(quote.name, config):
            continue
        accepted.setdefault(quote.code, quote)
    return [
        {
            "code": quote.code,
            "name": quote.name,
            "exchange": quote.exchange,
            "board": quote.board,
        }
        for quote in sorted(accepted.values(), key=lambda item: item.code)[:limit]
    ]


def read_universe_csv(path: Path, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            rows.append(
                {
                    "code": code,
                    "name": str(row.get("name") or code).strip(),
                    "exchange": str(row.get("exchange") or "").strip(),
                    "board": str(row.get("board") or "").strip(),
                }
            )
            if len(rows) >= limit:
                break
    return rows


def build_universe(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if args.universe_source == "csv":
        if not args.universe_csv:
            raise ValueError("--universe-source csv requires --universe-csv")
        rows = read_universe_csv(Path(args.universe_csv), args.universe_limit)
        return rows, {
            "provider": "csv",
            "universe_mode": "csv_debug",
            "source_file": args.universe_csv,
            "universe_limit": args.universe_limit,
            "selected_count": len(rows),
            "research_warning": "fixed CSV universe is explicit debug mode and is not default strategy validation",
        }
    quotes, metadata = fetch_snapshot_quotes(args.universe_source, args.timeout)
    if args.universe_filter_mode == "snapshot_liquidity":
        rows = select_universe_from_quotes(
            quotes,
            limit=args.universe_limit,
            min_amount=args.universe_min_amount,
        )
        metadata["universe_mode"] = "snapshot_liquidity"
        metadata["research_warning"] = (
            "uses current snapshot amount/turnover to shape the historical universe; "
            "kept for diagnostics, not default strategy validation"
        )
    else:
        rows = select_broad_current_listed_universe(quotes, limit=args.universe_limit)
        metadata["universe_mode"] = "broad_current_listed"
        metadata["research_warning"] = (
            "uses current listed A-share code identity only; still has survivorship/current-status bias "
            "because historical delisted names are not included"
        )
    metadata["universe_limit"] = args.universe_limit
    metadata["universe_filter_mode"] = args.universe_filter_mode
    metadata["universe_min_amount"] = args.universe_min_amount if args.universe_filter_mode == "snapshot_liquidity" else None
    metadata["selected_count"] = len(rows)
    return rows, metadata


def periods_per_year(frequency: str) -> int:
    return 252 if frequency == "daily" else 52


def fetch_history_for_universe(
    universe: list[dict[str, str]],
    args: argparse.Namespace,
    cache_root: Path,
) -> tuple[dict[str, Any], list[DataFetchFailure], str]:
    if args.data_source == "tencent":
        series_by_code, failures = fetch_many_tencent_series(
            universe,
            start_date=args.start_date,
            end_date=args.end_date,
            adjustment=args.adjustment,
            cache_root=cache_root,
            timeout=args.timeout,
            retries=args.retries,
        )
        return series_by_code, failures, TENCENT_HISTORY_SOURCE
    if args.data_source == "eastmoney":
        series_by_code, failures = fetch_many_historical_series(
            universe,
            start_date=args.start_date,
            end_date=args.end_date,
            adjustment=args.adjustment,
            cache_root=cache_root,
            timeout=args.timeout,
            retries=args.retries,
        )
        return series_by_code, failures, EASTMONEY_HISTORY_SOURCE

    eastmoney_series, eastmoney_failures = fetch_many_historical_series(
        universe,
        start_date=args.start_date,
        end_date=args.end_date,
        adjustment=args.adjustment,
        cache_root=cache_root,
        timeout=args.timeout,
        retries=args.retries,
    )
    failed_codes = {failure.code for failure in eastmoney_failures}
    fallback_symbols = [symbol for symbol in universe if symbol.get("code") in failed_codes]
    tencent_series, tencent_failures = fetch_many_tencent_series(
        fallback_symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        adjustment=args.adjustment,
        cache_root=cache_root,
        timeout=args.timeout,
        retries=args.retries,
    )
    combined_failures = [failure for failure in eastmoney_failures if failure.code not in tencent_series]
    combined_failures.extend(tencent_failures)
    eastmoney_series.update(tencent_series)
    return eastmoney_series, combined_failures, f"{EASTMONEY_HISTORY_SOURCE}; fallback {TENCENT_HISTORY_SOURCE}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    universe, universe_metadata = build_universe(args)
    if not universe:
        raise RuntimeError("no universe symbols selected; cannot run backtest")

    cache_root = Path(args.cache_root)
    print(f"Selected universe: {len(universe)} symbols from {universe_metadata.get('provider')}")
    series_by_code, failures, history_source = fetch_history_for_universe(universe, args, cache_root)
    benchmark_failures: list[DataFetchFailure] = []
    try:
        benchmark = fetch_benchmark_series(
            start_date=args.start_date,
            end_date=args.end_date,
            cache_root=cache_root,
            timeout=args.timeout,
            retries=args.retries,
        )
    except Exception as exc:
        benchmark_failures.append(
            DataFetchFailure(
                code="000300",
                name="沪深300",
                source=EASTMONEY_HISTORY_SOURCE,
                requested_start=args.start_date,
                requested_end=args.end_date,
                error=f"{type(exc).__name__}: {exc}",
            )
        )
        benchmark = fetch_yahoo_index_series(
            start_date=args.start_date,
            end_date=args.end_date,
            cache_root=cache_root,
            timeout=args.timeout,
            retries=args.retries,
        )
    config = BacktestConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        top_n=args.top_n,
        rebalance_frequency=args.rebalance_frequency,
        execution_timing=args.execution_timing,
        transaction_cost_rate=args.transaction_cost,
        slippage_rate=args.slippage,
        adjustment=args.adjustment,
        data_source=args.data_source,
        universe_size=len(universe),
        universe_construction=(
            f"{universe_metadata.get('provider')} {universe_metadata.get('universe_mode')} "
            f"limit {args.universe_limit}; historical delisted names are not included"
        ),
        universe_mode=str(universe_metadata.get("universe_mode") or args.universe_filter_mode),
        fixed_current_universe=True,
        survivorship_bias=(
            "current listed A-share transition universe; no current price, amount, score or candidate rank "
            "is used in default broad_current_listed mode, but delisted historical names are absent"
        ),
        periods_per_year=periods_per_year(args.rebalance_frequency),
    )
    result = run_cross_sectional_backtest(
        series_by_code=series_by_code,
        benchmark=benchmark,
        config=config,
        data_failures=failures + benchmark_failures,
    )
    result.data_audit["universe_metadata"] = universe_metadata
    result.data_audit["history_source"] = history_source
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_minimal_backtest")
    paths = write_backtest_outputs(
        run_id=run_id,
        result=result,
        output_dir=Path(args.output_dir),
        universe_rows=universe,
    )
    summary = {
        "run_id": run_id,
        "report_html": str(paths.report_html),
        "latest_html": str(paths.latest_html),
        "summary_json": str(paths.summary_json),
        "periods_csv": str(paths.periods_csv),
        "holdings_csv": str(paths.holdings_csv),
        "failures_csv": str(paths.failures_csv),
        "universe_csv": str(paths.universe_csv),
        "strategy_metrics": result.strategy_metrics.as_dict(),
        "benchmark_metrics": result.benchmark_metrics.as_dict(),
        "baseline_metrics": {key: value.as_dict() for key, value in result.baseline_metrics.items()},
        "conclusion": result.conclusion,
        "data_audit": result.data_audit,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
