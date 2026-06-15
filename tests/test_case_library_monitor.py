from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.case_library.importer import import_changed_files, import_legacy_cases
from stock_selector.case_library.monitor import CaseLibraryMonitor
from stock_selector.case_library.webapp import today_changes

from tests.test_case_library import make_case, write


def ensure_legacy(root: Path) -> None:
    (root / "RadarData").mkdir(parents=True, exist_ok=True)
    (root / "HumanView").mkdir(parents=True, exist_ok=True)


def wait_until(predicate, timeout: float = 8.0, interval: float = 0.05):
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:  # pragma: no cover - retained in assertion text
            last_error = exc
        time.sleep(interval)
    raise AssertionError(f"condition not met before timeout; last_error={last_error}")


def scalar(db: Path, sql: str, args: tuple = ()):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


class CaseLibraryMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="case_monitor_")
        self.base = Path(self.tmp.name)
        self.legacy = self.base / "legacy"
        self.out = self.base / "out"
        self.db = self.out / "case_library.sqlite3"
        self.output = self.out / "outputs"
        ensure_legacy(self.legacy)
        import_legacy_cases(self.legacy, self.db, self.output)
        self.monitors: list[CaseLibraryMonitor] = []

    def tearDown(self) -> None:
        for monitor in self.monitors:
            monitor.stop()
        self.tmp.cleanup()

    def start_monitor(self, **kwargs) -> CaseLibraryMonitor:
        monitor = CaseLibraryMonitor(
            legacy_root=self.legacy,
            db_path=self.db,
            output_dir=self.output,
            interval_seconds=0.05,
            debounce_seconds=0.15,
            **kwargs,
        )
        self.monitors.append(monitor)
        monitor.start()
        wait_until(lambda: monitor.status()["running"])
        return monitor

    def test_monitor_imports_new_complete_case(self):
        monitor = self.start_monitor()
        make_case(self.legacy, code="000002", name="测试股份", date="2026-02-01", run_id="20260201_093000_premarket")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM cases WHERE stock_code='000002'") == 1)
        changes = today_changes(self.db)
        self.assertTrue(any(item["stock_code"] == "000002" for item in changes["new_cases"]))
        self.assertIsNone(monitor.status()["last_error"])

    def test_monitor_imports_new_incomplete_case(self):
        self.start_monitor()
        make_case(self.legacy, code="000003", name="残缺股份", date="2026-02-02", run_id="20260202_093000_premarket", human=False)
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM cases WHERE stock_code='000003'") == 1)
        conn = sqlite3.connect(self.db)
        try:
            missing = json.loads(conn.execute("SELECT missing_json FROM cases WHERE stock_code='000003'").fetchone()[0])
        finally:
            conn.close()
        self.assertIn("HumanView", missing)

    def test_monitor_debounces_continuous_write(self):
        self.start_monitor()
        code = "000004"
        date = "2026-02-03"
        run_id = "20260203_093000_premarket"
        run = self.legacy / "RadarData" / code / date / "runs" / run_id
        write(self.legacy / "RadarData" / code / date / "runs_index.jsonl", json.dumps({
            "run_id": run_id,
            "run_time": "2026-02-03 09:30:00",
            "run_session": "premarket",
        }) + "\n")
        target = run / "packet" / "case_packet.json"
        write(target, "{bad")
        time.sleep(0.05)
        write(target, json.dumps({"stock_code": code, "run_id": run_id, "run_time": "2026-02-03 09:30:00", "top": "ok"}))
        write(run / "features" / "features_intraday_1m.csv", "time,price\n09:30,1\n")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM files WHERE path=? AND parse_status='ok'", (str(target.resolve()),)) == 1)
        self.assertEqual(scalar(self.db, "SELECT count(*) FROM files WHERE path=? AND parse_status='error'", (str(target.resolve()),)), 0)

    def test_monitor_detects_file_modify(self):
        make_case(self.legacy, code="000005", name="修改股份", date="2026-02-04", run_id="20260204_093000_premarket")
        import_legacy_cases(self.legacy, self.db, self.output)
        self.start_monitor()
        target = next((self.legacy / "RadarData" / "000005").rglob("run_manifest.json"))
        data = json.loads(target.read_text(encoding="utf-8"))
        data["new_observed_field"] = "after-monitor"
        time.sleep(0.02)
        target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM case_change_events WHERE changed_fields_json LIKE '%new_observed_field%'") >= 1)

    def test_monitor_marks_deleted_file(self):
        make_case(self.legacy, code="000006", name="删除股份", date="2026-02-05", run_id="20260205_093000_premarket")
        import_legacy_cases(self.legacy, self.db, self.output)
        self.start_monitor()
        target = next((self.legacy / "RadarData" / "000006").rglob("features_fund_flow.csv"))
        target.unlink()
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM files WHERE path=? AND parse_status='deleted'", (str(target.resolve()),)) == 1)

    def test_monitor_handles_broken_json(self):
        monitor = self.start_monitor()
        make_case(self.legacy, code="000007", name="坏JSON股份", date="2026-02-06", run_id="20260206_093000_premarket", broken_json=True)
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM files WHERE parse_status='error'") >= 1)
        self.assertTrue(monitor.status()["running"])

    def test_monitor_chinese_path(self):
        self.legacy = self.base / "中文旧项目"
        ensure_legacy(self.legacy)
        import_legacy_cases(self.legacy, self.db, self.output)
        self.start_monitor()
        make_case(self.legacy, code="000008", name="中文路径股份", date="2026-02-07", run_id="20260207_093000_premarket")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM stocks WHERE stock_code='000008'") == 1)

    def test_monitor_restart_keeps_working(self):
        monitor = self.start_monitor()
        monitor.stop()
        self.start_monitor()
        make_case(self.legacy, code="000009", name="重启股份", date="2026-02-08", run_id="20260208_093000_premarket")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM cases WHERE stock_code='000009'") == 1)

    def test_monitor_recovers_after_import_exception(self):
        calls = {"count": 0}

        def flaky_import(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated monitor import failure")
            return import_changed_files(**kwargs)

        monitor = self.start_monitor(import_func=flaky_import)
        make_case(self.legacy, code="000010", name="失败一次", date="2026-02-09", run_id="20260209_093000_premarket")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM monitor_events WHERE status='failed'") >= 1)
        make_case(self.legacy, code="000011", name="恢复股份", date="2026-02-10", run_id="20260210_093000_premarket")
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM auto_import_runs WHERE success=1") >= 1)
        self.assertTrue(monitor.status()["running"])

    def test_monitor_detects_rename(self):
        make_case(self.legacy, code="000012", name="重命名股份", date="2026-02-11", run_id="20260211_093000_premarket")
        import_legacy_cases(self.legacy, self.db, self.output)
        self.start_monitor()
        source = next((self.legacy / "RadarData" / "000012").rglob("features_intraday_1m.csv"))
        target = source.with_name("features_intraday_1m_renamed.csv")
        source.rename(target)
        wait_until(lambda: scalar(self.db, "SELECT count(*) FROM monitor_events WHERE event_type='renamed'") >= 1)

    def test_monitor_idle_keeps_legacy_read_only(self):
        make_case(self.legacy, code="000013", name="只读股份", date="2026-02-12", run_id="20260212_093000_premarket")
        import_legacy_cases(self.legacy, self.db, self.output)
        before = {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in self.legacy.rglob("*") if path.is_file()}
        monitor = self.start_monitor()
        time.sleep(0.3)
        monitor.stop()
        after = {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in self.legacy.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
