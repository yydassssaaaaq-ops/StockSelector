from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from stock_selector.data.eastmoney import (
    AShareQuote,
    classify_board,
    classify_exchange,
    to_float,
    to_int,
)


SINA_MARKET_CENTER_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


class SinaDataError(RuntimeError):
    """Raised when Sina market center data cannot be fetched or parsed."""


def sina_market_url(page: int, page_size: int) -> str:
    params = {
        "page": page,
        "num": page_size,
        "sort": "changepercent",
        "asc": 0,
        "node": "hs_a",
        "symbol": "",
        "_s_r_a": "page",
    }
    return SINA_MARKET_CENTER_URL + "?" + urllib.parse.urlencode(params)


def load_sina_page(url: str, timeout: float = 20.0) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockSelector/0.1",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SinaDataError(f"Sina response is not JSON: {exc}") from exc
    if not isinstance(data, list):
        raise SinaDataError("Sina response root is not a list")
    return [item for item in data if isinstance(item, dict)]


def exchange_from_symbol(symbol: str, code: str) -> str:
    lower = symbol.lower()
    if lower.startswith("sh"):
        return "SH"
    if lower.startswith("sz"):
        return "SZ"
    if lower.startswith("bj"):
        return "BJ"
    return classify_exchange(code)


def quote_time_from_tick(ticktime: str | None, fetched_at: datetime) -> str | None:
    if not ticktime:
        return None
    return f"{fetched_at.date().isoformat()}T{ticktime}{fetched_at.astimezone().strftime('%z')[:3]}:{fetched_at.astimezone().strftime('%z')[3:]}"


def amplitude(high: float | None, low: float | None, previous_close: float | None) -> float | None:
    if high is None or low is None or previous_close in (None, 0):
        return None
    return round((high - low) / previous_close * 100.0, 3)


def parse_sina_record(record: dict[str, Any], fetched_at: datetime | None = None) -> AShareQuote:
    fetched_at = fetched_at or datetime.now().astimezone()
    code = str(record.get("code") or "").strip()
    symbol = str(record.get("symbol") or "").strip()
    exchange = exchange_from_symbol(symbol, code)
    latest = to_float(record.get("trade"))
    high = to_float(record.get("high"))
    low = to_float(record.get("low"))
    previous_close = to_float(record.get("settlement"))
    market_cap = to_float(record.get("mktcap"))
    float_market_cap = to_float(record.get("nmc"))
    return AShareQuote(
        code=code,
        name=str(record.get("name") or "").strip(),
        exchange=exchange,
        board=classify_board(code),
        latest_price=latest,
        pct_change=to_float(record.get("changepercent")),
        volume=to_int(record.get("volume")),
        amount=to_float(record.get("amount")),
        amplitude=amplitude(high, low, previous_close),
        turnover_rate=to_float(record.get("turnoverratio")),
        pe_ttm=to_float(record.get("per")),
        volume_ratio=None,
        high=high,
        low=low,
        open=to_float(record.get("open")),
        previous_close=previous_close,
        total_market_cap=market_cap * 10_000 if market_cap is not None else None,
        float_market_cap=float_market_cap * 10_000 if float_market_cap is not None else None,
        pb=to_float(record.get("pb")),
        main_net_inflow=None,
        main_net_inflow_pct=None,
        quote_time=quote_time_from_tick(str(record.get("ticktime") or ""), fetched_at),
    )


def fetch_sina_a_share_quotes(
    *,
    page_size: int = 100,
    timeout: float = 20.0,
    max_pages: int = 80,
    sleep_seconds: float = 0.15,
) -> tuple[list[AShareQuote], dict[str, Any]]:
    fetched_at = datetime.now().astimezone()
    quotes: list[AShareQuote] = []
    pages_read = 0
    seen_codes: set[str] = set()
    for page in range(1, max_pages + 1):
        url = sina_market_url(page, min(page_size, 100))
        rows = load_sina_page(url, timeout=timeout)
        pages_read += 1
        if not rows:
            break
        new_count = 0
        for row in rows:
            quote = parse_sina_record(row, fetched_at)
            if not quote.code or quote.code in seen_codes:
                continue
            seen_codes.add(quote.code)
            quotes.append(quote)
            new_count += 1
        if len(rows) < min(page_size, 100) or new_count == 0:
            break
        time.sleep(sleep_seconds)
    metadata = {
        "source_name": "Sina Market Center hs_a quote snapshot",
        "source_url": SINA_MARKET_CENTER_URL,
        "first_page_url": sina_market_url(1, min(page_size, 100)),
        "page_size": min(page_size, 100),
        "pages_read": pages_read,
        "reported_total": None,
        "fetched_count": len(quotes),
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "field_limitations": ["main_net_inflow and main_net_inflow_pct are not provided by this source"],
    }
    if not quotes:
        raise SinaDataError("Sina returned no A-share quotes")
    return quotes, metadata
