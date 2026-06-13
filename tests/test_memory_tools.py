from __future__ import annotations
import json, os, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from memory_common import VALID_USER_VERIFICATIONS, VALID_VERIFICATION_LEVELS, atomic_json, classify_observed_head, load_status, observed_head_commit  # noqa: E402


class MemoryToolsTest(unittest.TestCase):
    def run_script(self, name: str):
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([sys.executable, str(SCRIPTS / name)], cwd=ROOT, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    def test_memory_status_can_be_read(self):
        self.assertEqual(load_status(ROOT)["project"], "StockSelector")

    def test_required_dirs_exist(self):
        for item in ["Agent-Memory", "Agent-Memory/00-当前状态", "scripts", "tests", "src/stock_selector"]:
            self.assertTrue((ROOT / item).exists(), item)

    def test_required_files_exist(self):
        for item in ["Agent-Memory/MEMORY_STATUS.json", "README.md", "AGENTS.md", "scripts/memory_common.py"]:
            self.assertTrue((ROOT / item).is_file(), item)

    def test_verification_level_is_valid(self):
        self.assertIn(load_status(ROOT)["verification_level"], VALID_VERIFICATION_LEVELS)

    def test_user_verification_is_valid(self):
        self.assertIn(load_status(ROOT)["user_verification"], VALID_USER_VERIFICATIONS)

    def test_observed_head_exists_in_status(self):
        status = load_status(ROOT)
        self.assertTrue(observed_head_commit(status))

    def test_current_task_and_round_match(self):
        status = load_status(ROOT)
        task_dir = ROOT / "Agent-Memory" / "01-轮次记录" / status["current_task"]
        round_dir = task_dir / status["current_round"]
        self.assertTrue((task_dir / "TASK.md").is_file())
        self.assertTrue((round_dir / "ROUND.md").is_file())

    def test_generated_context_and_index_non_empty(self):
        self.assertTrue((ROOT / "Agent-Memory/03-GPT导出/GPT_CONTEXT.md").read_text(encoding="utf-8").strip())
        self.assertTrue((ROOT / "Agent-Memory/INDEX.md").read_text(encoding="utf-8").strip())

    def test_build_gpt_context_runs(self):
        cp = self.run_script("build_gpt_context.py")
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)

    def test_build_index_runs(self):
        cp = self.run_script("build_index.py")
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)

    def test_validate_memory_runs(self):
        cp = self.run_script("validate_memory.py")
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)

    def test_project_status_runs(self):
        cp = self.run_script("project_status.py")
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)

    def test_project_status_shows_true_and_observed_head(self):
        cp = self.run_script("project_status.py")
        self.assertEqual(cp.returncode, 0, cp.stderr + cp.stdout)
        self.assertIn("当前真实 HEAD：", cp.stdout)
        self.assertIn("状态文件观察到的 HEAD：", cp.stdout)

    def test_commit_after_status_snapshot_does_not_fail_when_observed_head_is_ancestor(self):
        result = classify_observed_head(
            recorded="1111111111111111111111111111111111111111",
            current="2222222222222222222222222222222222222222",
            workspace_clean=True,
            recorded_exists=True,
            is_ancestor=True,
        )
        self.assertEqual(result["severity"], "WARNING")

    def test_validate_memory_accepts_legal_historical_commit_assessment(self):
        result = classify_observed_head(
            recorded="1111111111111111111111111111111111111111",
            current="2222222222222222222222222222222222222222",
            workspace_clean=False,
            recorded_exists=True,
            is_ancestor=False,
        )
        self.assertEqual(result["severity"], "WARNING")

    def test_invalid_observed_head_is_failure(self):
        result = classify_observed_head(
            recorded="not-a-commit",
            current="2222222222222222222222222222222222222222",
            workspace_clean=True,
            recorded_exists=False,
            is_ancestor=None,
        )
        self.assertEqual(result["severity"], "FAIL")

    def test_bat_helpers_are_portable(self):
        expected = {
            "project_status.bat": "project_status.py",
            "validate_memory.bat": "validate_memory.py",
            "build_gpt_context.bat": "build_gpt_context.py",
        }
        for bat_name, script_name in expected.items():
            with self.subTest(bat=bat_name):
                text = (SCRIPTS / bat_name).read_text(encoding="utf-8", errors="replace")
                lowered = text.lower()
                self.assertIn("%~dp0", text)
                self.assertIn('cd /d "%~dp0.."', text)
                self.assertNotIn("scripts\\scripts", lowered)
                self.assertIn("chcp 65001 >nul", lowered)
                self.assertIn('set "PYTHONUTF8=1"', text)
                self.assertIn("STOCKSELECTOR_NO_PAUSE", text)
                self.assertIn(f'set "SCRIPT=%~dp0{script_name}"', text)
                self.assertIn('python "%SCRIPT%"', text)
                self.assertIn('py "%SCRIPT%"', text)

    def test_atomic_json_write(self):
        tmp = ROOT / "logs" / ".test-tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        target = tmp / "atomic.json"
        try:
            atomic_json(target, {"ok": True}, ROOT)
            self.assertTrue(json.loads(target.read_text(encoding="utf-8"))["ok"])
        finally:
            if target.exists():
                target.unlink()
            if tmp.exists():
                tmp.rmdir()


if __name__ == "__main__":
    unittest.main()
