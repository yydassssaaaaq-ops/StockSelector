from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_FIELDS = [
    "f12",  # code
    "f14",  # name
    "f2",  # latest price
    "f3",  # pct change
    "f5",  # volume
    "f6",  # amount
    "f7",  # amplitude
    "f8",  # turnover rate
    "f9",  # PE TTM
    "f10",  # volume ratio
    "f15",  # high
    "f16",  # low
    "f17",  # open
    "f18",  # previous close
    "f20",  # total market cap
    "f21",  # float market cap
    "f23",  # PB
    "f62",  # main net inflow
    "f184",  # main net inflow pct
    "f124",  # quote timestamp
]
DEFAULT_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"


class EastmoneyDataError(RuntimeError):
    """Raised when the Eastmoney snapshot endpoint is unavailable or malformed."""


@dataclass(frozen=True)
class AShareQuote:
    code: str
    name: str
    exchange: str
    board: str
    latest_price: float | None
    pct_change: float | None
    volume: int | None
    amount: float | None
    amplitude: float | None
    turnover_rate: float | None
    pe_ttm: float | None
    volume_ratio: float | None
    high: float | None
    low: float | None
    open: float | None
    previous_close: float | None
    total_market_cap: float | None
    float_market_cap: float | None
    pb: float | None
    main_net_inflow: float | None
    main_net_inflow_pct: float | None
    quote_time: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_float(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def quote_time(value: Any) -> str | None:
    number = to_int(value)
    if not number:
        return None
    return datetime.fromtimestamp(number, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def classify_exchange(code: str) -> str:
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8", "9")):
        return "BJ"
    return "UNKNOWN"


def classify_board(code: str) -> str:
    if code.startswith(("688", "689")):
        return "STAR"
    if code.startswith(("300", "301")):
        return "CHINEXT"
    if code.startswith(("4", "8")):
        return "BSE"
    if code.startswith("6"):
        return "SH_MAIN"
    if code.startswith(("0", "2")):
        return "SZ_MAIN"
    return "UNKNOWN"


def parse_quote_record(record: dict[str, Any]) -> AShareQuote:
    code = str(record.get("f12") or "").strip()
    name = str(record.get("f14") or "").strip()
    return AShareQuote(
        code=code,
        name=name,
        exchange=classify_exchange(code),
        board=classify_board(code),
        latest_price=to_float(record.get("f2")),
        pct_change=to_float(record.get("f3")),
        volume=to_int(record.get("f5")),
        amount=to_float(record.get("f6")),
        amplitude=to_float(record.get("f7")),
        turnover_rate=to_float(record.get("f8")),
        pe_ttm=to_float(record.get("f9")),
        volume_ratio=to_float(record.get("f10")),
        high=to_float(record.get("f15")),
        low=to_float(record.get("f16")),
        open=to_float(record.get("f17")),
        previous_close=to_float(record.get("f18")),
        total_market_cap=to_float(record.get("f20")),
        float_market_cap=to_float(record.get("f21")),
        pb=to_float(record.get("f23")),
        main_net_inflow=to_float(record.get("f62")),
        main_net_inflow_pct=to_float(record.get("f184")),
        quote_time=quote_time(record.get("f124")),
    )


def build_quote_url(page: int, page_size: int) -> str:
    params = {
        "pn": page,
        "pz": page_size,
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": DEFAULT_FS,
        "fields": ",".join(EASTMONEY_FIELDS),
    }
    return EASTMONEY_QUOTE_URL + "?" + urllib.parse.urlencode(params)


def load_json_url(url: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StockSelector/0.1 (+local research workflow)",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise EastmoneyDataError(f"Eastmoney response is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise EastmoneyDataError("Eastmoney response root is not an object")
    return data


def fetch_a_share_quotes(
    *,
    page_size: int = 2000,
    timeout: float = 20.0,
    retries: int = 2,
    sleep_seconds: float = 0.4,
) -> tuple[list[AShareQuote], dict[str, Any]]:
    """Fetch the current A-share quote snapshot from Eastmoney's quote endpoint."""

    quotes: list[AShareQuote] = []
    total: int | None = None
    page = 1
    pages_read = 0
    while total is None or len(quotes) < total:
        url = build_quote_url(page, page_size)
        last_error: Exception | None = None
        data: dict[str, Any] | None = None
        for attempt in range(retries + 1):
            try:
                data = load_json_url(url, timeout=timeout)
                break
            except Exception as exc:  # pragma: no cover - exercised by real run
                last_error = exc
                if attempt < retries:
                    time.sleep(sleep_seconds * (attempt + 1))
        if data is None:
            raise EastmoneyDataError(f"Eastmoney request failed for page {page}: {last_error}") from last_error
        if data.get("rc") != 0:
            raise EastmoneyDataError(f"Eastmoney returned rc={data.get('rc')}: {data}")
        body = data.get("data") or {}
        if not isinstance(body, dict):
            raise EastmoneyDataError("Eastmoney data field is not an object")
        raw_items = body.get("diff") or []
        if not isinstance(raw_items, list):
            raise EastmoneyDataError("Eastmoney diff field is not a list")
        total = int(body.get("total") or len(raw_items))
        quotes.extend(parse_quote_record(item) for item in raw_items if isinstance(item, dict))
        pages_read += 1
        if not raw_items:
            break
        page += 1
    metadata = {
        "source_name": "Eastmoney push2 A-share quote snapshot",
        "source_url": EASTMONEY_QUOTE_URL,
        "first_page_url": build_quote_url(1, page_size),
        "page_size": page_size,
        "pages_read": pages_read,
        "reported_total": total,
        "fetched_count": len(quotes),
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    return quotes[: total or len(quotes)], metadata
