from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.data.eastmoney import fetch_a_share_quotes  # noqa: E402
from stock_selector.data.sina import fetch_sina_a_share_quotes  # noqa: E402
from stock_selector.reports.screen_report import write_screen_outputs  # noqa: E402
from stock_selector.screening.momentum_liquidity import ScreenConfig, screen_quotes  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用真实 A 股行情快照生成第一条选股业务闭环结果。")
    parser.add_argument("--top", type=int, default=30, help="输出候选股票数量。")
    parser.add_argument("--min-amount", type=float, default=200_000_000.0, help="最低成交额，单位元。")
    parser.add_argument("--min-turnover-rate", type=float, default=0.8, help="最低换手率百分比。")
    parser.add_argument("--min-pct-change", type=float, default=-3.0, help="最低涨跌幅百分比。")
    parser.add_argument("--max-pct-change", type=float, default=9.8, help="最高涨跌幅百分比，默认避开接近涨停的极端票。")
    parser.add_argument("--max-amplitude", type=float, default=18.0, help="最高振幅百分比。")
    parser.add_argument("--page-size", type=int, default=100, help="行情接口分页大小；新浪源单页上限按 100 处理。")
    parser.add_argument("--timeout", type=float, default=20.0, help="单次 HTTP 超时时间。")
    parser.add_argument("--source", choices=["auto", "eastmoney", "sina"], default="sina", help="真实行情源。sina 为默认稳定源；auto 会先试东财，失败后回退到新浪。")
    parser.add_argument("--output-root", default=str(ROOT / "outputs" / "a_share_screen"))
    parser.add_argument("--raw-root", default=str(ROOT / "data" / "raw" / "a_share_quotes"))
    return parser.parse_args(argv)


def fetch_quotes(source: str, page_size: int, timeout: float):
    if source == "eastmoney":
        quotes, metadata = fetch_a_share_quotes(page_size=page_size, timeout=timeout)
        metadata["provider"] = "eastmoney"
        return quotes, metadata
    if source == "sina":
        quotes, metadata = fetch_sina_a_share_quotes(page_size=min(page_size, 100), timeout=timeout)
        metadata["provider"] = "sina"
        return quotes, metadata
    try:
        quotes, metadata = fetch_a_share_quotes(page_size=page_size, timeout=timeout)
        metadata["provider"] = "eastmoney"
        return quotes, metadata
    except Exception as exc:
        quotes, metadata = fetch_sina_a_share_quotes(page_size=100, timeout=timeout)
        metadata["provider"] = "sina"
        metadata["fallback_from"] = "eastmoney"
        metadata["fallback_error"] = f"{type(exc).__name__}: {exc}"
        return quotes, metadata


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    quotes, metadata = fetch_quotes(args.source, args.page_size, args.timeout)
    config = ScreenConfig(
        top_n=args.top,
        min_amount=args.min_amount,
        min_turnover_rate=args.min_turnover_rate,
        min_pct_change=args.min_pct_change,
        max_pct_change=args.max_pct_change,
        max_amplitude=args.max_amplitude,
    )
    result = screen_quotes(quotes, config)
    run_id = datetime.now().strftime(f"%Y%m%d_%H%M%S_{metadata.get('provider', 'quote')}_snapshot")
    paths = write_screen_outputs(
        run_id=run_id,
        quotes=quotes,
        result=result,
        metadata=metadata,
        output_root=Path(args.output_root),
        raw_root=Path(args.raw_root),
    )
    summary = {
        "run_id": run_id,
        "quotes": len(quotes),
        "accepted_before_top_n": result.accepted_before_top_n,
        "candidates": len(result.candidates),
        "top": [
            {
                "rank": item.rank,
                "code": item.quote.code,
                "name": item.quote.name,
                "score": item.score,
                "pct_change": item.quote.pct_change,
                "amount": item.quote.amount,
                "main_net_inflow_pct": item.quote.main_net_inflow_pct,
            }
            for item in result.candidates[:5]
        ],
        "report_html": str(paths.report_html),
        "latest_html": str(paths.latest_html),
        "candidates_csv": str(paths.candidates_csv),
        "raw_csv": str(paths.raw_csv),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
