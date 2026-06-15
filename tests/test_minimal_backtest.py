from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.backtest.engine import BacktestConfig, run_cross_sectional_backtest  # noqa: E402
from stock_selector.backtest.execution import execute_holding_return  # noqa: E402
from stock_selector.backtest.metrics import calculate_metrics, max_drawdown  # noqa: E402
from stock_selector.data.eastmoney import parse_quote_record  # noqa: E402
from stock_selector.data.eastmoney_history import (  # noqa: E402
    HistoricalDataError,
    fetch_historical_series,
    parse_kline_row,
)
from stock_selector.data.models import DailyBar, DataFetchFailure, HistoricalSeries  # noqa: E402
from stock_selector.features.historical_factors import factor_snapshot_for_series, score_historical_universe  # noqa: E402
from stock_selector.data.sina import parse_sina_record  # noqa: E402
from stock_selector.data.tencent_history import fetch_tencent_series  # noqa: E402
from stock_selector.reports.backtest_report import write_backtest_outputs  # noqa: E402
from stock_selector.screening.momentum_liquidity import ScreenConfig, score_quote_detailed  # noqa: E402
from scripts.run_minimal_backtest import parse_args  # noqa: E402


DATES = ["2026-01-02", "2026-01-05", "2026-01-09", "2026-01-12", "2026-01-16", "2026-01-19"]


def bar(code: str, name: str, date: str, close: float, pct: float, amount: float = 900_000_000.0) -> DailyBar:
    return DailyBar(
        code=code,
        name=name,
        exchange="SH" if code.startswith("6") else "SZ",
        board="SH_MAIN" if code.startswith("6") else "SZ_MAIN",
        date=date,
        open=close * 0.99,
        close=close,
        high=close * 1.02,
        low=close * 0.98,
        volume=100_000,
        amount=amount,
        amplitude=4.0,
        pct_change=pct,
        change_amount=close * pct / 100.0,
        turnover_rate=3.0,
        adjustment="qfq",
        source="fixture",
    )


def series(code: str, name: str, closes: list[float], pcts: list[float]) -> HistoricalSeries:
    bars = [bar(code, name, day, close, pct) for day, close, pct in zip(DATES, closes, pcts)]
    return HistoricalSeries(
        code=code,
        name=name,
        exchange="SH" if code.startswith("6") else "SZ",
        board="SH_MAIN" if code.startswith("6") else "SZ_MAIN",
        source="fixture",
        adjustment="qfq",
        requested_start=DATES[0],
        requested_end=DATES[-1],
        fetched_at="2026-01-19T16:00:00+08:00",
        bars=bars,
        cache_hit=False,
        completeness={"returned_rows": len(bars), "has_data": True},
    )


