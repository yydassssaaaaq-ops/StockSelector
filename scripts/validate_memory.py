from __future__ import annotations
import argparse, json
from memory_common import VALID_USER_VERIFICATIONS, VALID_VERIFICATION_LEVELS, classify_observed_head, commit_exists, current_round_dir, current_task_dir, is_ancestor_commit, load_status, observed_head_commit, read_text, repo_root, validate_status, workspace_status


def main() -> int:
    argparse.ArgumentParser(description="验证 Agent-Memory 状态一致性。").parse_args()
    root = repo_root(); failures = []; warnings = []; infos = []; passes = []
    def ok(msg): passes.append("[PASS] " + msg)
    def bad(msg): failures.append("[FAIL] " + msg)
    def warn(msg): warnings.append("[WARNING] " + msg)
    def info(msg): infos.append("[INFO] " + msg)
    required_dirs = ["src/stock_selector", "tests", "config", "data/raw", "data/interim", "data/processed", "outputs", "logs", "docs", "scripts/templates", "Agent-Memory/00-当前状态", "Agent-Memory/01-轮次记录", "Agent-Memory/02-阶段快照", "Agent-Memory/03-GPT导出"]
    required_files = ["README.md", "AGENTS.md", ".gitignore", ".env.example", "pyproject.toml", "scripts/memory_common.py", "scripts/init_memory.py", "scripts/start_task.py", "scripts/start_round.py", "scripts/finish_round.py", "scripts/git_snapshot.py", "scripts/build_gpt_context.py", "scripts/build_index.py", "scripts/validate_memory.py", "scripts/create_checkpoint.py", "scripts/project_status.py", "tests/test_memory_tools.py", "Agent-Memory/INDEX.md", "Agent-Memory/MEMORY_STATUS.json", "Agent-Memory/03-GPT导出/GPT_CONTEXT.md", "Agent-Memory/00-当前状态/PROJECT.md", "Agent-Memory/00-当前状态/CURRENT_TASK.md", "Agent-Memory/00-当前状态/CURRENT_STATE.md", "Agent-Memory/00-当前状态/OPEN_ISSUES.md", "Agent-Memory/00-当前状态/FILE_MAP.md", "Agent-Memory/00-当前状态/ENVIRONMENT.md", "Agent-Memory/00-当前状态/USAGE.md"]
    for item in required_dirs:
        ok("目录存在：" + item) if (root / item).is_dir() else bad("目录缺失：" + item)
    for item in required_files:
        ok("文件存在：" + item) if (root / item).is_file() else bad("文件缺失：" + item)
    try:
        status = load_status(root); validate_status(status); ok("MEMORY_STATUS.json 有效")
    except Exception as exc:
        status = {}; bad("MEMORY_STATUS.json 无效：" + str(exc))
    if status:
        task_dir = current_task_dir(root, status); round_dir = current_round_dir(root, status)
        ok("当前 TASK 目录存在") if task_dir.is_dir() else bad("当前 TASK 目录缺失")
        ok("当前 ROUND 目录存在") if round_dir.is_dir() else bad("当前 ROUND 目录缺失")
        ok("TASK.md 存在") if (task_dir / "TASK.md").is_file() else bad("TASK.md 缺失")
        ok("ROUND.md 存在") if (round_dir / "ROUND.md").is_file() else bad("ROUND.md 缺失")
        ok("GPT_CONTEXT.md 非空") if (root / "Agent-Memory/03-GPT导出/GPT_CONTEXT.md").read_text(encoding="utf-8", errors="replace").strip() else bad("GPT_CONTEXT.md 为空")
        ok("INDEX.md 非空") if (root / "Agent-Memory/INDEX.md").read_text(encoding="utf-8", errors="replace").strip() else bad("INDEX.md 为空")
        ok("验证等级合法") if status.get("verification_level") in VALID_VERIFICATION_LEVELS else bad("验证等级非法")
        ok("用户验证状态合法") if status.get("user_verification") in VALID_USER_VERIFICATIONS else bad("用户验证状态非法")
        if status.get("user_verification") != "passed" and status.get("verification_level") in {"L4_USER_VERIFIED", "L5_CLOSED"}:
            bad("用户未完整验证通过时不得标记 L4 或 L5")
        issue_text = read_text(root / "Agent-Memory/00-当前状态/OPEN_ISSUES.md")
        if status.get("open_issues"):
            ok("OPEN_ISSUES.md 已记录开放问题") if all(str(x) in issue_text for x in status["open_issues"]) else bad("OPEN_ISSUES.md 与 JSON open_issues 不一致")
        else:
            ok("OPEN_ISSUES.md 标记当前无开放问题") if "当前无开放问题" in issue_text else bad("OPEN_ISSUES.md 应写明当前无开放问题")
        git = workspace_status(root)
        ok("JSON 分支与真实 Git 分支一致") if status.get("branch") == git.get("branch") else bad(f"JSON 分支与真实分支不一致：{status.get('branch')} != {git.get('branch')}")
        observed = observed_head_commit(status)
        current = git.get("head_commit")
        exists = commit_exists(root, observed)
        ancestor = is_ancestor_commit(root, observed, current) if observed and current and exists else None
        head_result = classify_observed_head(observed, current, bool(git.get("workspace_clean")), exists, ancestor)
        message = head_result["message"]
        if head_result["severity"] == "PASS":
            ok(message)
        elif head_result["severity"] == "INFO":
            info(message)
        elif head_result["severity"] == "WARNING":
            warn(message)
        else:
            bad(message)
        if status.get("head_commit") and status.get("head_commit") != observed:
            warn("兼容字段 head_commit 与 observed_head_commit 不一致；二者都应表示最近观察到的 HEAD")
        if git.get("branch") != "main":
            warn("真实分支不是 main：" + str(git.get("branch")))
        try:
            data = json.loads((round_dir / "workspace_manifest.json").read_text(encoding="utf-8"))
            for key in ["generated_at", "repository_root", "branch", "base_commit", "head_commit", "tracked_modified", "tracked_deleted", "untracked", "created_by_this_round", "changed_by_this_round", "sha256"]:
                ok("workspace_manifest 字段存在：" + key) if key in data else bad("workspace_manifest 缺少字段：" + key)
        except Exception as exc:
            bad("workspace_manifest.json 无效：" + str(exc))
    for folder in [root / "Agent-Memory", root / "docs"]:
        if folder.exists():
            for path in folder.rglob("*.md"):
                text = path.read_text(encoding="utf-8", errors="replace")
                for token in ["真实起始 commit", "真实当前 commit", "{{", "}}"]:
                    if token in text:
                        bad(f"发现未替换占位符 {token}：{path.relative_to(root)}")
    print("Agent-Memory 检查报告")
    print("=" * 24)
    for line in passes + infos + warnings + failures:
        print(line)
    print(f"结果：{'失败' if failures else '通过'}，FAIL {len(failures)} 项，WARNING {len(warnings)} 项。")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
