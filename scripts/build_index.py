from __future__ import annotations
import argparse
from memory_common import load_status, observed_head_commit, repo_root, workspace_status, write_text, fail


def main() -> int:
    argparse.ArgumentParser(description="根据 MEMORY_STATUS.json 覆盖生成 INDEX.md。").parse_args()
    try:
        root = repo_root(); status = load_status(root); git = workspace_status(root)
        content = f"""
# Agent-Memory INDEX

本索引由 `scripts/build_index.py` 自动生成。机器状态以 `MEMORY_STATUS.json` 为唯一权威来源。

## 当前机器状态

- 项目：{status.get('project')} / {status.get('project_name_zh')}
- 当前 TASK：{status.get('current_task')}
- 当前 ROUND：{status.get('current_round')}
- 执行状态：{status.get('execution_status')}
- 验证等级：{status.get('verification_level')}
- 用户验证：{status.get('user_verification')}
- GitHub 同步：{status.get('github_sync')}
- 状态文件记录分支：{status.get('branch')}
- 状态文件观察到的 HEAD：{observed_head_commit(status)}
- 最近稳定 commit：{status.get('last_stable_commit')}
- 最新 CHECKPOINT：{status.get('latest_checkpoint') or '无'}
- 工作区干净：{status.get('workspace_clean')}
- 最后更新：{status.get('last_updated')}

## 当前 Git 实测

- 真实分支：{git.get('branch')}
- 当前真实 HEAD：{git.get('head_commit')}
- 工作区干净：{git.get('workspace_clean')}

## 推荐阅读顺序

1. `Agent-Memory/MEMORY_STATUS.json`
2. `Agent-Memory/03-GPT导出/GPT_CONTEXT.md`
3. `Agent-Memory/00-当前状态/CURRENT_TASK.md`
4. `Agent-Memory/00-当前状态/CURRENT_STATE.md`
5. `Agent-Memory/00-当前状态/OPEN_ISSUES.md`
6. `Agent-Memory/01-轮次记录/{status.get('current_task')}/{status.get('current_round')}/ROUND.md`
7. `Agent-Memory/01-轮次记录/{status.get('current_task')}/{status.get('current_round')}/workspace_manifest.json`
""".strip() + "\n"
        write_text(root / "Agent-Memory" / "INDEX.md", content, root)
        print("已生成 INDEX.md")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