def trading_days(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    days: list[str] = []
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def long_series(
    code: str,
    name: str,
    dates: list[str],
    closes: list[float],
    *,
    amount: float = 900_000_000.0,
    volume: int = 100_000,
    open_overrides: dict[str, float] | None = None,
    volume_overrides: dict[str, int] | None = None,
) -> HistoricalSeries:
    open_overrides = open_overrides or {}
    volume_overrides = volume_overrides or {}
    bars: list[DailyBar] = []
    previous_close: float | None = None
    for trade_date, close in zip(dates, closes):
        open_price = open_overrides.get(trade_date, close * 0.995)
        pct = (close / previous_close - 1.0) * 100.0 if previous_close else None
        high = max(open_price, close) * 1.01
        low = min(open_price, close) * 0.99
        amplitude = (high - low) / previous_close * 100.0 if previous_close else None
        bars.append(
            DailyBar(
                code=code,
                name=name,
                exchange="SH" if code.startswith("6") else "SZ",
                board="SH_MAIN" if code.startswith("6") else "SZ_MAIN",
                date=trade_date,
                open=open_price,
                close=close,
                high=high,
                low=low,
                volume=volume_overrides.get(trade_date, volume),
                amount=amount,
                amplitude=amplitude,
                pct_change=pct,
                change_amount=(close - previous_close) if previous_close else None,
                turnover_rate=None,
                adjustment="qfq",
                source="fixture",
            )
        )
        previous_close = close
    return HistoricalSeries(
        code=code,
        name=name,
        exchange="SH" if code.startswith("6") else "SZ",
        board="SH_MAIN" if code.startswith("6") else "SZ_MAIN",
        source="fixture",
        adjustment="qfq",
        requested_start=dates[0],
        requested_end=dates[-1],
        fetched_at="2026-01-01T16:00:00+08:00",
        bars=bars,
        cache_hit=False,
        completeness={"returned_rows": len(bars), "has_data": True},
    )


class MinimalBacktestTest(unittest.TestCase):
    def test_cli_default_universe_is_broad_current_listed_not_csv_debug(self):
        args = parse_args([])
        self.assertEqual(args.universe_source, "sina")
        self.assertEqual(args.universe_filter_mode, "broad_current_listed")
        self.assertNotEqual(args.universe_source, "csv")

    def test_common_daily_bar_model_converts_to_neutral_quote(self):
        item = bar("600001", "模型股份", "2026-01-02", 11.0, 10.0)
        quote = item.to_quote()
        self.assertEqual(quote.code, "600001")
        self.assertEqual(quote.latest_price, 11.0)
        self.assertAlmostEqual(quote.previous_close or 0.0, 10.0)
        self.assertIsNone(quote.main_net_inflow)

    def test_data_source_field_mapping_uses_neutral_model(self):
        eastmoney_quote = parse_quote_record(
            {
                "f12": "600001",
                "f14": "映射股份",
                "f2": 10.0,
                "f3": 2.0,
                "f5": 100,
                "f6": 600_000_000,
                "f7": 5.0,
                "f8": 2.0,
                "f9": 20.0,
                "f10": 1.2,
                "f15": 10.4,
                "f16": 9.8,
                "f17": 10.1,
                "f18": 9.8,
                "f20": 10_000_000_000,
                "f21": 8_000_000_000,
                "f23": 2.0,
                "f62": 50_000_000,
                "f184": 5.0,
            }
        )
        sina_quote = parse_sina_record(
            {
                "symbol": "sh600001",
                "code": "600001",
                "name": "映射股份",
                "trade": "10.00",
                "changepercent": "2.0",
                "volume": "100",
                "amount": "600000000",
                "turnoverratio": "2.0",
                "settlement": "9.80",
                "high": "10.40",
                "low": "9.80",
            }
        )
        self.assertEqual(eastmoney_quote.code, sina_quote.code)
        self.assertEqual(eastmoney_quote.exchange, sina_quote.exchange)
        self.assertIsNone(sina_quote.main_net_inflow)
        self.assertEqual(eastmoney_quote.main_net_inflow, 50_000_000)

    def test_adjusted_history_cache_hit_and_metadata(self):
        payload = {
            "rc": 0,
            "data": {"klines": ["2026-01-02,10,11,12,9,1000,1000000,30,10,1,2"]},
        }

        def loader(_url: str, _timeout: float):
            return payload

        with tempfile.TemporaryDirectory(prefix="history_cache_") as td:
            first = fetch_historical_series(
                code="600001",
                name="缓存股份",
                exchange="SH",
                board="SH_MAIN",
                start_date="2026-01-01",
                end_date="2026-01-31",
                adjustment="qfq",
                cache_root=Path(td),
                loader=loader,
            )
            self.assertFalse(first.cache_hit)
            self.assertEqual(first.adjustment, "qfq")

            def failing_loader(_url: str, _timeout: float):
                raise AssertionError("cache was not used")

            second = fetch_historical_series(
                code="600001",
                name="缓存股份",
                exchange="SH",
                board="SH_MAIN",
                start_date="2026-01-01",
                end_date="2026-01-31",
                adjustment="qfq",
                cache_root=Path(td),
                loader=failing_loader,
            )
            self.assertTrue(second.cache_hit)
            self.assertEqual(second.completeness["returned_rows"], 1)

    def test_tencent_qfq_history_maps_real_ohlcv_and_marks_turnover_missing(self):
        payload = {
            "code": 0,
            "data": {
                "sz000725": {
                    "qfqday": [
                        ["2026-01-05", "4.220", "4.230", "4.270", "4.190", "8507616.000"],
                        ["2026-01-06", "4.300", "4.500", "4.550", "4.290", "7300000.000"],
                    ]
                }
            },
        }

        def loader(_url: str, _timeout: float):
            return payload

        with tempfile.TemporaryDirectory(prefix="tencent_history_") as td:
            item = fetch_tencent_series(
                code="000725",
                name="京东方Ａ",
                exchange="SZ",
                board="SZ_MAIN",
                start_date="2026-01-01",
                end_date="2026-01-31",
                adjustment="qfq",
                cache_root=Path(td),
                loader=loader,
            )
            self.assertEqual(item.source, "Tencent qfq daily kline")
            self.assertEqual(item.bars[0].close, 4.23)
            self.assertAlmostEqual(item.bars[0].amount, 8507616 * 100 * 4.23)
            self.assertIsNone(item.bars[0].turnover_rate)
            self.assertIn("amount_derivation", item.completeness)

    def test_abnormal_history_row_is_not_accepted_as_normal_data(self):
        with self.assertRaises(HistoricalDataError):
            parse_kline_row(
                "2026-01-02,0,11,12,9,1000,1000000,30,10,1,2",
                code="600001",
                name="异常股份",
                exchange="SH",
                board="SH_MAIN",
                adjustment="qfq",
            )

    def test_missing_factor_weights_are_renormalized(self):
        quote = parse_sina_record(
            {
                "symbol": "sh600001",
                "code": "600001",
                "name": "缺因子股份",
                "trade": "10.00",
                "changepercent": "2.5",
                "volume": "100",
                "amount": "800000000",
                "turnoverratio": "3.0",
                "settlement": "9.80",
                "high": "10.40",
                "low": "9.80",
                "per": "20",
                "pb": "2",
            }
        )
        details = score_quote_detailed(quote, ScreenConfig())
        self.assertIn("capital_flow_pct", details["missing_factors"])
        self.assertIn("capital_flow_amount", details["missing_factors"])
        self.assertAlmostEqual(details["data_completeness"], 0.7)
        self.assertAlmostEqual(sum(details["effective_weights"].values()), 100.0, places=2)
        self.assertFalse(details["cross_source_comparable"])

    def test_historical_signal_uses_only_bars_up_to_signal_date(self):
        dates = trading_days("2026-01-02", 75)
        signal_date = dates[63]
        stable_up = [10.0 + index * 0.08 for index in range(len(dates))]
        future_jump = [10.0 + index * 0.01 for index in range(len(dates))]
        stocks = {
            "600001": long_series("600001", "当期趋势", dates, stable_up),
            "600002": long_series("600002", "未来跳涨", dates, future_jump),
        }
        before = score_historical_universe(stocks, signal_date, top_n=2).as_dict()

        mutated_jump = future_jump[:]
        for index, trade_date in enumerate(dates):
            if trade_date > signal_date:
                mutated_jump[index] = mutated_jump[index] * 3
        mutated = {
            "600001": long_series("600001", "当期趋势", dates, stable_up),
            "600002": long_series("600002", "未来跳涨", dates, mutated_jump),
        }
        after = score_historical_universe(mutated, signal_date, top_n=2).as_dict()

        self.assertEqual(before["candidates"], after["candidates"])
        self.assertEqual(before["factor_coverage"], after["factor_coverage"])

    def test_window_and_listing_age_shortage_excludes_stock(self):
        dates = trading_days("2026-01-02", 30)
        item = long_series("600001", "窗口不足", dates, [10.0 + index * 0.1 for index in range(len(dates))])
        snapshot = factor_snapshot_for_series(item, dates[-1])
        self.assertFalse(snapshot.is_eligible)
        self.assertIn("trend_60d_return", snapshot.missing_factors)

    def test_signal_date_and_next_open_execution_are_separated(self):
        dates = trading_days("2026-01-02", 75)
        trend = [10.0 + index * 0.10 for index in range(len(dates))]
        weaker = [10.0 + index * 0.01 for index in range(len(dates))]
        benchmark_closes = [100.0 + index * 0.02 for index in range(len(dates))]
        stocks = {
            "600001": long_series("600001", "当期强", dates, trend),
            "600002": long_series("600002", "未来弱", dates, weaker),
        }
        benchmark = long_series("000300", "沪深300", dates, benchmark_closes)
        result = run_cross_sectional_backtest(
            series_by_code=stocks,
            benchmark=benchmark,
            config=BacktestConfig(
                start_date=dates[0],
                end_date=dates[-1],
                top_n=1,
                transaction_cost_rate=0.001,
                slippage_rate=0.0,
                universe_size=2,
                periods_per_year=52,
            ),
        )
        period = next(item for item in result.periods if item.holdings)
        self.assertLess(period.signal_date, period.entry_date)
        self.assertEqual(period.holdings[0].entry_date, period.entry_date)
        self.assertEqual(period.holdings[0].entry_status, "entry_filled")
        self.assertEqual(period.holdings[0].code, "600001")
        self.assertEqual(result.config.execution_timing, "next_open")

    def test_untradable_entry_keeps_partial_weight_as_cash(self):
        dates = trading_days("2026-01-02", 75)
        closes_a = [10.0 + index * 0.10 for index in range(len(dates))]
        closes_b = [10.0 + index * 0.09 for index in range(len(dates))]
        blocked_entry_dates = {trade_date: 0 for trade_date in dates[61:]}
        stocks = {
            "600001": long_series("600001", "可成交", dates, closes_a),
            "600002": long_series(
                "600002",
                "停牌样本",
                dates,
                closes_b,
                volume_overrides=blocked_entry_dates,
            ),
        }
        benchmark = long_series("000300", "沪深300", dates, [100.0 + index * 0.02 for index in range(len(dates))])
        result = run_cross_sectional_backtest(
            series_by_code=stocks,
            benchmark=benchmark,
            config=BacktestConfig(start_date=dates[0], end_date=dates[-1], top_n=2, universe_size=2),
        )
        period = next(item for item in result.periods if item.selected_count == 2)
        self.assertEqual(period.held_count, 1)
        self.assertGreater(period.cash_weight, 0.0)
        self.assertIn("600002", period.blocked_entries)

    def test_limit_up_entry_and_limit_down_exit_constraints_are_recorded(self):
        dates = trading_days("2026-01-02", 5)
        entry_date = dates[1]
        exit_date = dates[2]
        limit_up_series = long_series(
            "600001",
            "涨停难买",
            dates,
            [10.0, 11.0, 11.2, 11.3, 11.4],
            open_overrides={entry_date: 10.99},
        )
        blocked_buy = execute_holding_return(
            code="600001",
            series_map={bar.date: bar for bar in limit_up_series.bars},
            planned_entry_date=entry_date,
            planned_exit_date=exit_date,
            timing="next_open",
        )
        self.assertEqual(blocked_buy.entry_status, "probable_limit_up_entry_blocked")

        sell_dates = trading_days("2026-02-02", 5)
        planned_exit = sell_dates[2]
        sell_series = long_series(
            "600002",
            "跌停难卖",
            sell_dates,
            [10.0, 10.1, 9.09, 9.2, 9.3],
            open_overrides={planned_exit: 9.09},
        )
        delayed_sell = execute_holding_return(
            code="600002",
            series_map={bar.date: bar for bar in sell_series.bars},
            planned_entry_date=sell_dates[1],
            planned_exit_date=planned_exit,
            timing="next_open",
            max_exit_delay_days=2,
        )
        self.assertEqual(delayed_sell.exit_date, sell_dates[3])
        self.assertIn("probable_limit_down_exit_blocked", ";".join(delayed_sell.notes))

    def test_transaction_cost_return_drawdown_and_benchmark_alignment(self):
        metrics = calculate_metrics(
            [0.10, -0.10],
            periods_per_year=52,
            turnovers=[1.0, 2.0],
            trade_count=3,
            benchmark_returns=[0.05, 0.0],
        )
        self.assertAlmostEqual(metrics.cumulative_return, -0.01)
        self.assertAlmostEqual(max_drawdown([0.10, -0.10]), 0.10)
        self.assertAlmostEqual(metrics.turnover_rate, 1.5)
        self.assertEqual(metrics.trade_count, 3)
        self.assertEqual(metrics.effective_periods, 2)
        self.assertAlmostEqual(metrics.excess_cumulative_return or 0.0, -0.06)

    def test_single_stock_failure_does_not_interrupt_backtest_and_report_has_values(self):
        stocks = {
            "600001": series("600001", "成功股份", [10, 100, 100, 110, 110, 110], [5, 0, 1, 0, 1, 0]),
        }
        benchmark = series("000300", "沪深300", [100, 100, 100, 105, 105, 105], [0, 0, 0, 5, 0, 0])
        failure = DataFetchFailure(
            code="600999",
            name="失败股份",
            source="fixture",
            requested_start=DATES[0],
            requested_end=DATES[-1],
            error="fixture failure",
        )
        result = run_cross_sectional_backtest(
            series_by_code=stocks,
            benchmark=benchmark,
            config=BacktestConfig(start_date=DATES[0], end_date=DATES[-1], top_n=1, universe_size=2),
            data_failures=[failure],
        )
        self.assertEqual(result.data_audit["failed_series"], 1)
        self.assertGreaterEqual(result.strategy_metrics.effective_periods, 1)
        with tempfile.TemporaryDirectory(prefix="backtest_report_") as td:
            paths = write_backtest_outputs(
                run_id="20260119_test",
                result=result,
                output_dir=Path(td),
                universe_rows=[{"code": "600001", "name": "成功股份", "exchange": "SH", "board": "SH_MAIN"}],
            )
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["data_failures"][0]["code"], "600999")
            self.assertEqual(summary["strategy_metrics"]["effective_periods"], result.strategy_metrics.effective_periods)
            self.assertIn("strategy_identity", summary["data_audit"])
            self.assertIn("point_in_time_controls", summary["data_audit"])
            self.assertIn("can_prove", summary["data_audit"])
            self.assertIn("cannot_prove", summary["data_audit"])
            self.assertIn("universe_equal_weight", summary["baseline_metrics"])
            periods_text = paths.periods_csv.read_text(encoding="utf-8-sig")
            self.assertIn("net_return", periods_text)
            self.assertIn("2026-01-02", periods_text)


if __name__ == "__main__":
    unittest.main()
