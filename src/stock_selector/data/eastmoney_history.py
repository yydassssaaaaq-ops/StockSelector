from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stock_selector.data.eastmoney import classify_board, classify_exchange, to_float, to_int
from stock_selector.data.models import DailyBar, DataFetchFailure, HistoricalSeries


EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
ADJUSTMENT_TO_FQT = {
    "none": "0",
    "qfq": "1",
    "hfq": "2",
}
SOURCE_NAME = "Eastmoney push2his daily kline"


class HistoricalDataError(RuntimeError):
    """Raised when public historical daily data cannot be fetched or parsed."""


def normalize_adjustment(adjustment: str) -> str:
    normalized = adjustment.lower().strip()
    if normalized in ("front", "forward", "pre", "前复权"):
        normalized = "qfq"
    if normalized not in ADJUSTMENT_TO_FQT:
        raise ValueError(f"unsupported adjustment: {adjustment}")
    return normalized


def secid_for_code(code: str, exchange: str | None = None) -> str:
    exchange = (exchange or classify_exchange(code)).upper()
    if exchange == "SH":
        return f"1.{code}"
    return f"0.{code}"


def build_kline_url(
    *,
    secid: str,
    start_date: str,
    end_date: str,
    adjustment: str,
    period: str = "101",
) -> str:
    adjustment = normalize_adjustment(adjustment)
    params = {
        "secid": secid,
        "fields1": KLINE_FIELDS1,
        "fields2": KLINE_FIELDS2,
        "klt": period,
        "fqt": ADJUSTMENT_TO_FQT[adjustment],
        "beg": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
    }
    return EASTMONEY_KLINE_URL + "?" + urllib.parse.urlencode(params)


