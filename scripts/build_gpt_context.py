from __future__ import annotations
import argparse
from pathlib import Path
from memory_common import current_round_dir, load_status, observed_head_commit, read_text, render_list, repo_root, workspace_status, write_text, fail


def optional(path: Path, fallback: str = "待确认") -> str:
    return read_text(path).strip() if path.exists() and read_text(path).strip() else fallback


def brief(text: str, n: int = 24) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:n]) if lines else "待确认"


def next_step(status: dict) -> str:
    execution = status.get("execution_status")
    if execution == "waiting_github_sync":
        return "用户在 GitHub Desktop 中检查改动，确认后 Commit 并 Publish/Push；同步前不得标记 L5。"
    if execution == "waiting_user_reverification":
        return "用户重新双击验证 BAT 辅助入口，通过后再进入 GitHub 同步阶段。"
    return "用户检查自动验证结果，确认后再决定是否进入 GitHub 外循环。"


def verification_guard(status: dict) -> str:
    if status.get("user_verification") == "passed":
        return "用户验证已通过，可保持 `L4_USER_VERIFIED`；GitHub 同步前不得标记 `L5_CLOSED`。"
    return "当前不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。"


def main() -> int:
    argparse.ArgumentParser(description="覆盖生成 GPT_CONTEXT.md。").parse_args()
    try:
        root = repo_root(); status = load_status(root); git = workspace_status(root)
        mem = root / "Agent-Memory"; state = mem / "00-当前状态"; round_dir = current_round_dir(root, status)
        content = f"""
# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：{status.get('project')} / {status.get('project_name_zh')}
- 当前 TASK：{status.get('current_task')}
- 当前 ROUND：{status.get('current_round')}
- 执行状态：{status.get('execution_status')}
- 验证等级：{status.get('verification_level')}
- 用户验证：{status.get('user_verification')}
- GitHub 同步：{status.get('github_sync')}
- 当前真实分支：{git.get('branch')}
- 当前真实 HEAD：{git.get('head_commit')}
- 状态文件观察到的 HEAD：{observed_head_commit(status)}
- 工作区干净：{git.get('workspace_clean')}

## B. Agent 解释

### 当前任务
{brief(optional(state / 'CURRENT_TASK.md'))}

### 当前状态
{brief(optional(state / 'CURRENT_STATE.md'))}

### 开放问题
{brief(optional(state / 'OPEN_ISSUES.md', '当前无开放问题'))}

### 最近 ROUND
{brief(optional(round_dir / 'ROUND.md'))}

### 工作区摘要

tracked 修改：
{render_list(git.get('tracked_modified', []))}

未跟踪文件：
{render_list(git.get('untracked', [])[:120])}

## C. 用户验证

- 用户验证状态：{status.get('user_verification')}
- {verification_guard(status)}
- 下一步建议：{next_step(status)}

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/{status.get('current_task')}/{status.get('current_round')}/`
- `scripts/`
- `tests/test_memory_tools.py`
""".strip() + "\n"
        write_text(mem / "03-GPT导出" / "GPT_CONTEXT.md", content, root)
        print("已生成 GPT_CONTEXT.md")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
