from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .importer import (
    DEFAULT_DB,
    DEFAULT_LEGACY_ROOT,
    DEFAULT_OUTPUT_DIR,
    import_changed_files,
    init_db,
    json_dumps,
    now_iso,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_PATH = PROJECT_ROOT / "logs" / "case_library_monitor.log"


@dataclass(frozen=True)
class FileState:
    path: Path
    size: int
    mtime: float
    mtime_ns: int


@dataclass
class FileEvent:
    event_type: str
    path: Path
    old_path: Path | None = None
    size: int | None = None
    mtime: float | None = None
    sha256: str | None = None


def configure_logger(log_path: Path = LOG_PATH) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("stock_selector.case_library.monitor")
    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path for handler in logger.handlers):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


class CaseLibraryMonitor:
    def __init__(
        self,
        legacy_root: Path = DEFAULT_LEGACY_ROOT,
        db_path: Path = DEFAULT_DB,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        interval_seconds: float = 1.0,
        debounce_seconds: float = 2.0,
        enabled: bool = True,
        import_func: Callable[..., dict[str, Any]] = import_changed_files,
        log_path: Path = LOG_PATH,
    ) -> None:
        self.legacy_root = Path(legacy_root).resolve()
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.interval_seconds = interval_seconds
        self.debounce_seconds = debounce_seconds
        self.enabled = enabled
        self.import_func = import_func
        self.logger = configure_logger(log_path)
        self.watched_roots = [self.legacy_root / "RadarData", self.legacy_root / "HumanView"]
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._snapshot: dict[Path, FileState] = {}
        self._pending: dict[str, FileEvent] = {}
        self._last_change_monotonic: float | None = None
        self._last_heartbeat: str | None = None
        self._last_event_time: str | None = None
        self._last_import_time: str | None = None
        self._last_error: str | None = None
        self._last_import_summary: dict[str, Any] | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="case-library-monitor", daemon=False)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._running = False
            self._write_state()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = enabled
            if not enabled:
                self._pending.clear()
                self._last_change_monotonic = None
            self._write_state()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": self._running,
                "pending_count": len(self._pending),
                "last_heartbeat": self._last_heartbeat,
                "last_event_time": self._last_event_time,
                "last_import_time": self._last_import_time,
                "last_error": self._last_error,
                "interval_seconds": self.interval_seconds,
                "debounce_seconds": self.debounce_seconds,
                "watched_roots": [str(path) for path in self.watched_roots],
                "last_import_summary": self._last_import_summary,
            }

    def _run(self) -> None:
        with self._lock:
            self._running = True
            self._snapshot = self._scan_snapshot()
            self._last_heartbeat = now_iso()
            self._write_state()
        self.logger.info("monitor started roots=%s", [str(path) for path in self.watched_roots])
        while not self._stop.is_set():
            try:
                if self.enabled:
                    current = self._scan_snapshot()
                    events = self._detect_changes(self._snapshot, current)
                    if events:
                        with self._lock:
                            self._merge_pending(events)
                            self._last_change_monotonic = time.monotonic()
                            self._last_event_time = now_iso()
                            self._snapshot = current
                            self._write_state()
                    else:
                        ready = False
                        with self._lock:
                            if self._pending and self._last_change_monotonic is not None:
                                ready = (time.monotonic() - self._last_change_monotonic) >= self.debounce_seconds
                        if ready:
                            self._process_pending()
                else:
                    with self._lock:
                        self._snapshot = self._scan_snapshot()
                        self._pending.clear()
                with self._lock:
                    self._last_heartbeat = now_iso()
                    self._write_state()
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._write_state()
                self.logger.exception("monitor loop recovered after error")
            self._stop.wait(self.interval_seconds)
        with self._lock:
            self._running = False
            self._write_state()
        self.logger.info("monitor stopped")

    def _scan_snapshot(self) -> dict[Path, FileState]:
        snapshot: dict[Path, FileState] = {}
        for root in self.watched_roots:
            if not root.exists():
                continue
            for path in self._iter_files(root):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                snapshot[path.resolve()] = FileState(path.resolve(), stat.st_size, stat.st_mtime, stat.st_mtime_ns)
        return snapshot

    def _iter_files(self, root: Path):
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                yield Path(entry.path)
                        except OSError:
                            continue
            except OSError:
                continue

    def _detect_changes(self, old: dict[Path, FileState], new: dict[Path, FileState]) -> list[FileEvent]:
        events: list[FileEvent] = []
        old_paths = set(old)
        new_paths = set(new)
        for path in sorted(new_paths - old_paths):
            state = new[path]
            events.append(FileEvent("added", path, size=state.size, mtime=state.mtime))
        for path in sorted(old_paths - new_paths):
            state = old[path]
            events.append(FileEvent("deleted", path, size=state.size, mtime=state.mtime))
        for path in sorted(old_paths & new_paths):
            before = old[path]
            after = new[path]
            if before.size != after.size or before.mtime_ns != after.mtime_ns:
                events.append(FileEvent("modified", path, size=after.size, mtime=after.mtime))
        return events

    def _merge_pending(self, events: list[FileEvent]) -> None:
        for event in events:
            key = str(event.path).lower()
            old = self._pending.get(key)
            if old and old.event_type == "added" and event.event_type == "modified":
                old.size = event.size
                old.mtime = event.mtime
                continue
            if old and old.event_type == "deleted" and event.event_type == "added":
                self._pending[key] = FileEvent("modified", event.path, size=event.size, mtime=event.mtime)
                continue
            if old and old.event_type == "added" and event.event_type == "deleted":
                self._pending.pop(key, None)
                continue
            self._pending[key] = event

    def _process_pending(self) -> None:
        with self._lock:
            events = list(self._pending.values())
            self._pending.clear()
            self._last_change_monotonic = None
        events = self._coalesce_renames(events)
        if not events:
            return
        event_ids = self._record_events(events, status="detected")
        changed_paths = [event.path for event in events if event.event_type in {"added", "modified", "renamed"}]
        deleted_paths = [
            event.path if event.event_type == "deleted" else event.old_path
            for event in events
            if event.event_type in {"deleted", "renamed"} and (event.path if event.event_type == "deleted" else event.old_path)
        ]
        counts = {
            "added": sum(1 for event in events if event.event_type == "added"),
            "modified": sum(1 for event in events if event.event_type == "modified"),
            "deleted": sum(1 for event in events if event.event_type == "deleted"),
            "renamed": sum(1 for event in events if event.event_type == "renamed"),
        }
        try:
            summary = self.import_func(
                legacy_root=self.legacy_root,
                db_path=self.db_path,
                output_dir=self.output_dir,
                changed_paths=changed_paths,
                deleted_paths=[path for path in deleted_paths if path is not None],
                event_counts=counts,
                reason="monitor",
            )
            import_id = summary.get("auto_import_id")
            self._update_event_status(event_ids, "imported", import_id=import_id)
            with self._lock:
                self._last_import_time = summary.get("finished_at") or now_iso()
                self._last_import_summary = summary
                self._last_error = None
                self._write_state()
            self.logger.info("incremental import done events=%s summary=%s", counts, summary)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self._update_event_status(event_ids, "failed", message=message)
            with self._lock:
                self._last_error = message
                self._write_state()
            self.logger.exception("incremental import failed but monitor remains alive")

    def _coalesce_renames(self, events: list[FileEvent]) -> list[FileEvent]:
        added = [event for event in events if event.event_type == "added" and event.path.exists()]
        deleted = [event for event in events if event.event_type == "deleted"]
        if not added or not deleted:
            return events
        old_hashes = self._old_hashes([event.path for event in deleted])
        used_added: set[int] = set()
        used_deleted: set[int] = set()
        renamed: list[FileEvent] = []
        for di, deleted_event in enumerate(deleted):
            old_hash = old_hashes.get(str(deleted_event.path.resolve()))
            if not old_hash:
                continue
            for ai, added_event in enumerate(added):
                if ai in used_added:
                    continue
                try:
                    new_hash = sha256_file(added_event.path)
                except OSError:
                    continue
                if old_hash == new_hash:
                    added_event.sha256 = new_hash
                    renamed.append(FileEvent("renamed", added_event.path, old_path=deleted_event.path, size=added_event.size, mtime=added_event.mtime, sha256=new_hash))
                    used_added.add(ai)
                    used_deleted.add(di)
                    break
        result: list[FileEvent] = []
        for event in events:
            if event.event_type == "added" and any(event.path == added[i].path for i in used_added):
                continue
            if event.event_type == "deleted" and any(event.path == deleted[i].path for i in used_deleted):
                continue
            result.append(event)
        result.extend(renamed)
        return result

    def _old_hashes(self, paths: list[Path]) -> dict[str, str]:
        if not paths:
            return {}
        conn = init_db(self.db_path)
        try:
            result: dict[str, str] = {}
            for path in paths:
                row = conn.execute("SELECT sha256 FROM files WHERE path=?", (str(path.resolve()),)).fetchone()
                if row and row["sha256"]:
                    result[str(path.resolve())] = row["sha256"]
            return result
        finally:
            conn.close()

    def _record_events(self, events: list[FileEvent], status: str) -> list[int]:
        conn = init_db(self.db_path)
        try:
            ids: list[int] = []
            for event in events:
                cursor = conn.execute(
                    """
                    INSERT INTO monitor_events(event_time, event_type, path, old_path, size, mtime, sha256, status, message)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        now_iso(),
                        event.event_type,
                        str(event.path.resolve()),
                        str(event.old_path.resolve()) if event.old_path else None,
                        event.size,
                        event.mtime,
                        event.sha256,
                        status,
                        None,
                    ),
                )
                ids.append(cursor.lastrowid)
            conn.commit()
            return ids
        finally:
            conn.close()

    def _update_event_status(self, event_ids: list[int], status: str, import_id: int | None = None, message: str | None = None) -> None:
        if not event_ids:
            return
        conn = init_db(self.db_path)
        try:
            for event_id in event_ids:
                conn.execute(
                    "UPDATE monitor_events SET status=?, import_id=?, message=? WHERE id=?",
                    (status, import_id, message, event_id),
                )
            conn.commit()
        finally:
            conn.close()

    def _write_state(self) -> None:
        conn = init_db(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO monitor_state(id, enabled, running, last_heartbeat, last_event_time, last_import_time,
                                          last_error, debounce_seconds, watched_roots_json, updated_at)
                VALUES(1,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled=excluded.enabled,
                    running=excluded.running,
                    last_heartbeat=excluded.last_heartbeat,
                    last_event_time=excluded.last_event_time,
                    last_import_time=excluded.last_import_time,
                    last_error=excluded.last_error,
                    debounce_seconds=excluded.debounce_seconds,
                    watched_roots_json=excluded.watched_roots_json,
                    updated_at=excluded.updated_at
                """,
                (
                    int(self.enabled),
                    int(self._running),
                    self._last_heartbeat,
                    self._last_event_time,
                    self._last_import_time,
                    self._last_error,
                    self.debounce_seconds,
                    json_dumps([str(path) for path in self.watched_roots]),
                    now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def monitor_state_from_db(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    conn = init_db(db_path)
    try:
        row = conn.execute("SELECT * FROM monitor_state WHERE id=1").fetchone()
        if not row:
            return {"enabled": False, "running": False, "last_error": None, "pending_count": 0}
        return {
            "enabled": bool(row["enabled"]),
            "running": bool(row["running"]),
            "pending_count": 0,
            "last_heartbeat": row["last_heartbeat"],
            "last_event_time": row["last_event_time"],
            "last_import_time": row["last_import_time"],
            "last_error": row["last_error"],
            "debounce_seconds": row["debounce_seconds"],
            "watched_roots": row["watched_roots_json"],
        }
    finally:
        conn.close()
