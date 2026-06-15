from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stock_selector.data.eastmoney import classify_board, classify_exchange, to_float, to_int
from stock_selector.data.models import DailyBar, DataFetchFailure, HistoricalSeries


TENCENT_FQKLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SOURCE_NAME = "Tencent qfq daily kline"


class TencentHistoryError(RuntimeError):
    """Raised when Tencent historical daily data cannot be fetched or parsed."""


def symbol_for_code(code: str, exchange: str | None = None) -> str:
    exchange = (exchange or classify_exchange(code)).upper()
    prefix = "sh" if exchange == "SH" else "sz"
    return f"{prefix}{code}"


def normalize_adjustment(adjustment: str) -> str:
    normalized = adjustment.lower().strip()
    if normalized in ("front", "forward", "pre", "前复权"):
        normalized = "qfq"
    if normalized not in {"qfq", "hfq", "none"}:
        raise ValueError(f"unsupported Tencent adjustment: {adjustment}")
    return normalized


def build_kline_url(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    adjustment: str,
    max_rows: int = 640,
) -> str:
    adjustment = normalize_adjustment(adjustment)
    start = start_date.replace("-", "-")
    end = end_date.replace("-", "-")
    parts = [symbol, "day", start, end, str(max_rows)]
    if adjustment in {"qfq", "hfq"}:
        parts.append(adjustment)
    params = {"param": ",".join(parts)}
    return TENCENT_FQKLINE_URL + "?" + urllib.parse.urlencode(params)


def row_key(adjustment: str) -> str:
    adjustment = normalize_adjustment(adjustment)
    if adjustment == "qfq":
        return "qfqday"
    if adjustment == "hfq":
        return "hfqday"
    return "day"


def load_json_url(url: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 StockSelector/0.1",
            "Referer": "https://gu.qq.com/",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TencentHistoryError(f"Tencent kline response is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TencentHistoryError("Tencent kline response root is not an object")
    return data


def cache_file(cache_root: Path, code: str, start_date: str, end_date: str, adjustment: str) -> Path:
    return cache_root / "tencent" / f"{code}_{normalize_adjustment(adjustment)}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.json"


def parse_rows(
    payload: dict[str, Any],
    *,
    code: str,
    name: str,
    exchange: str,
    board: str,
    adjustment: str,
    start_date: str,
    end_date: str,
) -> list[DailyBar]:
    if payload.get("code") not in (0, "0", None):
        raise TencentHistoryError(f"Tencent kline returned code={payload.get('code')}: {payload.get('msg')}")
    symbol = symbol_for_code(code, exchange)
    data = payload.get("data") or {}
    body = data.get(symbol) if isinstance(data, dict) else None
    if not isinstance(body, dict):
        raise TencentHistoryError(f"Tencent kline data is missing for {symbol}")
    rows = body.get(row_key(adjustment)) or body.get("day") or []
    if not isinstance(rows, list):
        raise TencentHistoryError(f"Tencent kline rows are not a list for {symbol}")
    bars: list[DailyBar] = []
    previous_close: float | None = None
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        trade_date = str(row[0])
        if trade_date < start_date or trade_date > end_date:
            continue
        open_price = to_float(row[1])
        close_price = to_float(row[2])
        high = to_float(row[3])
        low = to_float(row[4])
        volume_hands = to_int(row[5])
        if None in (open_price, close_price, high, low, volume_hands):
            raise TencentHistoryError(f"missing required price/volume field for {code} on {trade_date}")
        if min(open_price or 0.0, close_price or 0.0, high or 0.0, low or 0.0) <= 0:
            raise TencentHistoryError(f"non-positive price for {code} on {trade_date}")
        amount = float(volume_hands or 0) * 100.0 * float(close_price or 0.0)
        pct_change = None
        change_amount = None
        amplitude = None
        if previous_close and previous_close > 0:
            change_amount = float(close_price or 0.0) - previous_close
            pct_change = change_amount / previous_close * 100.0
            amplitude = (float(high or 0.0) - float(low or 0.0)) / previous_close * 100.0
        bars.append(
            DailyBar(
                code=code,
                name=name,
                exchange=exchange,
                board=board,
                date=trade_date,
                open=float(open_price or 0.0),
                close=float(close_price or 0.0),
                high=float(high or 0.0),
                low=float(low or 0.0),
                volume=int(volume_hands or 0),
                amount=amount,
                amplitude=amplitude,
                pct_change=pct_change,
                change_amount=change_amount,
                turnover_rate=None,
                adjustment=normalize_adjustment(adjustment),
                source=SOURCE_NAME,
            )
        )
        previous_close = float(close_price or 0.0)
    bars.sort(key=lambda item: item.date)
    if not bars:
        raise TencentHistoryError(f"no Tencent bars returned for {code}")
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
    return HistoricalSeries(
        code=code,
        name=name,
        exchange=exchange,
        board=board,
        source=SOURCE_NAME,
        adjustment=normalize_adjustment(adjustment),
        requested_start=start_date,
        requested_end=end_date,
        fetched_at=fetched_at,
        bars=bars,
        cache_hit=cache_hit,
        completeness={
            "requested_start": start_date,
            "requested_end": end_date,
            "returned_rows": len(bars),
            "first_date": bars[0].date if bars else None,
            "last_date": bars[-1].date if bars else None,
            "has_data": bool(bars),
            "amount_derivation": "volume_hands * 100 * close; turnover_rate is not provided",
        },
    )


def fetch_tencent_series(
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
    loader: Callable[[str, float], dict[str, Any]] = load_json_url,
) -> HistoricalSeries:
    adjustment = normalize_adjustment(adjustment)
    exchange = exchange or classify_exchange(code)
    board = board or classify_board(code)
    cached = cache_file(cache_root, code, start_date, end_date, adjustment)
    if cached.is_file():
        data = json.loads(cached.read_text(encoding="utf-8"))
        bars = parse_rows(
            data["payload"],
            code=code,
            name=name or data.get("name") or code,
            exchange=exchange,
            board=board,
            adjustment=adjustment,
            start_date=start_date,
            end_date=end_date,
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

    url = build_kline_url(
        symbol=symbol_for_code(code, exchange),
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
                time.sleep(0.5 * (attempt + 1))
    if payload is None:
        raise TencentHistoryError(f"Tencent kline request failed for {code}: {last_error}") from last_error
    bars = parse_rows(
        payload,
        code=code,
        name=name or code,
        exchange=exchange,
        board=board,
        adjustment=adjustment,
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
                "code": code,
                "name": name,
                "exchange": exchange,
                "board": board,
                "adjustment": adjustment,
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


def fetch_many_tencent_series(
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
            series_by_code[code] = fetch_tencent_series(
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