def load_json_url(url: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StockSelector/0.1 (+minimal historical backtest)",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HistoricalDataError(f"Eastmoney kline response is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HistoricalDataError("Eastmoney kline response root is not an object")
    return data


def cache_file(cache_root: Path, code: str, start_date: str, end_date: str, adjustment: str) -> Path:
    safe_code = re.sub(r"[^0-9A-Za-z_.-]", "_", code)
    safe_start = start_date.replace("-", "")
    safe_end = end_date.replace("-", "")
    return cache_root / "eastmoney" / f"{safe_code}_{normalize_adjustment(adjustment)}_{safe_start}_{safe_end}.json"


def parse_kline_row(
    row: str,
    *,
    code: str,
    name: str,
    exchange: str,
    board: str,
    adjustment: str,
) -> DailyBar:
    fields = row.split(",")
    if len(fields) < 11:
        raise HistoricalDataError(f"malformed kline row for {code}: {row}")
    date = fields[0]
    open_price = to_float(fields[1])
    close_price = to_float(fields[2])
    high = to_float(fields[3])
    low = to_float(fields[4])
    volume = to_int(fields[5])
    amount = to_float(fields[6])
    amplitude = to_float(fields[7])
    pct_change = to_float(fields[8])
    change_amount = to_float(fields[9])
    turnover_rate = to_float(fields[10])
    required = {
        "open": open_price,
        "close": close_price,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        raise HistoricalDataError(f"missing {','.join(missing)} in kline row for {code} on {date}")
    if min(open_price or 0.0, close_price or 0.0, high or 0.0, low or 0.0) <= 0:
        raise HistoricalDataError(f"non-positive price in kline row for {code} on {date}")
    return DailyBar(
        code=code,
        name=name,
        exchange=exchange,
        board=board,
        date=date,
        open=open_price or 0.0,
        close=close_price or 0.0,
        high=high or 0.0,
        low=low or 0.0,
        volume=volume or 0,
        amount=amount or 0.0,
        amplitude=amplitude,
        pct_change=pct_change,
        change_amount=change_amount,
        turnover_rate=turnover_rate,
        adjustment=adjustment,
        source=SOURCE_NAME,
    )


def parse_kline_payload(
    payload: dict[str, Any],
    *,
    code: str,
    name: str,
    exchange: str,
    board: str,
    adjustment: str,
) -> list[DailyBar]:
    if payload.get("rc") != 0:
        raise HistoricalDataError(f"Eastmoney kline returned rc={payload.get('rc')}: {payload.get('rt')}")
    body = payload.get("data")
    if not isinstance(body, dict):
        raise HistoricalDataError(f"Eastmoney kline data is missing for {code}")
    rows = body.get("klines") or []
    if not isinstance(rows, list):
        raise HistoricalDataError(f"Eastmoney kline rows are not a list for {code}")
    bars = [
        parse_kline_row(
            row,
            code=code,
            name=name,
            exchange=exchange,
            board=board,
            adjustment=adjustment,
        )
        for row in rows
        if isinstance(row, str)
    ]
    bars.sort(key=lambda item: item.date)
    return bars


def series_from_bars(
    *,
    code: str,
    name: str,
    exchange: str,
    board: str,
    adjustment: str,
    start_date: str,
    end_date: str,
    fetched_at: str,
    bars: list[DailyBar],
    cache_hit: bool,
) -> HistoricalSeries:
    completeness = {
        "requested_start": start_date,
        "requested_end": end_date,
        "returned_rows": len(bars),
        "first_date": bars[0].date if bars else None,
        "last_date": bars[-1].date if bars else None,
        "has_data": bool(bars),
    }
    if not bars:
        raise HistoricalDataError(f"no historical bars returned for {code}")
    return HistoricalSeries(
        code=code,
        name=name,
        exchange=exchange,
        board=board,
        source=SOURCE_NAME,
        adjustment=adjustment,
        requested_start=start_date,
        requested_end=end_date,
        fetched_at=fetched_at,
        bars=bars,
        cache_hit=cache_hit,
        completeness=completeness,
    )


def fetch_historical_series(
    *,
    code: str,
    name: str = "",
    exchange: str | None = None,
    board: str | None = None,
    start_date: str,
    end_date: str,
    adjustment: str = "qfq",
    cache_root: Path,
    timeout: float = 20.0,
    retries: int = 2,
    retry_sleep_seconds: float = 0.5,
    loader: Callable[[str, float], dict[str, Any]] = load_json_url,
) -> HistoricalSeries:
    adjustment = normalize_adjustment(adjustment)
    exchange = exchange or classify_exchange(code)
    board = board or classify_board(code)
    cached = cache_file(cache_root, code, start_date, end_date, adjustment)
    if cached.is_file():
        data = json.loads(cached.read_text(encoding="utf-8"))
        bars = parse_kline_payload(
            data["payload"],
            code=code,
            name=name or data.get("name") or code,
            exchange=exchange,
            board=board,
            adjustment=adjustment,
        )
        return series_from_bars(
            code=code,
            name=name or data.get("name") or code,
            exchange=exchange,
            board=board,
            adjustment=adjustment,
            start_date=start_date,
            end_date=end_date,
            fetched_at=data.get("fetched_at") or "",
            bars=bars,
            cache_hit=True,
        )

    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    url = build_kline_url(
        secid=secid_for_code(code, exchange),
        start_date=start_date,
        end_date=end_date,
        adjustment=adjustment,
    )
    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    for attempt in range(retries + 1):
        try:
            payload = loader(url, timeout)
            break
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_sleep_seconds * (attempt + 1))
    if payload is None:
        raise HistoricalDataError(f"Eastmoney kline request failed for {code}: {last_error}") from last_error
    bars = parse_kline_payload(
        payload,
        code=code,
        name=name or code,
        exchange=exchange,
        board=board,
        adjustment=adjustment,
    )
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(
        json.dumps(
            {
                "source": SOURCE_NAME,
                "source_url": EASTMONEY_KLINE_URL,
                "request_url": url,
                "code": code,
                "name": name,
                "exchange": exchange,
                "board": board,
                "adjustment": adjustment,
                "fqt": ADJUSTMENT_TO_FQT[adjustment],
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
    return series_from_bars(
        code=code,
        name=name or code,
        exchange=exchange,
        board=board,
        adjustment=adjustment,
        start_date=start_date,
        end_date=end_date,
        fetched_at=fetched_at,
        bars=bars,
        cache_hit=False,
    )


def fetch_many_historical_series(
    symbols: list[dict[str, str]],
    *,
    start_date: str,
    end_date: str,
    adjustment: str,
    cache_root: Path,
    timeout: float = 20.0,
    retries: int = 2,
) -> tuple[dict[str, HistoricalSeries], list[DataFetchFailure]]:
    series_by_code: dict[str, HistoricalSeries] = {}
    failures: list[DataFetchFailure] = []
    for symbol in symbols:
        code = symbol.get("code", "")
        name = symbol.get("name", "")
        try:
            series_by_code[code] = fetch_historical_series(
                code=code,
                name=name,
                exchange=symbol.get("exchange") or None,
                board=symbol.get("board") or None,
                start_date=start_date,
                end_date=end_date,
                adjustment=adjustment,
                cache_root=cache_root,
                timeout=timeout,
                retries=retries,
            )
        except Exception as exc:
            failures.append(
                DataFetchFailure(
                    code=code,
                    name=name,
                    source=SOURCE_NAME,
                    requested_start=start_date,
                    requested_end=end_date,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return series_by_code, failures


def fetch_benchmark_series(
    *,
    code: str = "000300",
    name: str = "沪深300",
    start_date: str,
    end_date: str,
    cache_root: Path,
    timeout: float = 20.0,
    retries: int = 2,
) -> HistoricalSeries:
    return fetch_historical_series(
        code=code,
        name=name,
        exchange="SH",
        board="INDEX",
        start_date=start_date,
        end_date=end_date,
        adjustment="none",
        cache_root=cache_root,
        timeout=timeout,
        retries=retries,
    )
