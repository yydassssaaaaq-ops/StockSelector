from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from stock_selector.data.models import DailyBar


@dataclass(frozen=True)
class ExecutionOutcome:
    code: str
    planned_entry_date: str
    planned_exit_date: str
    entry_date: str | None
    exit_date: str | None
    entry_price: float | None
    exit_price: float | None
    gross_return: float | None
    entry_status: str
    exit_status: str
    notes: list[str]

    @property
    def is_executed(self) -> bool:
        return self.gross_return is not None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def previous_close(bar: DailyBar) -> float | None:
    if bar.pct_change in (None, -100.0):
        return None
    denominator = 1.0 + bar.pct_change / 100.0
    if denominator <= 0:
        return None
    value = bar.close / denominator
    return value if value > 0 else None


def board_limit_rate(board: str, name: str = "") -> float:
    upper_name = name.upper()
    if "ST" in upper_name or "*ST" in upper_name:
        return 0.05
    board_upper = board.upper()
    if board_upper in {"STAR", "CHINEXT"}:
        return 0.20
    if board_upper == "BSE":
        return 0.30
    return 0.10


def price_for_timing(bar: DailyBar, timing: str) -> float:
    if timing == "next_open":
        return bar.open
    if timing == "next_close":
        return bar.close
    raise ValueError(f"unsupported execution timing: {timing}")


def open_return(bar: DailyBar) -> float | None:
    prev = previous_close(bar)
    if prev is None:
        return None
    return bar.open / prev - 1.0


def is_probable_limit_up_at_open(bar: DailyBar, *, tolerance: float = 0.002) -> bool:
    value = open_return(bar)
    if value is None:
        return False
    return value >= board_limit_rate(bar.board, bar.name) - tolerance


def is_probable_limit_down_at_open(bar: DailyBar, *, tolerance: float = 0.002) -> bool:
    value = open_return(bar)
    if value is None:
        return False
    return value <= -board_limit_rate(bar.board, bar.name) + tolerance


def validate_entry_bar(bar: DailyBar, timing: str) -> tuple[bool, str]:
    price = price_for_timing(bar, timing)
    if price <= 0:
        return False, "missing_or_non_positive_entry_price"
    if bar.volume <= 0:
        return False, "zero_volume_entry_bar"
    if timing == "next_open" and is_probable_limit_up_at_open(bar):
        return False, "probable_limit_up_entry_blocked"
    return True, "entry_filled"


def validate_exit_bar(bar: DailyBar, timing: str) -> tuple[bool, str]:
    price = price_for_timing(bar, timing)
    if price <= 0:
        return False, "missing_or_non_positive_exit_price"
    if bar.volume <= 0:
        return False, "zero_volume_exit_bar"
    if timing == "next_open" and is_probable_limit_down_at_open(bar):
        return False, "probable_limit_down_exit_blocked"
    return True, "exit_filled"


def _candidate_exit_dates(sorted_dates: list[str], planned_exit_date: str, max_exit_delay_days: int) -> list[str]:
    dates = [item for item in sorted_dates if item >= planned_exit_date]
    return dates[: max_exit_delay_days + 1]


def execute_holding_return(
    *,
    code: str,
    series_map: dict[str, DailyBar],
    planned_entry_date: str,
    planned_exit_date: str,
    timing: str = "next_open",
    max_exit_delay_days: int = 5,
) -> ExecutionOutcome:
    notes: list[str] = []
    entry_bar = series_map.get(planned_entry_date)
    if entry_bar is None:
        return ExecutionOutcome(
            code=code,
            planned_entry_date=planned_entry_date,
            planned_exit_date=planned_exit_date,
            entry_date=None,
            exit_date=None,
            entry_price=None,
            exit_price=None,
            gross_return=None,
            entry_status="missing_entry_bar",
            exit_status="not_attempted",
            notes=["planned entry date has no bar"],
        )
    entry_ok, entry_status = validate_entry_bar(entry_bar, timing)
    if not entry_ok:
        return ExecutionOutcome(
            code=code,
            planned_entry_date=planned_entry_date,
            planned_exit_date=planned_exit_date,
            entry_date=None,
            exit_date=None,
            entry_price=None,
            exit_price=None,
            gross_return=None,
            entry_status=entry_status,
            exit_status="not_attempted",
            notes=["entry blocked by daily-bar tradability approximation"],
        )

    sorted_dates = sorted(series_map)
    exit_bar: DailyBar | None = None
    exit_status = "missing_exit_bar"
    exit_date: str | None = None
    for candidate_date in _candidate_exit_dates(sorted_dates, planned_exit_date, max_exit_delay_days):
        candidate_bar = series_map.get(candidate_date)
        if candidate_bar is None:
            continue
        exit_ok, status = validate_exit_bar(candidate_bar, timing)
        if exit_ok:
            exit_bar = candidate_bar
            exit_status = status
            exit_date = candidate_date
            if candidate_date != planned_exit_date:
                notes.append(f"exit_delayed_from={planned_exit_date}")
            break
        exit_status = status
        notes.append(f"{candidate_date}:{status}")

    if exit_bar is None or exit_date is None:
        return ExecutionOutcome(
            code=code,
            planned_entry_date=planned_entry_date,
            planned_exit_date=planned_exit_date,
            entry_date=planned_entry_date,
            exit_date=None,
            entry_price=price_for_timing(entry_bar, timing),
            exit_price=None,
            gross_return=None,
            entry_status=entry_status,
            exit_status=exit_status,
            notes=notes or ["planned exit date has no tradable bar"],
        )

    entry_price = price_for_timing(entry_bar, timing)
    exit_price = price_for_timing(exit_bar, timing)
    return ExecutionOutcome(
        code=code,
        planned_entry_date=planned_entry_date,
        planned_exit_date=planned_exit_date,
        entry_date=planned_entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        gross_return=exit_price / entry_price - 1.0,
        entry_status=entry_status,
        exit_status=exit_status,
        notes=notes,
    )
