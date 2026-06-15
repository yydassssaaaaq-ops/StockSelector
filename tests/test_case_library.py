from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stock_selector.case_library.importer import import_legacy_cases
from stock_selector.case_library.webapp import create_server


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_case(
    root: Path,
    code: str = "000001",
    name: str = "平安银行",
    date: str = "2026-01-02",
    run_id: str = "20260102_093000_premarket",
    human: bool = True,
    broken_json: bool = False,
) -> None:
    radar_run = root / "RadarData" / code / date / "runs" / run_id
    human_run = root / "HumanView" / f"{code}_{name}_{date}" / "runs" / run_id
    run_time = f"{date} 09:30:00"
    entry = {
        "run_id": run_id,
        "run_time": run_time,
        "run_session": "premarket",
        "data_quality_grade": "B",
        "radar_root": str((root / "RadarData" / code / date).resolve()),
        "run_root": str(radar_run.resolve()),
        "humanview_root": str(human_run.resolve()),
    }
    write(root / "RadarData" / code / "stock_timeline.json", json.dumps({
        "stock_code": code,
        "stock_name": name,
        "run_count": 1,
        "dates": [{"trade_date": date, "run_count": 1, "latest_run_id": run_id}],
        "latest_run_id": run_id,
        "runs": [entry],
    }, ensure_ascii=False))
    write(root / "RadarData" / code / date / "runs_index.jsonl", json.dumps(entry, ensure_ascii=False) + "\n")
    write(radar_run / "run_manifest.json", json.dumps({"ok": True, "run_id": run_id, "run_context": entry}, ensure_ascii=False))
    packet = {
        "股票代码": code,
        "股票名称": name,
        "数据可信等级": "B",
        "run_id": run_id,
        "run_time": run_time,
        "有效日K来源": "tencent_qfq_backup",
        "关键数据检查": {"分钟分时": True, "个股资金流": True},
    }
    write(radar_run / "packet" / "case_packet.json", json.dumps(packet, ensure_ascii=False))
    write(radar_run / "packet" / "agent_case_packet.json", json.dumps(packet, ensure_ascii=False))
    quality = {
        "股票代码": code,
        "股票名称": name,
        "数据可信等级": "B",
        "run_id": run_id,
        "run_time": run_time,
        "模块成功数": 1,
        "模块失败数": 1,
        "模块状态": [
            {"name": "1分钟分时-测试源", "ok": True, "rows": 2, "cols": 3, "status": "OK"},
            {"name": "概念板块-测试源", "ok": False, "rows": 0, "cols": 0, "status": "FAIL_TEST", "error": "fixture"},
        ],
    }
    write(radar_run / "quality" / "data_quality_report.json", json.dumps(quality, ensure_ascii=False))
    write(radar_run / "features" / "features_intraday_1m.csv", "time,price\n09:30,1.0\n")
    write(radar_run / "features" / "features_fund_flow.csv", "name,value\nmain,1\n")
    write(radar_run / "charts" / f"intraday_trade_chart_{code}_{date}.png", "not-a-real-png-but-indexable")
    if broken_json:
        write(radar_run / "observe" / "broken.json", "{bad json")
    if human:
        write(human_run / "00_打开我.html", "<html><body>报告</body></html>")
        write(human_run / "00_人类摘要.md", "# 摘要\n真实测试案卷")
        write(human_run / "tables" / "模块状态.csv", "模块,状态\n测试,OK\n")
        write(human_run / "human_view_manifest.json", json.dumps({
            "ok": True,
            "run_id": run_id,
            "run_time": run_time,
            "open_html": str((human_run / "00_打开我.html").resolve()),
        }, ensure_ascii=False))


