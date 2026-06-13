from __future__ import annotations
import argparse
from memory_common import format_user_verification, load_status, observed_head_commit, repo_root, workspace_status, fail


def next_step(status: dict) -> str:
    execution = status.get("execution_status")
    if execution == "waiting_github_sync":
        return "用户在 GitHub Desktop 中检查改动，确认后 Commit 并 Publish/Push；同步前不得标记 L5。"
    if execution == "waiting_user_reverification":
        return "用户重新双击验证 BAT 辅助入口，通过后再进入 GitHub 同步阶段。"
    return "用户检查自动验证结果，确认后再决定是否进入 GitHub 外循环。"


def main() -> int:
    argparse.ArgumentParser(description="输出当前项目闭环状态。").parse_args()
    try:
        root = repo_root(); status = load_status(root); git = workspace_status(root)
        print("项目状态")
        print("=" * 20)
        print(f"项目：{status.get('project')} / {status.get('project_name_zh')}")
        print(f"当前 TASK：{status.get('current_task')}")
        print(f"当前 ROUND：{status.get('current_round')}")
        print(f"执行状态：{status.get('execution_status')}")
        print(f"验证等级：{status.get('verification_level')}")
        print(f"用户验证：{format_user_verification(status.get('user_verification'))}")
        print(f"真实分支：{git.get('branch')}")
        print(f"当前真实 HEAD：{git.get('head_commit')}")
        print(f"状态文件观察到的 HEAD：{observed_head_commit(status)}")
        print(f"最近稳定 commit：{status.get('last_stable_commit')}")
        print(f"GitHub 同步：{status.get('github_sync')}")
        print(f"工作区干净：{git.get('workspace_clean')}")
        print(f"tracked 修改数量：{len(git.get('tracked_modified', []))}")
        print(f"untracked 数量：{len(git.get('untracked', []))}")
        print(f"未解决问题数量：{len(status.get('open_issues', []))}")
        print("GPT_CONTEXT 路径：Agent-Memory/03-GPT导出/GPT_CONTEXT.md")
        print(f"建议下一步：{next_step(status)}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
