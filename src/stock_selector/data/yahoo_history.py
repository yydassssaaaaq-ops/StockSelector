from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stock_selector.data.models import DailyBar, HistoricalSeries


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
SOURCE_NAME = "Yahoo Finance chart index daily"


class YahooHistoryError(RuntimeError):
    """Raised when Yahoo chart data cannot be fetched or parsed."""


def unix_seconds(day: str, *, include_end: bool = False) -> int:
    parsed = date.fromisoformat(day)
    if include_end:
        parsed = date.fromordinal(parsed.toordinal() + 1)
    return int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc).timestamp())


def build_chart_url(symbol: str, start_date: str, end_date: str) -> str:
    params = {
        "period1": unix_seconds(start_date),
        "period2": unix_seconds(end_date, include_end=True),
        "interval": "1d",
        "events": "history",
    }
    return f"{YAHOO_CHART_URL}/{urllib.parse.quote(symbol)}?" + urllib.parse.urlencode(params)


def load_json_url(url: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockSelector/0.1",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise YahooHistoryError(f"Yahoo chart response is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise YahooHistoryError("Yahoo chart response root is not an object")
    return data


def cache_file(cache_root: Path, symbol: str, start_date: str, end_date: str) -> Path:
    safe_symbol = symbol.replace(".", "_")
    return cache_root / "yahoo" / f"{safe_symbol}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.json"


def parse_chart_payload(
    payload: dict[str, Any],
    *,
    code: str,
    name: str,
    symbol: str,
    start_date: str,
    end_date: str,
) -> list[DailyBar]:
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise YahooHistoryError("Yahoo chart field is missing")
    if chart.get("error"):
        raise YahooHistoryError(f"Yahoo chart returned error: {chart.get('error')}")
    result = chart.get("result") or []
    if not result or not isinstance(result[0], dict):
        raise YahooHistoryError(f"Yahoo chart returned no result for {symbol}")
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote_list = item.get("indicators", {}).get("quote") or []
    if not timestamps or not quote_list:
        raise YahooHistoryError(f"Yahoo chart returned no daily quote rows for {symbol}")
    quote = quote_list[0]
    opens = quote.get("open") or []
    closes = quote.get("close") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    volumes = quote.get("volume") or []
    bars: list[DailyBar] = []
    previous_close: float | None = None
    for index, stamp in enumerate(timestamps):
        trade_date = datetime.fromtimestamp(int(stamp), tz=timezone.utc).date().isoformat()
        if trade_date < start_date or trade_date > end_date:
            continue
        open_price = opens[index] if index < len(opens) else None
        close_price = closes[index] if index < len(closes) else None
        high = highs[index] if index < len(highs) else None
        low = lows[index] if index < len(lows) else None
        if None in (open_price, close_price, high, low) or min(open_price, close_price, high, low) <= 0:
            continue
        pct_change = None
        change_amount = None
        if previous_close and previous_close > 0:
            change_amount = close_price - previous_close
            pct_change = change_amount / previous_close * 100.0
        amplitude = (high - low) / previous_close * 100.0 if previous_close and previous_close > 0 else None
        bars.append(
            DailyBar(
                code=code,
                name=name,
                exchange="SH",
                board="INDEX",
                date=trade_date,
                open=float(open_price),
                close=float(close_price),
                high=float(high),
                low=float(low),
                volume=int(volumes[index] or 0) if index < len(volumes) else 0,
                amount=0.0,
                amplitude=amplitude,
                pct_change=pct_change,
                change_amount=change_amount,
                turnover_rate=None,
                adjustment="none",
                source=SOURCE_NAME,
            )
        )
        previous_close = float(close_price)
    bars.sort(key=lambda row: row.date)
    if not bars:
        raise YahooHistoryError(f"Yahoo chart returned no valid bars for {symbol}")
    return bars


def fetch_yahoo_index_series(
    *,
    symbol: str = "000300.SS",
    code: str = "000300",
    name: str = "沪深300",
    start_date: str,
    end_date: str,
    cache_root: Path,
    timeout: float = 20.0,
    retries: int = 2,
    loader: Callable[[str, float], dict[str, Any]] = load_json_url,
) -> HistoricalSeries:
    cached = cache_file(cache_root, symbol, start_date, end_date)
    if cached.is_file():
        data = json.loads(cached.read_text(encoding="utf-8"))
        bars = parse_chart_payload(
            data["payload"],
            code=code,
            name=name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        return HistoricalSeries(
            code=code,
            name=name,
            exchange="SH",
            board="INDEX",
            source=SOURCE_NAME,
            adjustment="none",
            requested_start=start_date,
            requested_end=end_date,
            fetched_at=data.get("fetched_at") or "",
            bars=bars,
            cache_hit=True,
            completeness={
                "requested_start": start_date,
                "requested_end": end_date,
                "returned_rows": len(bars),
                "first_date": bars[0].date,
                "last_date": bars[-1].date,
                "has_data": True,
                "symbol": symbol,
            },
        )

    url = build_chart_url(symbol, start_date, end_date)
    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    for attempt in range(retries + 1):
        try:
            payload = loader(url, timeout)
            break
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    if payload is None:
        raise YahooHistoryError(f"Yahoo chart request failed for {symbol}: {last_error}") from last_error
    bars = parse_chart_payload(
        payload,
        code=code,
        name=name,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(
        json.dumps(
            {
                "source": SOURCE_NAME,
                "request_url": url,
                "symbol": symbol,
                "code": code,
                "name": name,
                "requested_start": start_date,
                "requested_end": end_date,
                "fetched_at": fetched_at,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return HistoricalSeries(
        code=code,
        name=name,
        exchange="SH",
        board="INDEX",
        source=SOURCE_NAME,
        adjustment="none",
        requested_start=start_date,
        requested_end=end_date,
        fetched_at=fetched_at,
        bars=bars,
        cache_hit=False,
        completeness={
            "requested_start": start_date,
            "requested_end": end_date,
            "returned_rows": len(bars),
            "first_date": bars[0].date,
            "last_date": bars[-1].date,
            "has_data": True,
            "symbol": symbol,
        },
    )
