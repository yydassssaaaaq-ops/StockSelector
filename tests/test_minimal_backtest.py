from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.backtest.engine import BacktestConfig, run_cross_sectional_backtest  # noqa: E402
from stock_selector.backtest.metrics import calculate_metrics, max_drawdown  # noqa: E402
from stock_selector.data.eastmoney import parse_quote_record  # noqa: E402
from stock_selector.data.eastmoney_history import (  # noqa: E402
    HistoricalDataError,
    fetch_historical_series,
    parse_kline_row,
)
from stock_selector.data.models import DailyBar, DataFetchFailure, HistoricalSeries  # noqa: E402
from stock_selector.data.sina import parse_sina_record  # noqa: E402
from stock_selector.data.tencent_history import fetch_tencent_series  # noqa: E402
from stock_selector.reports.backtest_report import write_backtest_outputs  # noqa: E402
from stock_selector.screening.momentum_liquidity import ScreenConfig, score_quote_detailed  # noqa: E402


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


class MinimalBacktestTest(unittest.TestCase):
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

    def test_signal_date_and_execution_date_are_separated_and_no_future_function(self):
        stocks = {
            "600001": series("600001", "当期强", [10, 100, 100, 110, 110, 110], [5, 0, -1, 0, 0, 0]),
            "600002": series("600002", "未来强", [10, 100, 100, 90, 90, 99], [0, 0, 8, 0, 8, 0]),
        }
        benchmark = series("000300", "沪深300", [100, 100, 100, 105, 105, 105], [0, 0, 0, 5, 0, 0])
        result = run_cross_sectional_backtest(
            series_by_code=stocks,
            benchmark=benchmark,
            config=BacktestConfig(
                start_date=DATES[0],
                end_date=DATES[-1],
                top_n=1,
                transaction_cost_rate=0.001,
                slippage_rate=0.0,
                universe_size=2,
                periods_per_year=52,
            ),
        )
        self.assertEqual(result.periods[0].signal_date, "2026-01-02")
        self.assertEqual(result.periods[0].entry_date, "2026-01-05")
        self.assertEqual(result.periods[0].holdings[0].code, "600001")
        self.assertNotEqual(result.periods[0].holdings[0].code, "600002")
        self.assertAlmostEqual(result.periods[0].gross_return or 0.0, 0.10)
        self.assertAlmostEqual(result.periods[0].net_return or 0.0, 0.099)
        self.assertAlmostEqual(result.periods[0].benchmark_return or 0.0, 0.05)

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
            periods_text = paths.periods_csv.read_text(encoding="utf-8-sig")
            self.assertIn("net_return", periods_text)
            self.assertIn("2026-01-02", periods_text)


if __name__ == "__main__":
    unittest.main()