class CaseLibraryTest(unittest.TestCase):
    def import_fixture(self, legacy: Path, out: Path):
        db = out / "case_library.sqlite3"
        output = out / "outputs"
        summary = import_legacy_cases(legacy, db, output)
        return summary, db, output

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory(prefix="case_empty_") as td:
            root = Path(td) / "legacy"
            (root / "RadarData").mkdir(parents=True)
            (root / "HumanView").mkdir(parents=True)
            summary, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["scanned_files"], 0)
            self.assertEqual(summary["recognized_cases"], 0)

    def test_single_complete_case(self):
        with tempfile.TemporaryDirectory(prefix="case_complete_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            summary, db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["stock_count"], 1)
            self.assertEqual(summary["recognized_cases"], 1)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("SELECT has_humanview FROM cases").fetchone()[0], 1)
            conn.close()

    def test_incomplete_case(self):
        with tempfile.TemporaryDirectory(prefix="case_incomplete_") as td:
            root = Path(td) / "legacy"
            make_case(root, human=False)
            _summary, db, _out = self.import_fixture(root, Path(td) / "out")
            conn = sqlite3.connect(db)
            missing = json.loads(conn.execute("SELECT missing_json FROM cases").fetchone()[0])
            conn.close()
            self.assertIn("HumanView", missing)

    def test_duplicate_files(self):
        with tempfile.TemporaryDirectory(prefix="case_dup_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            summary, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertGreater(summary["duplicate_count"], 0)

    def test_incremental_update(self):
        with tempfile.TemporaryDirectory(prefix="case_incremental_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            first, _db, _out = self.import_fixture(root, Path(td) / "out")
            second, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(second["new_file_count"], 0)
            self.assertGreater(second["unchanged_file_count"], 0)
            target = next(root.rglob("features_intraday_1m.csv"))
            time.sleep(0.01)
            target.write_text("time,price\n09:30,1.1\n", encoding="utf-8")
            third, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertGreaterEqual(third["updated_file_count"], 1)
            self.assertGreater(first["new_file_count"], 0)

    def test_broken_json(self):
        with tempfile.TemporaryDirectory(prefix="case_broken_") as td:
            root = Path(td) / "legacy"
            make_case(root, broken_json=True)
            summary, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["recognized_cases"], 1)
            self.assertGreaterEqual(summary["unparsed_count"], 1)

    def test_chinese_path(self):
        with tempfile.TemporaryDirectory(prefix="case_cn_") as td:
            root = Path(td) / "中文旧项目"
            make_case(root, name="测试中文")
            summary, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["stock_count"], 1)

    def test_same_stock_multiple_dates(self):
        with tempfile.TemporaryDirectory(prefix="case_multidate_") as td:
            root = Path(td) / "legacy"
            make_case(root, date="2026-01-02", run_id="20260102_093000_premarket")
            make_case(root, date="2026-01-03", run_id="20260103_093000_premarket")
            summary, _db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["recognized_cases"], 2)

    def test_same_stock_same_day_multiple_runs(self):
        with tempfile.TemporaryDirectory(prefix="case_multirun_") as td:
            root = Path(td) / "legacy"
            make_case(root, date="2026-01-02", run_id="20260102_093000_premarket")
            make_case(root, date="2026-01-02", run_id="20260102_153000_post_close")
            summary, db, _out = self.import_fixture(root, Path(td) / "out")
            self.assertEqual(summary["recognized_cases"], 2)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("SELECT count(*) FROM cases WHERE trade_date='2026-01-02'").fetchone()[0], 2)
            conn.close()

    def test_web_service_smoke(self):
        with tempfile.TemporaryDirectory(prefix="case_web_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            _summary, db, out = self.import_fixture(root, Path(td) / "out")
            server = create_server(db, root, out, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/summary"
                data = json.loads(urllib.request.urlopen(url, timeout=5).read().decode("utf-8"))
                self.assertEqual(data["stock_count"], 1)
            finally:
                server.shutdown()
                server.server_close()

    def test_sqlite_consistency(self):
        with tempfile.TemporaryDirectory(prefix="case_sqlite_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            _summary, db, _out = self.import_fixture(root, Path(td) / "out")
            conn = sqlite3.connect(db)
            case_count = conn.execute("SELECT count(*) FROM cases").fetchone()[0]
            file_count = conn.execute("SELECT count(*) FROM files WHERE case_id IS NOT NULL").fetchone()[0]
            module_count = conn.execute("SELECT count(*) FROM modules").fetchone()[0]
            conn.close()
            self.assertEqual(case_count, 1)
            self.assertGreater(file_count, 0)
            self.assertGreater(module_count, 0)

    def test_legacy_read_only_protection(self):
        with tempfile.TemporaryDirectory(prefix="case_readonly_") as td:
            root = Path(td) / "legacy"
            make_case(root)
            before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            self.import_fixture(root, Path(td) / "out")
            after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
