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

from stock_selector.data.eastmoney import parse_quote_record  # noqa: E402
from stock_selector.data.sina import parse_sina_record  # noqa: E402
from stock_selector.reports.screen_report import write_screen_outputs  # noqa: E402
from stock_selector.screening.momentum_liquidity import ScreenConfig, screen_quotes  # noqa: E402


def quote(
    code: str,
    name: str,
    pct: float,
    amount: float,
    turnover: float,
    flow_pct: float,
    flow_amount: float,
    amplitude: float = 8.0,
    price: float = 12.3,
):
    return parse_quote_record(
        {
            "f12": code,
            "f14": name,
            "f2": price,
            "f3": pct,
            "f5": 123456,
            "f6": amount,
            "f7": amplitude,
            "f8": turnover,
            "f9": 28.0,
            "f10": 1.3,
            "f15": price * 1.02,
            "f16": price * 0.98,
            "f17": price,
            "f18": price * 0.99,
            "f20": 5_000_000_000,
            "f21": 3_000_000_000,
            "f23": 2.1,
            "f62": flow_amount,
            "f184": flow_pct,
            "f124": 1781508873,
        }
    )


class AShareScreenTest(unittest.TestCase):
    def test_parse_quote_record_maps_fields(self):
        item = quote("300001", "测试科技", 3.2, 500_000_000, 4.5, 6.5, 80_000_000)
        self.assertEqual(item.code, "300001")
        self.assertEqual(item.exchange, "SZ")
        self.assertEqual(item.board, "CHINEXT")
        self.assertEqual(item.latest_price, 12.3)
        self.assertTrue(item.quote_time)

    def test_parse_sina_record_maps_fields_without_flow(self):
        item = parse_sina_record(
            {
                "symbol": "sh600000",
                "code": "600000",
                "name": "浦发银行",
                "trade": "9.530",
                "changepercent": -1.45,
                "settlement": "9.670",
                "open": "9.680",
                "high": "9.720",
                "low": "9.470",
                "volume": 87932132,
                "amount": 842270434.0,
                "ticktime": "15:00:03",
                "per": 6.31,
                "pb": 0.42,
                "mktcap": 3174050.0,
                "nmc": 3174050.0,
                "turnoverratio": 0.26,
            }
        )
        self.assertEqual(item.exchange, "SH")
        self.assertEqual(item.board, "SH_MAIN")
        self.assertEqual(item.amount, 842270434.0)
        self.assertIsNone(item.main_net_inflow)
        self.assertGreater(item.amplitude or 0, 0)

    def test_screen_quotes_filters_and_ranks(self):
        quotes = [
            quote("600001", "强势制造", 4.2, 1_200_000_000, 5.2, 9.1, 160_000_000),
            quote("000002", "弱流动性", 2.2, 50_000_000, 1.2, 4.0, 20_000_000),
            quote("300003", "高振幅", 3.0, 600_000_000, 4.0, 5.0, 50_000_000, amplitude=25.0),
            quote("600004", "ST测试", 2.5, 700_000_000, 3.0, 7.0, 90_000_000),
        ]
        result = screen_quotes(quotes, ScreenConfig(top_n=3))
        self.assertEqual(result.total_quotes, 4)
        self.assertEqual(result.accepted_before_top_n, 1)
        self.assertEqual(result.candidates[0].quote.code, "600001")
        self.assertIn("amount_too_low", result.rejection_counts)
        self.assertIn("amplitude_too_high", result.rejection_counts)
        self.assertIn("excluded_name", result.rejection_counts)

    def test_write_screen_outputs(self):
        with tempfile.TemporaryDirectory(prefix="screen_report_") as td:
            root = Path(td)
            quotes = [
                quote("600001", "强势制造", 4.2, 1_200_000_000, 5.2, 9.1, 160_000_000),
                quote("000002", "平稳消费", 1.8, 500_000_000, 2.1, 3.5, 30_000_000),
            ]
            result = screen_quotes(quotes, ScreenConfig(top_n=2))
            paths = write_screen_outputs(
                run_id="20260102_093000_test",
                quotes=quotes,
                result=result,
                metadata={"source_name": "fixture", "reported_total": 2, "fetched_at": "2026-01-02T09:30:00+08:00"},
                output_root=root / "outputs",
                raw_root=root / "raw",
            )
            self.assertTrue(paths.report_html.is_file())
            self.assertTrue(paths.latest_html.is_file())
            self.assertTrue(paths.raw_csv.is_file())
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["result"]["total_quotes"], 2)


if __name__ == "__main__":
    unittest.main()
