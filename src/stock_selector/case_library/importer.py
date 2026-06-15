from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEGACY_ROOT = Path("D:/AAAAAAAAA项目/L.Lawlight/1")
DEFAULT_DB = PROJECT_ROOT / "data" / "processed" / "case_library.sqlite3"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "case_library"
RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_[A-Za-z0-9_\-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STOCK_CODE_RE = re.compile(r"^\d{6}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def read_text(path: Path, limit: int | None = None) -> str:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        return handle.read(limit)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_json_load(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(read_text(path)), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in read_text(path).splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    except Exception:
        return rows
    return rows


def path_to_str(path: Path | None) -> str | None:
    return str(path.resolve()) if path else None


def normalize_path(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        return Path(value)
    except Exception:
        return None


def get_first(data: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in data and data[name] not in ("", None):
            return data[name]
    return None


def parse_human_dir_name(name: str) -> tuple[str | None, str | None, str | None]:
    parts = name.split("_")
    if len(parts) >= 3 and STOCK_CODE_RE.match(parts[0]) and DATE_RE.match(parts[-1]):
        return parts[0], "_".join(parts[1:-1]) or None, parts[-1]
    return None, None, None


def parse_run_time_from_id(run_id: str | None) -> tuple[str | None, str | None]:
    if not run_id:
        return None, None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(.+)$", run_id)
    if not m:
        return None, None
    run_time = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return run_time, m.group(7)


def trade_date_from_run(run_time: str | None, run_id: str | None, fallback: str | None) -> str | None:
    if run_time and len(run_time) >= 10 and DATE_RE.match(run_time[:10]):
        return run_time[:10]
    parsed, _ = parse_run_time_from_id(run_id)
    if parsed:
        return parsed[:10]
    return fallback


@dataclass
class CaseCandidate:
    case_id: str
    stock_code: str | None = None
    stock_name: str | None = None
    trade_date: str | None = None
    run_id: str | None = None
    run_time: str | None = None
    run_session: str | None = None
    data_cutoff_time: str | None = None
    quality: str | None = None
    radar_root: str | None = None
    humanview_root: str | None = None
    canonical_root: str | None = None
    sources: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def merge(self, other: "CaseCandidate") -> None:
        for key in [
            "stock_code", "stock_name", "trade_date", "run_id", "run_time",
            "run_session", "data_cutoff_time", "quality", "radar_root",
            "humanview_root", "canonical_root",
        ]:
            if not getattr(self, key) and getattr(other, key):
                setattr(self, key, getattr(other, key))
        self.sources.update(other.sources)
        self.warnings.extend(x for x in other.warnings if x not in self.warnings)
        self.raw.update({k: v for k, v in other.raw.items() if k not in self.raw})


def case_id_for(stock_code: str | None, run_id: str | None, trade_date: str | None) -> str:
    code = stock_code or "unknown"
    if run_id:
        return f"{code}:{run_id}"
    if trade_date:
        return f"{code}:{trade_date}:legacy"
    return f"{code}:missing-run"


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stocks (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            first_run_time TEXT,
            last_run_time TEXT,
            case_count INTEGER DEFAULT 0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            stock_code TEXT,
            stock_name TEXT,
            trade_date TEXT,
            run_id TEXT,
            run_time TEXT,
            run_session TEXT,
            data_cutoff_time TEXT,
            data_quality TEXT,
            data_sources_json TEXT,
            module_success INTEGER,
            module_failed INTEGER,
            module_empty INTEGER,
            has_humanview INTEGER,
            has_radardata INTEGER,
            has_charts INTEGER,
            has_intraday INTEGER,
            has_fund_flow INTEGER,
            radar_root TEXT,
            humanview_root TEXT,
            canonical_root TEXT,
            file_count INTEGER,
            field_coverage REAL,
            missing_json TEXT,
            warnings_json TEXT,
            json_summary TEXT,
            csv_preview TEXT,
            text_summary TEXT,
            html_entries TEXT,
            png_entries TEXT,
            structure_signature TEXT,
            duplicate_group TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            case_id TEXT,
            stock_code TEXT,
            source_root TEXT,
            file_type TEXT,
            role TEXT,
            size INTEGER,
            mtime REAL,
            sha256 TEXT,
            parse_status TEXT,
            error TEXT,
            duplicate_of TEXT,
            content_summary TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS modules (
            case_id TEXT,
            module_name TEXT,
            ok INTEGER,
            status TEXT,
            rows INTEGER,
            cols INTEGER,
            source_file TEXT,
            error TEXT,
            PRIMARY KEY (case_id, module_name, source_file)
        );
        CREATE TABLE IF NOT EXISTS import_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            case_id TEXT,
            kind TEXT,
            message TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS duplicates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT,
            path TEXT,
            duplicate_of TEXT,
            case_id TEXT,
            detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            legacy_root TEXT,
            summary_json TEXT
        );
        CREATE TABLE IF NOT EXISTS monitor_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 1,
            running INTEGER DEFAULT 0,
            last_heartbeat TEXT,
            last_event_time TEXT,
            last_import_time TEXT,
            last_error TEXT,
            debounce_seconds REAL,
            watched_roots_json TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS monitor_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT,
            event_type TEXT,
            path TEXT,
            old_path TEXT,
            size INTEGER,
            mtime REAL,
            sha256 TEXT,
            status TEXT,
            message TEXT,
            import_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS auto_import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            legacy_root TEXT,
            changed_count INTEGER,
            added_count INTEGER,
            modified_count INTEGER,
            deleted_count INTEGER,
            renamed_count INTEGER,
            duration_ms INTEGER,
            success INTEGER,
            summary_json TEXT,
            error TEXT
        );
        CREATE TABLE IF NOT EXISTS case_change_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER,
            created_at TEXT,
            case_id TEXT,
            stock_code TEXT,
            stock_name TEXT,
            change_type TEXT,
            before_json TEXT,
            after_json TEXT,
            changed_fields_json TEXT
        );
        """
    )
    ensure_column(conn, "files", "deleted_at", "TEXT")
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def discover_cases(legacy_root: Path) -> tuple[dict[str, CaseCandidate], dict[str, dict[str, Any]]]:
    cases: dict[str, CaseCandidate] = {}
    date_latest: dict[str, dict[str, Any]] = {}
    radar = legacy_root / "RadarData"
    human = legacy_root / "HumanView"

    def add(candidate: CaseCandidate) -> None:
        if candidate.case_id in cases:
            cases[candidate.case_id].merge(candidate)
        else:
            cases[candidate.case_id] = candidate

    for timeline in radar.glob("*/stock_timeline.json"):
        data, err = safe_json_load(timeline)
        if err or not isinstance(data, dict):
            continue
        stock_code = str(data.get("stock_code") or timeline.parent.name)
        stock_name = data.get("stock_name")
        for item in data.get("runs", []) if isinstance(data.get("runs"), list) else []:
            if not isinstance(item, dict):
                continue
            run_id = item.get("run_id")
            run_time = item.get("run_time")
            trade_date = trade_date_from_run(run_time, run_id, None)
            case_id = case_id_for(stock_code, run_id, trade_date)
            date_latest[f"{stock_code}:{trade_date}"] = item
            add(CaseCandidate(
                case_id=case_id,
                stock_code=stock_code,
                stock_name=stock_name,
                trade_date=trade_date,
                run_id=run_id,
                run_time=run_time,
                run_session=item.get("run_session"),
                data_cutoff_time=item.get("data_cutoff_time"),
                quality=item.get("data_quality_grade"),
                radar_root=item.get("run_root") or item.get("radar_root"),
                humanview_root=item.get("humanview_root"),
                canonical_root=item.get("run_root") or item.get("radar_root"),
                sources={"stock_timeline.json"},
                raw={"timeline_entry": item},
            ))

    for index in list(radar.glob("*/stock_runs_index.jsonl")) + list(radar.glob("*/*/runs_index.jsonl")):
        stock_code = index.parts[index.parts.index("RadarData") + 1] if "RadarData" in index.parts else None
        for item in parse_jsonl(index):
            run_id = item.get("run_id")
            run_time = item.get("run_time")
            trade_date = trade_date_from_run(run_time, run_id, None)
            case_id = case_id_for(stock_code, run_id, trade_date)
            date_latest[f"{stock_code}:{trade_date}"] = item
            add(CaseCandidate(
                case_id=case_id,
                stock_code=stock_code,
                trade_date=trade_date,
                run_id=run_id,
                run_time=run_time,
                run_session=item.get("run_session"),
                data_cutoff_time=item.get("data_cutoff_time"),
                quality=item.get("data_quality_grade"),
                radar_root=item.get("run_root") or item.get("radar_root"),
                humanview_root=item.get("humanview_root"),
                canonical_root=item.get("run_root") or item.get("radar_root"),
                sources={index.name},
                raw={"runs_index_entry": item},
            ))

    for run_dir in list(radar.glob("*/*/runs/*")) + list(human.glob("*/runs/*")):
        if not run_dir.is_dir() or not RUN_ID_RE.match(run_dir.name):
            continue
        run_id = run_dir.name
        parsed_time, session = parse_run_time_from_id(run_id)
        stock_code: str | None = None
        stock_name: str | None = None
        trade_date: str | None = None
        if "RadarData" in run_dir.parts:
            i = run_dir.parts.index("RadarData")
            stock_code = run_dir.parts[i + 1]
            trade_date = run_dir.parts[i + 2]
        elif "HumanView" in run_dir.parts:
            i = run_dir.parts.index("HumanView")
            stock_code, stock_name, trade_date = parse_human_dir_name(run_dir.parts[i + 1])
        case_id = case_id_for(stock_code, run_id, trade_date)
        add(CaseCandidate(
            case_id=case_id,
            stock_code=stock_code,
            stock_name=stock_name,
            trade_date=trade_date,
            run_id=run_id,
            run_time=parsed_time,
            run_session=session,
            radar_root=path_to_str(run_dir) if "RadarData" in run_dir.parts else None,
            humanview_root=path_to_str(run_dir) if "HumanView" in run_dir.parts else None,
            canonical_root=path_to_str(run_dir),
            sources={"run_directory"},
        ))

    # Legacy date-level cases: only create when no run index exists for the date.
    for date_dir in radar.glob("*/*"):
        if not date_dir.is_dir() or not DATE_RE.match(date_dir.name):
            continue
        stock_code = date_dir.parent.name
        has_runs = (date_dir / "runs").is_dir() and any((date_dir / "runs").iterdir())
        if has_runs:
            continue
        trade_date = date_dir.name
        case_id = case_id_for(stock_code, None, trade_date)
        add(CaseCandidate(
            case_id=case_id,
            stock_code=stock_code,
            trade_date=trade_date,
            radar_root=path_to_str(date_dir),
            canonical_root=path_to_str(date_dir),
            sources={"legacy_date_directory"},
        ))

    for view_dir in human.iterdir() if human.exists() else []:
        if not view_dir.is_dir():
            continue
        stock_code, stock_name, trade_date = parse_human_dir_name(view_dir.name)
        if not stock_code or not trade_date:
            continue
        has_runs = (view_dir / "runs").is_dir() and any((view_dir / "runs").iterdir())
        if has_runs:
            latest = date_latest.get(f"{stock_code}:{trade_date}", {})
            run_id = latest.get("run_id")
            case_id = case_id_for(stock_code, run_id, trade_date)
            add(CaseCandidate(
                case_id=case_id,
                stock_code=stock_code,
                stock_name=stock_name,
                trade_date=trade_date,
                run_id=run_id,
                run_time=latest.get("run_time"),
                run_session=latest.get("run_session"),
                humanview_root=path_to_str(view_dir / "runs" / run_id) if run_id else path_to_str(view_dir),
                canonical_root=path_to_str(view_dir / "runs" / run_id) if run_id else path_to_str(view_dir),
                sources={"humanview_latest_directory"},
                warnings=[] if run_id else ["HumanView date directory has runs but no latest run id was found."],
            ))
        else:
            case_id = case_id_for(stock_code, None, trade_date)
            add(CaseCandidate(
                case_id=case_id,
                stock_code=stock_code,
                stock_name=stock_name,
                trade_date=trade_date,
                humanview_root=path_to_str(view_dir),
                canonical_root=path_to_str(view_dir),
                sources={"legacy_humanview_directory"},
            ))

    return cases, date_latest


def build_date_latest(cases: dict[str, CaseCandidate]) -> dict[str, CaseCandidate]:
    latest: dict[str, CaseCandidate] = {}
    for case in cases.values():
        if not case.stock_code or not case.trade_date or not case.run_id:
            continue
        key = f"{case.stock_code}:{case.trade_date}"
        old = latest.get(key)
        if old is None or (case.run_time or "") > (old.run_time or ""):
            latest[key] = case
    return latest


def case_for_file(path: Path, legacy_root: Path, cases: dict[str, CaseCandidate], latest: dict[str, CaseCandidate]) -> tuple[str | None, str | None, str]:
    rel = path.relative_to(legacy_root)
    parts = rel.parts
    if parts[0] == "RadarData" and len(parts) >= 3:
        stock_code = parts[1]
        trade_date = parts[2] if DATE_RE.match(parts[2]) else None
        if "runs" in parts:
            idx = parts.index("runs")
            if idx + 1 < len(parts) and RUN_ID_RE.match(parts[idx + 1]):
                run_id = parts[idx + 1]
                return case_id_for(stock_code, run_id, trade_date), stock_code, "radar_run"
        if trade_date:
            candidate = latest.get(f"{stock_code}:{trade_date}")
            if candidate:
                return candidate.case_id, stock_code, "radar_latest_view"
            return case_id_for(stock_code, None, trade_date), stock_code, "radar_legacy_date"
        return None, stock_code, "radar_stock_meta"
    if parts[0] == "HumanView" and len(parts) >= 2:
        stock_code, _stock_name, trade_date = parse_human_dir_name(parts[1])
        if "runs" in parts:
            idx = parts.index("runs")
            if idx + 1 < len(parts) and RUN_ID_RE.match(parts[idx + 1]):
                return case_id_for(stock_code, parts[idx + 1], trade_date), stock_code, "human_run"
        if stock_code and trade_date:
            candidate = latest.get(f"{stock_code}:{trade_date}")
            if candidate:
                return candidate.case_id, stock_code, "human_latest_view"
            return case_id_for(stock_code, None, trade_date), stock_code, "human_legacy_date"
    return None, None, "unclassified"


def infer_file_role(path: Path) -> str:
    lower = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if lower in {"case_packet.json", "agent_case_packet.json", "case_packet.md"}:
        return "packet"
    if lower == "data_quality_report.json" or "quality" in parts:
        return "quality"
    if "raw" in parts:
        return "raw_machine_data"
    if "features" in parts:
        return "feature_machine_data"
    if "charts" in parts or path.suffix.lower() == ".png":
        return "chart"
    if "predict" in parts or "predict_links" in parts:
        return "prediction_or_link"
    if "observe" in parts:
        return "observation"
    if lower.endswith(".html"):
        return "human_html_report"
    if path.suffix.lower() in {".md", ".txt"}:
        return "human_text_report"
    if lower == "human_view_manifest.json":
        return "human_manifest"
    return "supporting_file"


def preview_csv(path: Path, rows: int = 6) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            sample = []
            for i, row in enumerate(reader):
                if i >= rows:
                    break
                sample.append(row[:12])
        return {"rows": sample, "truncated": True}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def summarize_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    data, err = safe_json_load(path)
    if err:
        return {}, [], err
    if isinstance(data, dict):
        summary: dict[str, Any] = {"top_keys": list(data.keys())[:40]}
        for key in ["股票代码", "股票名称", "日期标签", "数据可信等级", "run_id", "run_time", "run_session", "data_quality_grade", "summary_status"]:
            if key in data:
                summary[key] = data.get(key)
        modules = []
        raw_modules = data.get("模块状态")
        if isinstance(raw_modules, list):
            for item in raw_modules:
                if isinstance(item, dict):
                    modules.append(item)
        return summary, modules, None
    if isinstance(data, list):
        return {"list_length": len(data), "first_type": type(data[0]).__name__ if data else None}, [], None
    return {"json_type": type(data).__name__}, [], None


def summarize_file(path: Path) -> tuple[str, str | None, dict[str, Any], list[dict[str, Any]]]:
    ext = path.suffix.lower()
    role = infer_file_role(path)
    if ext == ".json":
        summary, modules, err = summarize_json(path)
        return ("error" if err else "ok"), err, summary, modules
    if ext == ".jsonl":
        rows = parse_jsonl(path)
        return "ok", None, {"jsonl_records": len(rows), "first_keys": list(rows[0].keys())[:20] if rows else []}, []
    if ext == ".csv":
        return "ok", None, preview_csv(path), []
    if ext in {".md", ".txt", ".log"}:
        try:
            text = read_text(path, limit=1600)
            return "ok", None, {"text_preview": text.strip()[:1200], "chars_sampled": len(text)}, []
        except Exception as exc:
            return "error", f"{type(exc).__name__}: {exc}", {}, []
    if ext == ".html":
        return "ok", None, {"title": path.name, "html_entry": str(path.resolve())}, []
    if ext == ".png":
        return "ok", None, {"image": str(path.resolve())}, []
    return "ok", None, {"role": role}, []


def upgrade_case_from_json(case: CaseCandidate, path: Path, summary: dict[str, Any]) -> None:
    if case.stock_code is None:
        value = summary.get("股票代码") or summary.get("stock_code")
        if value:
            case.stock_code = str(value)
    if case.stock_name is None:
        value = summary.get("股票名称") or summary.get("stock_name")
        if value:
            case.stock_name = str(value)
    if case.quality is None:
        value = summary.get("数据可信等级") or summary.get("data_quality_grade")
        if value:
            case.quality = str(value)
    if case.run_id is None and summary.get("run_id"):
        case.run_id = str(summary["run_id"])
    if case.run_time is None and summary.get("run_time"):
        case.run_time = str(summary["run_time"])


def upsert_file(
    conn: sqlite3.Connection,
    path: Path,
    case_id: str | None,
    stock_code: str | None,
    source_root: str,
    duplicate_of: str | None,
    summary: dict[str, Any],
    parse_status: str,
    error: str | None,
    counters: Counter,
) -> None:
    abs_path = str(path.resolve())
    stat = path.stat()
    old = conn.execute("SELECT size, mtime, sha256 FROM files WHERE path=?", (abs_path,)).fetchone()
    if old and old["size"] == stat.st_size and abs(float(old["mtime"]) - stat.st_mtime) < 0.0001:
        digest = old["sha256"]
        counters["unchanged_files"] += 1
    else:
        digest = sha256_file(path)
        if old:
            counters["updated_files"] += 1
        else:
            counters["new_files"] += 1
    conn.execute(
        """
        INSERT INTO files(path, case_id, stock_code, source_root, file_type, role, size, mtime, sha256,
                          parse_status, error, duplicate_of, content_summary, updated_at, deleted_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(path) DO UPDATE SET
            case_id=excluded.case_id, stock_code=excluded.stock_code, source_root=excluded.source_root,
            file_type=excluded.file_type, role=excluded.role, size=excluded.size, mtime=excluded.mtime,
            sha256=excluded.sha256, parse_status=excluded.parse_status, error=excluded.error,
            duplicate_of=excluded.duplicate_of, content_summary=excluded.content_summary,
            updated_at=excluded.updated_at, deleted_at=NULL
        """,
        (
            abs_path,
            case_id,
            stock_code,
            source_root,
            path.suffix.lower() or "unknown",
            infer_file_role(path),
            stat.st_size,
            stat.st_mtime,
            digest,
            parse_status,
            error,
            duplicate_of,
            json_dumps(summary),
            now_iso(),
            None,
        ),
    )


def recompute_cases(conn: sqlite3.Connection, cases: dict[str, CaseCandidate]) -> None:
    conn.execute("DELETE FROM modules")
    for case in cases.values():
        rows = conn.execute(
            "SELECT * FROM files WHERE case_id=? AND coalesce(parse_status,'')!='deleted'",
            (case.case_id,),
        ).fetchall()
        json_summaries: list[dict[str, Any]] = []
        csv_previews: list[dict[str, Any]] = []
        text_summaries: list[dict[str, Any]] = []
        html_entries: list[str] = []
        png_entries: list[str] = []
        modules: dict[str, dict[str, Any]] = {}
        data_sources: set[str] = set(case.sources)
        missing: list[str] = []
        warnings = list(case.warnings)
        structure_keys: set[str] = set()
        has_intraday = False
        has_fund_flow = False
        has_charts = False
        for row in rows:
            try:
                summary = json.loads(row["content_summary"] or "{}")
            except Exception:
                summary = {}
            role = row["role"] or ""
            path = row["path"]
            if row["parse_status"] == "error":
                warnings.append(f"无法解析：{path}：{row['error']}")
            if row["file_type"] == ".json":
                json_summaries.append({"path": path, **summary})
                structure_keys.update(summary.get("top_keys", []))
                if case.quality is None:
                    q = summary.get("数据可信等级") or summary.get("data_quality_grade")
                    if q:
                        case.quality = str(q)
                if case.stock_name is None:
                    n = summary.get("股票名称") or summary.get("stock_name")
                    if n:
                        case.stock_name = str(n)
            elif row["file_type"] == ".csv":
                csv_previews.append({"path": path, "role": role, **summary})
            elif row["file_type"] in {".md", ".txt", ".log"}:
                text_summaries.append({"path": path, "role": role, **summary})
            elif row["file_type"] == ".html":
                html_entries.append(path)
            elif row["file_type"] == ".png":
                png_entries.append(path)
            lower_path = path.lower()
            if "minute" in lower_path or "intraday" in lower_path or "分时" in path:
                has_intraday = True
            if "fund_flow" in lower_path or "资金流" in path:
                has_fund_flow = True
            if role == "chart" or row["file_type"] == ".png":
                has_charts = True
        for json_row in json_summaries:
            if "有效日K来源" in json_row:
                data_sources.add(str(json_row["有效日K来源"]))
        module_rows = conn.execute(
            "SELECT path, content_summary FROM files WHERE case_id=? AND file_type='.json' AND coalesce(parse_status,'')!='deleted'",
            (case.case_id,),
        ).fetchall()
        for row in module_rows:
            data, err = safe_json_load(Path(row["path"]))
            if err or not isinstance(data, dict):
                continue
            raw_modules = data.get("模块状态")
            if not isinstance(raw_modules, list):
                continue
            for item in raw_modules:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("模块") or "unknown")
                modules[name] = {
                    "name": name,
                    "ok": bool(item.get("ok")),
                    "status": item.get("status"),
                    "rows": item.get("rows"),
                    "cols": item.get("cols"),
                    "source_file": row["path"],
                    "error": item.get("error"),
                }
        for item in modules.values():
            conn.execute(
                "INSERT OR REPLACE INTO modules(case_id, module_name, ok, status, rows, cols, source_file, error) VALUES(?,?,?,?,?,?,?,?)",
                (case.case_id, item["name"], int(item["ok"]), item["status"], item["rows"], item["cols"], item["source_file"], item["error"]),
            )
        success = sum(1 for item in modules.values() if item["ok"])
        failed = sum(1 for item in modules.values() if not item["ok"])
        empty = 0
        if not rows:
            missing.append("no_files")
        if not any(row["source_root"] == "RadarData" for row in rows):
            missing.append("RadarData")
        if not any(row["source_root"] == "HumanView" for row in rows):
            missing.append("HumanView")
        if not html_entries:
            missing.append("html_report")
        if not png_entries:
            missing.append("png_chart")
        fields = [
            case.stock_code, case.stock_name, case.trade_date, case.run_id or case.trade_date,
            case.run_time or case.trade_date, case.quality, rows, modules, data_sources,
            html_entries or text_summaries, png_entries,
        ]
        coverage = round(sum(1 for item in fields if item) / len(fields), 4)
        structure_signature = hashlib.sha1("|".join(sorted(structure_keys)).encode("utf-8")).hexdigest() if structure_keys else None
        conn.execute(
            """
            INSERT INTO cases(case_id, stock_code, stock_name, trade_date, run_id, run_time, run_session,
                              data_cutoff_time, data_quality, data_sources_json, module_success, module_failed,
                              module_empty, has_humanview, has_radardata, has_charts, has_intraday, has_fund_flow,
                              radar_root, humanview_root, canonical_root, file_count, field_coverage, missing_json,
                              warnings_json, json_summary, csv_preview, text_summary, html_entries, png_entries,
                              structure_signature, duplicate_group, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(case_id) DO UPDATE SET
                stock_code=excluded.stock_code, stock_name=excluded.stock_name, trade_date=excluded.trade_date,
                run_id=excluded.run_id, run_time=excluded.run_time, run_session=excluded.run_session,
                data_cutoff_time=excluded.data_cutoff_time, data_quality=excluded.data_quality,
                data_sources_json=excluded.data_sources_json, module_success=excluded.module_success,
                module_failed=excluded.module_failed, module_empty=excluded.module_empty,
                has_humanview=excluded.has_humanview, has_radardata=excluded.has_radardata,
                has_charts=excluded.has_charts, has_intraday=excluded.has_intraday,
                has_fund_flow=excluded.has_fund_flow, radar_root=excluded.radar_root,
                humanview_root=excluded.humanview_root, canonical_root=excluded.canonical_root,
                file_count=excluded.file_count, field_coverage=excluded.field_coverage,
                missing_json=excluded.missing_json, warnings_json=excluded.warnings_json,
                json_summary=excluded.json_summary, csv_preview=excluded.csv_preview,
                text_summary=excluded.text_summary, html_entries=excluded.html_entries,
                png_entries=excluded.png_entries, structure_signature=excluded.structure_signature,
                duplicate_group=excluded.duplicate_group, updated_at=excluded.updated_at
            """,
            (
                case.case_id,
                case.stock_code,
                case.stock_name,
                case.trade_date,
                case.run_id,
                case.run_time,
                case.run_session,
                case.data_cutoff_time,
                case.quality or "unknown",
                json_dumps(sorted(data_sources)),
                success,
                failed,
                empty,
                int(any(row["source_root"] == "HumanView" for row in rows)),
                int(any(row["source_root"] == "RadarData" for row in rows)),
                int(has_charts),
                int(has_intraday),
                int(has_fund_flow),
                case.radar_root,
                case.humanview_root,
                case.canonical_root,
                len(rows),
                coverage,
                json_dumps(missing),
                json_dumps(warnings[:50]),
                json_dumps(json_summaries[:12]),
                json_dumps(csv_previews[:10]),
                json_dumps(text_summaries[:10]),
                json_dumps(html_entries),
                json_dumps(png_entries),
                structure_signature,
                None,
                now_iso(),
            ),
        )
    conn.execute("DELETE FROM stocks")
    for row in conn.execute(
        "SELECT stock_code, max(stock_name) stock_name, min(coalesce(run_time, trade_date)) first_run_time, max(coalesce(run_time, trade_date)) last_run_time, count(*) case_count FROM cases WHERE stock_code IS NOT NULL GROUP BY stock_code"
    ).fetchall():
        conn.execute(
            "INSERT INTO stocks(stock_code, stock_name, first_run_time, last_run_time, case_count, updated_at) VALUES(?,?,?,?,?,?)",
            (row["stock_code"], row["stock_name"], row["first_run_time"], row["last_run_time"], row["case_count"], now_iso()),
        )


def build_summary(conn: sqlite3.Connection, counters: Counter, started_at: str, legacy_root: Path, scanned_dirs: int, scanned_files: int) -> dict[str, Any]:
    quality = dict(conn.execute("SELECT data_quality, count(*) c FROM cases GROUP BY data_quality").fetchall())
    file_types = dict(conn.execute("SELECT file_type, count(*) c FROM files GROUP BY file_type").fetchall())
    module_stats = [
        dict(row) for row in conn.execute(
            "SELECT module_name, sum(ok) success_count, sum(case when ok=0 then 1 else 0 end) failed_count, count(*) total_count FROM modules GROUP BY module_name ORDER BY failed_count DESC, total_count DESC LIMIT 30"
        ).fetchall()
    ]
    summary = {
        "started_at": started_at,
        "finished_at": now_iso(),
        "legacy_root": str(legacy_root.resolve()),
        "scanned_directories": scanned_dirs,
        "scanned_files": scanned_files,
        "recognized_cases": conn.execute("SELECT count(*) FROM cases").fetchone()[0],
        "stock_count": conn.execute("SELECT count(*) FROM stocks").fetchone()[0],
        "run_record_count": conn.execute("SELECT count(*) FROM cases WHERE run_id IS NOT NULL").fetchone()[0],
        "duplicate_count": conn.execute("SELECT count(*) FROM duplicates").fetchone()[0],
        "unparsed_count": conn.execute("SELECT count(*) FROM files WHERE parse_status='error'").fetchone()[0],
        "file_type_counts": file_types,
        "quality_distribution": quality,
        "module_status_stats": module_stats,
        "new_file_count": counters["new_files"],
        "updated_file_count": counters["updated_files"],
        "unchanged_file_count": counters["unchanged_files"],
        "error_count": conn.execute("SELECT count(*) FROM import_errors").fetchone()[0],
    }
    return summary


def import_legacy_cases(
    legacy_root: Path = DEFAULT_LEGACY_ROOT,
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started_at = now_iso()
    legacy_root = legacy_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)
    counters: Counter = Counter()
    conn.execute("DELETE FROM import_errors")
    conn.execute("DELETE FROM duplicates")
    if not legacy_root.exists():
        raise FileNotFoundError(f"旧项目目录不存在：{legacy_root}")
    roots = [legacy_root / "RadarData", legacy_root / "HumanView"]
    scanned_dirs = 0
    scanned_files = 0
    for root in roots:
        if root.exists():
            for item in root.rglob("*"):
                if item.is_dir():
                    scanned_dirs += 1
                elif item.is_file():
                    scanned_files += 1
    cases, _ = discover_cases(legacy_root)
    latest = build_date_latest(cases)
    seen_hash: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                case_id, stock_code, source_role = case_for_file(path, legacy_root, cases, latest)
                source_root = path.relative_to(legacy_root).parts[0]
                parse_status, error, summary, modules = summarize_file(path)
                digest = sha256_file(path)
                duplicate_of = seen_hash.get(digest)
                if duplicate_of:
                    conn.execute(
                        "INSERT INTO duplicates(kind, path, duplicate_of, case_id, detail, created_at) VALUES(?,?,?,?,?,?)",
                        ("file_hash", str(path.resolve()), duplicate_of, case_id, "same sha256", now_iso()),
                    )
                    counters["duplicates"] += 1
                else:
                    seen_hash[digest] = str(path.resolve())
                if case_id and case_id not in cases:
                    cases[case_id] = CaseCandidate(case_id=case_id, stock_code=stock_code, sources={"file_path_inference"})
                if case_id and case_id in cases:
                    if source_root == "RadarData" and not cases[case_id].radar_root:
                        cases[case_id].radar_root = str(path.parent.resolve())
                    if source_root == "HumanView" and not cases[case_id].humanview_root:
                        cases[case_id].humanview_root = str(path.parent.resolve())
                    if path.suffix.lower() == ".json":
                        upgrade_case_from_json(cases[case_id], path, summary)
                if error:
                    conn.execute(
                        "INSERT INTO import_errors(path, case_id, kind, message, created_at) VALUES(?,?,?,?,?)",
                        (str(path.resolve()), case_id, "parse_error", error, now_iso()),
                    )
                summary["source_role"] = source_role
                upsert_file(conn, path, case_id, stock_code, source_root, duplicate_of, summary, parse_status, error, counters)
            except Exception as exc:
                conn.execute(
                    "INSERT INTO import_errors(path, case_id, kind, message, created_at) VALUES(?,?,?,?,?)",
                    (str(path.resolve()), None, "import_exception", f"{type(exc).__name__}: {exc}", now_iso()),
                )
                counters["exceptions"] += 1
    recompute_cases(conn, cases)
    summary = build_summary(conn, counters, started_at, legacy_root, scanned_dirs, scanned_files)
    (output_dir / "import_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generate_archaeology_report(conn, output_dir / "数据考古发现.html", summary)
    conn.execute(
        "INSERT INTO import_runs(started_at, finished_at, legacy_root, summary_json) VALUES(?,?,?,?)",
        (started_at, summary["finished_at"], str(legacy_root), json_dumps(summary)),
    )
    conn.commit()
    conn.close()
    return summary


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def case_candidate_from_path(path: Path, legacy_root: Path, case_id: str, stock_code: str | None) -> CaseCandidate:
    rel = path.relative_to(legacy_root)
    parts = rel.parts
    stock_name: str | None = None
    trade_date: str | None = None
    run_id: str | None = None
    run_time: str | None = None
    run_session: str | None = None
    radar_root: str | None = None
    humanview_root: str | None = None
    canonical_root: str | None = None
    if parts[0] == "RadarData" and len(parts) >= 3:
        stock_code = stock_code or parts[1]
        trade_date = parts[2] if DATE_RE.match(parts[2]) else None
        if "runs" in parts:
            idx = parts.index("runs")
            if idx + 1 < len(parts):
                run_id = parts[idx + 1]
                run_time, run_session = parse_run_time_from_id(run_id)
                run_root = legacy_root.joinpath(*parts[: idx + 2])
                radar_root = str(run_root.resolve())
                canonical_root = radar_root
        elif trade_date:
            root = legacy_root.joinpath(*parts[:3])
            radar_root = str(root.resolve())
            canonical_root = radar_root
    elif parts[0] == "HumanView" and len(parts) >= 2:
        parsed_code, parsed_name, parsed_date = parse_human_dir_name(parts[1])
        stock_code = stock_code or parsed_code
        stock_name = parsed_name
        trade_date = parsed_date
        if "runs" in parts:
            idx = parts.index("runs")
            if idx + 1 < len(parts):
                run_id = parts[idx + 1]
                run_time, run_session = parse_run_time_from_id(run_id)
                run_root = legacy_root.joinpath(*parts[: idx + 2])
                humanview_root = str(run_root.resolve())
                canonical_root = humanview_root
        else:
            root = legacy_root.joinpath(*parts[:2])
            humanview_root = str(root.resolve())
            canonical_root = humanview_root
    return CaseCandidate(
        case_id=case_id,
        stock_code=stock_code,
        stock_name=stock_name,
        trade_date=trade_date,
        run_id=run_id,
        run_time=run_time,
        run_session=run_session,
        radar_root=radar_root,
        humanview_root=humanview_root,
        canonical_root=canonical_root,
        sources={"incremental_file_path"},
    )


def case_candidate_from_db(row: sqlite3.Row) -> CaseCandidate:
    return CaseCandidate(
        case_id=row["case_id"],
        stock_code=row["stock_code"],
        stock_name=row["stock_name"],
        trade_date=row["trade_date"],
        run_id=row["run_id"],
        run_time=row["run_time"],
        run_session=row["run_session"],
        data_cutoff_time=row["data_cutoff_time"],
        quality=row["data_quality"],
        radar_root=row["radar_root"],
        humanview_root=row["humanview_root"],
        canonical_root=row["canonical_root"],
        sources={"database_existing_case"},
    )


def case_snapshot(conn: sqlite3.Connection, case_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not case_ids:
        return {}
    placeholders = ",".join("?" for _ in case_ids)
    result: dict[str, dict[str, Any]] = {}
    for row in conn.execute(f"SELECT * FROM cases WHERE case_id IN ({placeholders})", tuple(case_ids)).fetchall():
        json_summary = json_loads(row["json_summary"], [])
        field_keys: set[str] = set()
        for item in json_summary if isinstance(json_summary, list) else []:
            if isinstance(item, dict):
                for key in item.get("top_keys", []) if isinstance(item.get("top_keys"), list) else []:
                    field_keys.add(str(key))
        modules = {
            item["module_name"]: bool(item["ok"])
            for item in conn.execute("SELECT module_name, ok FROM modules WHERE case_id=?", (row["case_id"],)).fetchall()
        }
        result[row["case_id"]] = {
            "case_id": row["case_id"],
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"],
            "trade_date": row["trade_date"],
            "run_id": row["run_id"],
            "run_time": row["run_time"],
            "data_quality": row["data_quality"],
            "data_sources": json_loads(row["data_sources_json"], []),
            "module_success": row["module_success"],
            "module_failed": row["module_failed"],
            "file_count": row["file_count"],
            "field_coverage": row["field_coverage"],
            "has_humanview": row["has_humanview"],
            "has_radardata": row["has_radardata"],
            "has_charts": row["has_charts"],
            "has_intraday": row["has_intraday"],
            "has_fund_flow": row["has_fund_flow"],
            "missing": json_loads(row["missing_json"], []),
            "structure_signature": row["structure_signature"],
            "field_keys": sorted(field_keys),
            "modules": modules,
        }
    return result


def changed_case_fields(before: dict[str, Any] | None, after: dict[str, Any] | None, new_stock: bool) -> tuple[str, dict[str, Any]]:
    if before is None and after is not None:
        return "new_case", {
            "new_stock": new_stock,
            "field_keys_added": after.get("field_keys", []),
            "data_sources_added": after.get("data_sources", []),
            "missing_after": after.get("missing", []),
        }
    if before is not None and after is None:
        return "removed_case", {"removed": True}
    if before is None or after is None:
        return "unknown", {}
    changes: dict[str, Any] = {}
    tracked = [
        "data_quality", "module_success", "module_failed", "file_count", "field_coverage",
        "has_humanview", "has_radardata", "has_charts", "has_intraday", "has_fund_flow",
        "structure_signature", "missing",
    ]
    for key in tracked:
        if before.get(key) != after.get(key):
            changes[key] = {"before": before.get(key), "after": after.get(key)}
    before_fields = set(before.get("field_keys", []))
    after_fields = set(after.get("field_keys", []))
    added_fields = sorted(after_fields - before_fields)
    removed_fields = sorted(before_fields - after_fields)
    if added_fields:
        changes["field_keys_added"] = added_fields
    if removed_fields:
        changes["field_keys_removed"] = removed_fields
    before_sources = set(before.get("data_sources", []))
    after_sources = set(after.get("data_sources", []))
    if before_sources != after_sources:
        changes["data_sources_added"] = sorted(after_sources - before_sources)
        changes["data_sources_removed"] = sorted(before_sources - after_sources)
    before_modules = before.get("modules", {})
    after_modules = after.get("modules", {})
    module_changes = [
        {"module": name, "before": before_modules.get(name), "after": after_modules.get(name)}
        for name in sorted(set(before_modules) | set(after_modules))
        if before_modules.get(name) != after_modules.get(name)
    ]
    if module_changes:
        changes["module_status_changes"] = module_changes
    return ("updated_case" if changes else "unchanged_case"), changes


def import_changed_files(
    legacy_root: Path = DEFAULT_LEGACY_ROOT,
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    changed_paths: list[Path] | None = None,
    deleted_paths: list[Path] | None = None,
    event_counts: dict[str, int] | None = None,
    reason: str = "monitor",
) -> dict[str, Any]:
    started_at = now_iso()
    started_perf = time.perf_counter()
    legacy_root = legacy_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    changed_paths = changed_paths or []
    deleted_paths = deleted_paths or []
    event_counts = event_counts or {}
    conn = init_db(db_path)
    auto_id: int | None = None
    try:
        auto_id = conn.execute(
            """
            INSERT INTO auto_import_runs(started_at, legacy_root, changed_count, added_count, modified_count,
                                         deleted_count, renamed_count, success, summary_json)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                started_at,
                str(legacy_root),
                len(changed_paths) + len(deleted_paths),
                event_counts.get("added", 0),
                event_counts.get("modified", 0),
                event_counts.get("deleted", len(deleted_paths)),
                event_counts.get("renamed", 0),
                0,
                json_dumps({"reason": reason}),
            ),
        ).lastrowid
        counters: Counter = Counter()
        cases, _ = discover_cases(legacy_root)
        latest = build_date_latest(cases)
        affected_case_ids: set[str] = set()
        normalized_changed: list[Path] = []
        normalized_deleted: list[Path] = []
        missing_changed_paths: list[Path] = []
        skipped_paths = 0
        for raw_path in changed_paths:
            path = Path(raw_path).resolve()
            if not path.exists() or not path.is_file():
                missing_changed_paths.append(path)
                continue
            try:
                rel = path.relative_to(legacy_root)
            except ValueError:
                skipped_paths += 1
                continue
            if not rel.parts or rel.parts[0] not in {"RadarData", "HumanView"}:
                skipped_paths += 1
                continue
            normalized_changed.append(path)
            case_id, stock_code, _source_role = case_for_file(path, legacy_root, cases, latest)
            if case_id:
                affected_case_ids.add(case_id)
                if case_id not in cases:
                    cases[case_id] = case_candidate_from_path(path, legacy_root, case_id, stock_code)
        deleted_seen: set[str] = set()
        for raw_path in [*deleted_paths, *missing_changed_paths]:
            path = Path(raw_path).resolve()
            path_key = str(path).lower()
            if path_key in deleted_seen:
                continue
            deleted_seen.add(path_key)
            old = conn.execute("SELECT * FROM files WHERE path=?", (str(path),)).fetchone()
            if old and old["case_id"]:
                affected_case_ids.add(old["case_id"])
                if old["case_id"] not in cases:
                    case_row = conn.execute("SELECT * FROM cases WHERE case_id=?", (old["case_id"],)).fetchone()
                    if case_row:
                        cases[old["case_id"]] = case_candidate_from_db(case_row)
            normalized_deleted.append(path)
        before = case_snapshot(conn, affected_case_ids)
        before_stock_codes = {row["stock_code"] for row in conn.execute("SELECT stock_code FROM stocks").fetchall()}
        for path in normalized_deleted:
            conn.execute("DELETE FROM import_errors WHERE path=?", (str(path),))
            old = conn.execute("SELECT * FROM files WHERE path=?", (str(path),)).fetchone()
            if old:
                conn.execute(
                    "UPDATE files SET parse_status='deleted', deleted_at=?, updated_at=?, error=NULL WHERE path=?",
                    (now_iso(), now_iso(), str(path)),
                )
                counters["deleted_files"] += 1
        for path in normalized_changed:
            abs_path = str(path.resolve())
            try:
                case_id, stock_code, source_role = case_for_file(path, legacy_root, cases, latest)
                rel = path.relative_to(legacy_root)
                source_root = rel.parts[0]
                parse_status, error, summary, _modules = summarize_file(path)
                digest = sha256_file(path)
                dup = conn.execute(
                    "SELECT path FROM files WHERE sha256=? AND path<>? AND coalesce(parse_status,'')!='deleted' ORDER BY path LIMIT 1",
                    (digest, abs_path),
                ).fetchone()
                duplicate_of = dup["path"] if dup else None
                conn.execute("DELETE FROM import_errors WHERE path=?", (abs_path,))
                conn.execute("DELETE FROM duplicates WHERE path=?", (abs_path,))
                if duplicate_of:
                    conn.execute(
                        "INSERT INTO duplicates(kind, path, duplicate_of, case_id, detail, created_at) VALUES(?,?,?,?,?,?)",
                        ("file_hash", abs_path, duplicate_of, case_id, "same sha256", now_iso()),
                    )
                    counters["duplicates"] += 1
                if case_id and case_id not in cases:
                    cases[case_id] = case_candidate_from_path(path, legacy_root, case_id, stock_code)
                if case_id and case_id in cases:
                    if source_root == "RadarData" and not cases[case_id].radar_root:
                        cases[case_id].radar_root = str(path.parent.resolve())
                    if source_root == "HumanView" and not cases[case_id].humanview_root:
                        cases[case_id].humanview_root = str(path.parent.resolve())
                    if path.suffix.lower() == ".json":
                        upgrade_case_from_json(cases[case_id], path, summary)
                if error:
                    conn.execute(
                        "INSERT INTO import_errors(path, case_id, kind, message, created_at) VALUES(?,?,?,?,?)",
                        (abs_path, case_id, "parse_error", error, now_iso()),
                    )
                summary["source_role"] = source_role
                upsert_file(conn, path, case_id, stock_code, source_root, duplicate_of, summary, parse_status, error, counters)
            except Exception as exc:
                conn.execute(
                    "INSERT INTO import_errors(path, case_id, kind, message, created_at) VALUES(?,?,?,?,?)",
                    (abs_path, None, "incremental_exception", f"{type(exc).__name__}: {exc}", now_iso()),
                )
                counters["exceptions"] += 1
        recompute_cases(conn, cases)
        after = case_snapshot(conn, affected_case_ids)
        changed_case_count = 0
        new_case_count = 0
        updated_case_count = 0
        for case_id in sorted(affected_case_ids):
            before_case = before.get(case_id)
            after_case = after.get(case_id)
            stock_code = (after_case or before_case or {}).get("stock_code")
            new_stock = bool(stock_code and stock_code not in before_stock_codes)
            change_type, changes = changed_case_fields(before_case, after_case, new_stock)
            if change_type == "unchanged_case":
                continue
            changed_case_count += 1
            if change_type == "new_case":
                new_case_count += 1
            elif change_type == "updated_case":
                updated_case_count += 1
            conn.execute(
                """
                INSERT INTO case_change_events(import_id, created_at, case_id, stock_code, stock_name, change_type,
                                               before_json, after_json, changed_fields_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    auto_id,
                    now_iso(),
                    case_id,
                    stock_code,
                    (after_case or before_case or {}).get("stock_name"),
                    change_type,
                    json_dumps(before_case),
                    json_dumps(after_case),
                    json_dumps(changes),
                ),
            )
        summary = build_summary(
            conn,
            counters,
            started_at,
            legacy_root,
            scanned_dirs=0,
            scanned_files=len(normalized_changed) + len(normalized_deleted),
        )
        summary.update(
            {
                "mode": "incremental_monitor",
                "reason": reason,
                "auto_import_id": auto_id,
                "processed_changed_paths": len(normalized_changed),
                "processed_deleted_paths": len(normalized_deleted),
                "skipped_path_count": skipped_paths,
                "affected_case_count": len(affected_case_ids),
                "changed_case_count": changed_case_count,
                "new_case_count": new_case_count,
                "updated_case_count": updated_case_count,
                "deleted_file_count": counters["deleted_files"],
                "duration_ms": int((time.perf_counter() - started_perf) * 1000),
            }
        )
        (output_dir / "import_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generate_archaeology_report(conn, output_dir / "鏁版嵁鑰冨彜鍙戠幇.html", summary)
        conn.execute(
            "INSERT INTO import_runs(started_at, finished_at, legacy_root, summary_json) VALUES(?,?,?,?)",
            (started_at, summary["finished_at"], str(legacy_root), json_dumps(summary)),
        )
        conn.execute(
            """
            UPDATE auto_import_runs
            SET finished_at=?, duration_ms=?, success=1, summary_json=?, error=NULL
            WHERE id=?
            """,
            (summary["finished_at"], summary["duration_ms"], json_dumps(summary), auto_id),
        )
        conn.commit()
        return summary
    except Exception as exc:
        if auto_id is not None:
            conn.execute(
                "UPDATE auto_import_runs SET finished_at=?, duration_ms=?, success=0, error=? WHERE id=?",
                (now_iso(), int((time.perf_counter() - started_perf) * 1000), f"{type(exc).__name__}: {exc}", auto_id),
            )
            conn.commit()
        raise
    finally:
        conn.close()


def table_rows(rows: list[sqlite3.Row] | list[dict[str, Any]], columns: list[str]) -> str:
    body = []
    for row in rows:
        cells = []
        for col in columns:
            value = row[col] if isinstance(row, sqlite3.Row) else row.get(col)
            cells.append(f"<td>{html.escape(str(value if value is not None else ''))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def generate_archaeology_report(conn: sqlite3.Connection, output_path: Path, summary: dict[str, Any]) -> None:
    complete = conn.execute(
        "SELECT stock_code, stock_name, count(*) case_count, round(avg(field_coverage),3) avg_coverage FROM cases GROUP BY stock_code ORDER BY avg_coverage DESC, case_count DESC LIMIT 10"
    ).fetchall()
    most_runs = conn.execute(
        "SELECT stock_code, stock_name, count(*) case_count FROM cases GROUP BY stock_code ORDER BY case_count DESC, stock_code LIMIT 10"
    ).fetchall()
    same_day = conn.execute(
        "SELECT stock_code, trade_date, count(*) runs FROM cases GROUP BY stock_code, trade_date HAVING count(*)>1 ORDER BY runs DESC"
    ).fetchall()
    failing = conn.execute(
        "SELECT module_name, sum(case when ok=0 then 1 else 0 end) failed_count, count(*) total_count FROM modules GROUP BY module_name ORDER BY failed_count DESC, total_count DESC LIMIT 10"
    ).fetchall()
    sources = conn.execute("SELECT data_sources_json FROM cases").fetchall()
    source_counter: Counter = Counter()
    for row in sources:
        try:
            for item in json.loads(row["data_sources_json"] or "[]"):
                source_counter[item] += 1
        except Exception:
            pass
    signatures = conn.execute(
        "SELECT structure_signature, count(*) c FROM cases GROUP BY structure_signature ORDER BY c DESC"
    ).fetchall()
    duplicates = conn.execute(
        "SELECT duplicate_of, count(*) c FROM duplicates GROUP BY duplicate_of ORDER BY c DESC LIMIT 10"
    ).fetchall()
    usable = conn.execute(
        "SELECT count(*) FROM cases WHERE has_radardata=1 AND has_intraday=1 AND has_fund_flow=1"
    ).fetchone()[0]
    limited = 0
    for row in conn.execute("SELECT missing_json, module_failed FROM cases").fetchall():
        try:
            missing = json.loads(row["missing_json"] or "[]")
        except Exception:
            missing = []
        if missing or int(row["module_failed"] or 0) > 0:
            limited += 1
    html_text = f"""
<!doctype html>
<meta charset="utf-8">
<title>数据考古发现</title>
<style>
body{{font-family:Segoe UI,'Microsoft YaHei',sans-serif;margin:32px;color:#17202a;background:#f7f8fa;line-height:1.6}}
h1,h2{{color:#0f3557}} section{{background:white;padding:18px 22px;margin:18px 0;border:1px solid #d8dee8;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{border:1px solid #d8dee8;padding:7px;vertical-align:top}} th{{background:#eef3f8}}
.kpi{{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:12px}} .card{{background:#eef6ff;padding:12px;border-radius:6px}}
</style>
<h1>真实历史股票案卷库 V0.1 - 数据考古发现</h1>
<section class="kpi">
<div class="card"><b>股票数</b><br>{summary['stock_count']}</div>
<div class="card"><b>历史运行案卷</b><br>{summary['recognized_cases']}</div>
<div class="card"><b>扫描文件</b><br>{summary['scanned_files']}</div>
<div class="card"><b>无法解析</b><br>{summary['unparsed_count']}</div>
</section>
<section><h2>1. 旧项目实际积累了多少只股票的数据</h2><p>按 SQLite `stocks` 表统计，实际识别 {summary['stock_count']} 只股票，来源为 RadarData 股票代码目录、stock_timeline、runs_index 和 HumanView 目录名。</p></section>
<section><h2>2. 一共存在多少次历史运行</h2><p>识别案卷 {summary['recognized_cases']} 个，其中带明确 run_id 的运行记录 {summary['run_record_count']} 个。没有 run_id 的旧格式日期目录以 legacy 案卷记录，缺失字段保持 null/unknown。</p></section>
<section><h2>3. 数据最完整的股票</h2>{table_rows(complete, ['stock_code','stock_name','case_count','avg_coverage'])}</section>
<section><h2>4. 运行次数最多的股票</h2>{table_rows(most_runs, ['stock_code','stock_name','case_count'])}</section>
<section><h2>5. 同一天多次运行</h2>{table_rows(same_day, ['stock_code','trade_date','runs']) if same_day else '<p>未发现同股票同日多次运行。</p>'}</section>
<section><h2>6. 最容易失败的模块</h2>{table_rows(failing, ['module_name','failed_count','total_count'])}</section>
<section><h2>7. 最常使用的数据源</h2><p>{html.escape(json.dumps(source_counter.most_common(12), ensure_ascii=False))}</p></section>
<section><h2>8. 历史数据格式变化</h2><p>发现 {len(signatures)} 类结构化字段签名。早期目录存在日期级 packet/quality/raw/features；后续引入 runs/&lt;run_id&gt; 历史快照，并在日期目录保留 latest view。HumanView 同样存在日期级报告和 runs 快照两种形态。</p>{table_rows(signatures[:10], ['structure_signature','c'])}</section>
<section><h2>9. 重复目录或文件</h2><p>按 SHA-256 识别重复文件 {summary['duplicate_count']} 个，主要来自日期级 latest view 与 runs 快照、以及 case_packet/agent_case_packet 等内容副本。</p>{table_rows(duplicates, ['duplicate_of','c'])}</section>
<section><h2>10. 可直接服务未来选股系统的数据</h2><p>{usable} 个案卷同时具有 RadarData、分时/分钟线线索和资金流相关线索；这些可作为后续特征设计、数据质量回放、模块可靠性评估的真实历史输入。</p></section>
<section><h2>11. 当前无法可靠利用的数据</h2><p>{limited} 个案卷存在缺失项或模块失败记录。无法解析文件与缺失字段已进入 SQLite `files/import_errors/cases.missing_json`，未用默认值伪装。</p></section>
<section><h2>12. 下一步最值得接入 StockSelector 的三类数据</h2><ol><li>质量与模块状态：用于过滤不可用案卷并建立数据可信等级。</li><li>分时/大额成交/资金流特征：已有 CSV 与 parquet 文件，可直接做历史特征候选库。</li><li>HumanView 摘要与 HTML 报告：适合做人工复盘入口，帮助解释案卷完整性而非生成投资结论。</li></ol></section>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读导入旧 L.Lawlight 历史案卷。")
    parser.add_argument("--legacy-root", default=os.environ.get("STOCK_SELECTOR_LEGACY_ROOT", str(DEFAULT_LEGACY_ROOT)))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    summary = import_legacy_cases(Path(args.legacy_root), Path(args.db), Path(args.output_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
