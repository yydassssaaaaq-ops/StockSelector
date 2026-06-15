from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "StockSelector"
PROJECT_ZH = "A股智能选股系统"
TASK_ID = "TASK-20260612-001"
ROUND_ID = "ROUND-001"
TASK_NAME = "建立 Agent 项目闭环系统 V4.1 执行增强版和选股系统工程壳"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def repo_root() -> Path:
    cur = Path.cwd().resolve()
    for item in [cur, *cur.parents]:
        if (item / ".git").exists():
            return item
    raise RuntimeError("未找到 .git，请在 StockSelector 仓库内运行。")


def find_git() -> Path | None:
    candidates: list[Path] = []
    if shutil.which("git"):
        candidates.append(Path(shutil.which("git") or ""))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend(sorted(Path(local).glob("GitHubDesktop/app-*/resources/app/git/cmd/git.exe"), reverse=True))
        candidates.extend(sorted(Path(local).glob("GitHubDesktop/app-*/resources/app/git/mingw64/bin/git.exe"), reverse=True))
    for item in [
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\bin\git.exe"),
        Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\git.exe"),
        *candidates,
    ]:
        if item and item.exists():
            return item
    return None


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    git = find_git()
    if git is None:
        return subprocess.CompletedProcess(["git", *args], 127, "", "未找到 git 可执行文件")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [str(git), *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def fallback_branch_head(root: Path) -> tuple[str, str | None]:
    head_file = root / ".git" / "HEAD"
    text = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if text.startswith("ref: "):
        ref = text[5:].strip()
        branch = ref.rsplit("/", 1)[-1]
        ref_path = root / ".git" / ref
        return branch, ref_path.read_text(encoding="utf-8", errors="replace").strip() if ref_path.exists() else None
    return "detached", text or None


def git_branch_head(root: Path) -> tuple[str, str | None]:
    branch_cp = run_git(root, ["branch", "--show-current"])
    head_cp = run_git(root, ["rev-parse", "--verify", "HEAD"])
    branch = branch_cp.stdout.strip() if branch_cp.returncode == 0 and branch_cp.stdout.strip() else ""
    head = head_cp.stdout.strip() if head_cp.returncode == 0 and head_cp.stdout.strip() else None
    if branch and head:
        return branch, head
    fallback_branch, fallback_head = fallback_branch_head(root)
    return branch or fallback_branch, head or fallback_head


def parse_status(root: Path) -> dict[str, object]:
    cp = run_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    tracked_modified: list[str] = []
    tracked_deleted: list[str] = []
    renamed: list[dict[str, str]] = []
    untracked: list[str] = []
    if cp.returncode == 0:
        parts = cp.stdout.split("\0")
        i = 0
        while i < len(parts):
            rec = parts[i]
            if not rec:
                i += 1
                continue
            xy = rec[:2]
            path = rec[3:] if len(rec) > 3 else ""
            if xy == "??":
                untracked.append(path)
            elif "R" in xy or "C" in xy:
                old = parts[i + 1] if i + 1 < len(parts) else ""
                renamed.append({"from": old, "to": path})
                i += 1
            elif "D" in xy:
                tracked_deleted.append(path)
            else:
                tracked_modified.append(path)
            i += 1
    branch, head = git_branch_head(root)
    clean = not tracked_modified and not tracked_deleted and not renamed and not untracked
    return {
        "branch": branch,
        "head_commit": head,
        "workspace_clean": clean,
        "tracked_modified": sorted(set(tracked_modified)),
        "tracked_deleted": sorted(set(tracked_deleted)),
        "renamed": renamed,
        "untracked": sorted(set(untracked)),
        "git_available": cp.returncode == 0,
        "git_warning": "" if cp.returncode == 0 else (cp.stderr.strip() or "git 不可用"),
    }


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def safe_write(root: Path, rel_path: str, content: str, force: bool) -> bool:
    path = root / rel_path
    resolved = path.resolve()
    if ".git" in resolved.relative_to(root.resolve()).parts:
        raise RuntimeError(f"拒绝写入 .git：{resolved}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content.lstrip("\n").replace("\r\n", "\n")
    if path.exists() and path.read_text(encoding="utf-8", errors="replace") == text:
        return False
    if path.exists() and not force:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def touch(root: Path, rel_path: str) -> None:
    path = root / rel_path
    if ".git" in path.resolve().relative_to(root.resolve()).parts:
        raise RuntimeError("拒绝写入 .git")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


MEMORY_COMMON = r'''
from __future__ import annotations

import hashlib, json, os, shutil, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = "StockSelector"
PROJECT_NAME_ZH = "A股智能选股系统"
VALID_VERIFICATION_LEVELS = {"L0_PLANNED", "L1_CHANGED", "L2_AGENT_TESTED", "L4_USER_VERIFIED", "L5_CLOSED"}
VALID_USER_VERIFICATIONS = {"not_run", "passed", "failed", "partial_failed"}
USER_VERIFICATION_LABELS = {
    "not_run": "not_run（用户尚未验证）",
    "passed": "passed（用户验证通过）",
    "failed": "failed（用户验证失败）",
    "partial_failed": "partial_failed（核心能力通过，部分入口或场景失败）",
}
REQUIRED_STATUS_FIELDS = [
    "schema_version", "project", "project_name_zh", "current_task", "current_round",
    "latest_checkpoint", "execution_status", "verification_level", "user_verification",
    "branch", "base_commit", "head_commit", "last_stable_commit", "workspace_clean",
    "github_sync", "last_updated", "open_issues", "notes",
]
BANNED_GIT = {"add", "commit", "push", "pull", "merge", "rebase", "reset", "clean", "checkout", "switch"}


def fail(message: str, code: int = 1) -> None:
    print(f"错误：{message}", file=sys.stderr)
    raise SystemExit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for item in [cur, *cur.parents]:
        if (item / ".git").exists():
            return item
    raise RuntimeError("未找到 .git，请在 StockSelector 仓库内运行。")


def ensure_inside_repo(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    if ".git" in resolved.relative_to(root.resolve()).parts:
        raise RuntimeError(f"拒绝访问 .git 内部路径：{resolved}")
    return resolved


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str, root: Path | None = None) -> bool:
    root = root or repo_root()
    ensure_inside_repo(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content.lstrip("\n").replace("\r\n", "\n")
    if path.exists() and read_text(path) == text:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def atomic_json(path: Path, data: Any, root: Path | None = None) -> None:
    root = root or repo_root()
    ensure_inside_repo(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def memory_root(root: Path) -> Path:
    return root / "Agent-Memory"


def load_status(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    return read_json(memory_root(root) / "MEMORY_STATUS.json")


def validate_status(status: dict[str, Any]) -> None:
    missing = [item for item in REQUIRED_STATUS_FIELDS if item not in status]
    if missing:
        raise RuntimeError("MEMORY_STATUS.json 缺少字段：" + ", ".join(missing))
    if status.get("verification_level") not in VALID_VERIFICATION_LEVELS:
        raise RuntimeError("verification_level 不合法")
    if status.get("user_verification") not in VALID_USER_VERIFICATIONS:
        raise RuntimeError("user_verification 不合法")
    if not observed_head_commit(status):
        raise RuntimeError("MEMORY_STATUS.json 缺少 observed_head_commit/head_commit 观察值")


def format_user_verification(value: str | None) -> str:
    return USER_VERIFICATION_LABELS.get(str(value), f"{value}（未知用户验证状态）")


def observed_head_commit(status: dict[str, Any]) -> str | None:
    """Return the HEAD value observed when MEMORY_STATUS.json was generated."""
    return status.get("observed_head_commit") or status.get("head_commit")


def commit_exists(root: Path, commit: str | None) -> bool:
    if not commit:
        return False
    cp = run_git(["cat-file", "-e", f"{commit}^{{commit}}"], root)
    return cp.returncode == 0


def is_ancestor_commit(root: Path, maybe_ancestor: str, maybe_descendant: str) -> bool | None:
    cp = run_git(["merge-base", "--is-ancestor", maybe_ancestor, maybe_descendant], root)
    if cp.returncode == 0:
        return True
    if cp.returncode == 1:
        return False
    return None


def classify_observed_head(recorded: str | None, current: str | None, workspace_clean: bool, recorded_exists: bool, is_ancestor: bool | None) -> dict[str, str]:
    if not recorded:
        return {"severity": "FAIL", "message": "状态文件观察到的 HEAD 缺失"}
    if not current:
        return {"severity": "FAIL", "message": "无法读取当前真实 HEAD"}
    if not recorded_exists:
        return {"severity": "FAIL", "message": f"状态文件观察到的 HEAD 不是 Git 可识别的 commit：{recorded}"}
    if recorded == current:
        return {"severity": "PASS", "message": "状态文件观察到的 HEAD 与当前真实 HEAD 一致"}
    if is_ancestor is True:
        return {"severity": "WARNING", "message": "状态文件观察到的 HEAD 是当前真实 HEAD 的祖先；这通常表示状态文件生成后发生过提交，不构成自引用失败"}
    if not workspace_clean:
        return {"severity": "WARNING", "message": "状态文件观察到的 HEAD 与当前真实 HEAD 不一致，但工作区存在未提交修改；以当前真实 HEAD 为准"}
    if is_ancestor is None:
        return {"severity": "WARNING", "message": "状态文件观察到的 HEAD 合法，但无法确认它与当前真实 HEAD 的祖先关系"}
    return {"severity": "FAIL", "message": "状态文件观察到的 HEAD 与当前真实 HEAD 不一致，且不是祖先；请检查是否切换历史或状态记录异常"}


def save_status(root: Path, status: dict[str, Any]) -> None:
    validate_status(status)
    atomic_json(memory_root(root) / "MEMORY_STATUS.json", status, root)


def find_git() -> Path | None:
    candidates = []
    found = shutil.which("git")
    if found:
        candidates.append(Path(found))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend(sorted(Path(local).glob("GitHubDesktop/app-*/resources/app/git/cmd/git.exe"), reverse=True))
        candidates.extend(sorted(Path(local).glob("GitHubDesktop/app-*/resources/app/git/mingw64/bin/git.exe"), reverse=True))
    candidates.extend([Path(r"C:\Program Files\Git\cmd\git.exe"), Path(r"C:\Program Files\Git\bin\git.exe")])
    return next((item for item in candidates if item.exists()), None)


def run_git(args: list[str], root: Path | None = None) -> subprocess.CompletedProcess[str]:
    root = root or repo_root()
    if args and args[0] in BANNED_GIT:
        raise RuntimeError("拒绝执行非只读 Git 命令：git " + " ".join(args))
    git = find_git()
    if git is None:
        return subprocess.CompletedProcess(["git", *args], 127, "", "未找到 git 可执行文件")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run([str(git), *args], cwd=root, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def fallback_branch_head(root: Path) -> tuple[str, str | None]:
    head = read_text(root / ".git" / "HEAD").strip()
    if head.startswith("ref: "):
        ref = head[5:].strip()
        branch = ref.rsplit("/", 1)[-1]
        ref_path = root / ".git" / ref
        return branch, read_text(ref_path).strip() if ref_path.exists() else None
    return "detached", head or None


def git_branch_head(root: Path | None = None) -> tuple[str, str | None]:
    root = root or repo_root()
    branch_cp = subprocess.CompletedProcess([], 1, "", "")
    head_cp = subprocess.CompletedProcess([], 1, "", "")
    git = find_git()
    if git:
        branch_cp = subprocess.run([str(git), "branch", "--show-current"], cwd=root, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        head_cp = subprocess.run([str(git), "rev-parse", "--verify", "HEAD"], cwd=root, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fb_branch, fb_head = fallback_branch_head(root)
    return (branch_cp.stdout.strip() or fb_branch, head_cp.stdout.strip() or fb_head)


def workspace_status(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    git = find_git()
    tracked_modified: list[str] = []
    tracked_deleted: list[str] = []
    renamed: list[dict[str, str]] = []
    untracked: list[str] = []
    warning = ""
    ok = False
    if git:
        cp = subprocess.run([str(git), "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ok = cp.returncode == 0
        warning = "" if ok else cp.stderr.strip()
        if ok:
            parts = cp.stdout.split("\0")
            i = 0
            while i < len(parts):
                rec = parts[i]
                if not rec:
                    i += 1
                    continue
                xy, path = rec[:2], rec[3:]
                if xy == "??":
                    untracked.append(path)
                elif "R" in xy or "C" in xy:
                    old = parts[i + 1] if i + 1 < len(parts) else ""
                    renamed.append({"from": old, "to": path})
                    i += 1
                elif "D" in xy:
                    tracked_deleted.append(path)
                else:
                    tracked_modified.append(path)
                i += 1
    else:
        warning = "未找到 git，可用 .git 元数据降级读取分支和 HEAD。"
    branch, head = git_branch_head(root)
    clean = not tracked_modified and not tracked_deleted and not renamed and not untracked
    return {
        "branch": branch, "head_commit": head, "workspace_clean": clean,
        "tracked_modified": sorted(set(tracked_modified)), "tracked_deleted": sorted(set(tracked_deleted)),
        "renamed": renamed, "untracked": sorted(set(untracked)), "git_available": ok, "git_warning": warning,
    }


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_sha(root: Path, paths: list[str]) -> dict[str, str]:
    out = {}
    for item in sorted(set(paths)):
        path = root / item
        if path.is_file():
            digest = sha256_file(path)
            if digest:
                out[item] = digest
    return out


def current_task_dir(root: Path, status: dict[str, Any] | None = None) -> Path:
    status = status or load_status(root)
    return memory_root(root) / "01-轮次记录" / status["current_task"]


def current_round_dir(root: Path, status: dict[str, Any] | None = None) -> Path:
    status = status or load_status(root)
    return current_task_dir(root, status) / status["current_round"]


def manifest(root: Path | None = None, base_commit: str | None = None, start_clean: bool | None = None) -> dict[str, Any]:
    root = root or repo_root()
    st = workspace_status(root)
    changed = st["tracked_modified"] + st["tracked_deleted"] + [r.get("to", "") for r in st["renamed"]]
    created = st["untracked"]
    return {
        "generated_at": now_iso(), "repository_root": str(root), "branch": st["branch"],
        "base_commit": base_commit, "head_commit": st["head_commit"],
        "start_workspace_clean": start_clean, "end_workspace_clean": st["workspace_clean"],
        "tracked_modified": st["tracked_modified"], "tracked_deleted": st["tracked_deleted"],
        "renamed": st["renamed"], "untracked": st["untracked"],
        "created_by_this_round": created, "changed_by_this_round": changed,
        "sha256": collect_sha(root, created + changed), "git_available": st["git_available"],
        "git_warning": st["git_warning"], "git_add_executed": False, "committed": False, "pushed": False,
    }


def render_list(items: list[Any], empty: str = "无") -> str:
    if not items:
        return "- " + empty
    return "\n".join("- " + (json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)) for item in items)
'''

BUILD_GPT_CONTEXT = r'''
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
'''

BUILD_INDEX = r'''
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
'''

GIT_SNAPSHOT = r'''
from __future__ import annotations
import argparse
from pathlib import Path
from memory_common import atomic_json, current_round_dir, load_status, manifest, repo_root, run_git, fail


def write_patch(root: Path, output: Path) -> tuple[bool, str]:
    cp = run_git(["diff", "--binary"], root)
    if cp.returncode != 0:
        return False, cp.stderr.strip() or "git diff 执行失败"
    output.write_text(cp.stdout, encoding="utf-8", newline="\n")
    return True, "patch 仅包含 tracked diff，不包含未跟踪文件。"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 workspace_manifest.json，不执行 git add/commit/push。")
    parser.add_argument("--output")
    parser.add_argument("--base-commit")
    parser.add_argument("--start-clean", choices=["true", "false"])
    parser.add_argument("--patch", action="store_true")
    args = parser.parse_args()
    try:
        root = repo_root(); status = load_status(root)
        out = Path(args.output) if args.output else current_round_dir(root, status) / "workspace_manifest.json"
        if not out.is_absolute():
            out = root / out
        data = manifest(root, args.base_commit or status.get("base_commit"), None if args.start_clean is None else args.start_clean == "true")
        if args.patch:
            ok, note = write_patch(root, out.with_name("changes.patch"))
            data["patch"] = {"path": str(out.with_name("changes.patch")), "generated": ok, "includes_untracked": False, "note": note}
        atomic_json(out, data, root)
        print(f"已生成工作区清单：{out}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

VALIDATE_MEMORY = r'''
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
        if status.get("execution_status") in {"task_started", "round_started"} and status.get("user_verification") != "not_run":
            bad("新 TASK/ROUND 开始后用户验证状态必须重置为 not_run")
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
'''

PROJECT_STATUS = r'''
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
'''

FINISH_ROUND = r'''
from __future__ import annotations
import argparse, json
from pathlib import Path
from memory_common import atomic_json, current_round_dir, fail, load_status, manifest, now_iso, render_list, repo_root, save_status, workspace_status, write_text


def md_tests(items):
    return "\n".join(f"- `{x.get('command')}`：退出码 {x.get('exit_code')}，{x.get('result')}" for x in items) if items else "- 未提供测试结果"


def main() -> int:
    parser = argparse.ArgumentParser(description="结束当前 ROUND，写入真实测试结果。")
    parser.add_argument("--tests-json", required=True)
    args = parser.parse_args()
    try:
        root = repo_root(); status = load_status(root)
        tests = json.loads(Path(args.tests_json).read_text(encoding="utf-8-sig"))
        all_passed = all(int(x.get("exit_code", 1)) == 0 for x in tests)
        git = workspace_status(root)
        data = manifest(root, status.get("base_commit"), status.get("start_workspace_clean"))
        round_dir = current_round_dir(root, status)
        atomic_json(round_dir / "workspace_manifest.json", data, root)
        level = "L2_AGENT_TESTED" if all_passed else "L1_CHANGED"
        execution = "waiting_user_review" if all_passed else "agent_test_failed"
        status.update({
            "execution_status": execution, "verification_level": level, "user_verification": "not_run",
            "branch": git.get("branch"), "observed_head_commit": git.get("head_commit"), "head_commit": git.get("head_commit"),
            "workspace_clean": git.get("workspace_clean"), "github_sync": "not_pushed",
            "last_updated": now_iso(), "open_issues": [] if all_passed else ["自动测试未全部通过，需查看 ROUND.md。"],
        })
        save_status(root, status)
        round_md = f"""
# {status.get('current_round')}

## 基本信息

- 所属 TASK：{status.get('current_task')}
- ROUND ID：{status.get('current_round')}
- 触发来源：用户初始化指令文件 `Codex初始化指令-StockSelector-V4.1.txt`
- 用户目标：建立 Agent 项目闭环系统 V4.1 执行增强版和选股系统工程壳。
- 本轮目标：完成工程目录、Agent-Memory、自动化脚本、状态校验、测试和第一轮记录。
- 起始时间：{status.get('round_started_at')}
- 结束时间：{now_iso()}

## Codex 实际修改

- 建立 `src/stock_selector/` 中性业务模块壳。
- 建立 `Agent-Memory/` 记忆系统、当前状态文档、TASK 与 ROUND 记录。
- 实现 `scripts/` 下闭环自动化脚本和 Windows BAT 辅助入口。
- 建立 `tests/test_memory_tools.py` 并使用 `unittest` 验证脚本能力。
- 扩展 `.gitignore`，新增 `.env.example` 与 `pyproject.toml`。
- 未开发任何真实选股算法。

## 修改文件

tracked 修改：
{render_list(data.get('tracked_modified', []))}

未跟踪文件：
{render_list(data.get('untracked', []))}

## Git 状态锚点

- 当前真实分支：{data.get('branch')}
- 开始 HEAD：{data.get('base_commit')}
- 结束 HEAD：{data.get('head_commit')}
- 初始工作区是否干净：{data.get('start_workspace_clean')}
- 结束工作区是否干净：{data.get('end_workspace_clean')}
- workspace_manifest.json：`Agent-Memory/01-轮次记录/{status.get('current_task')}/{status.get('current_round')}/workspace_manifest.json`
- 是否 Commit：否
- 是否 Push：否
- 是否切换分支：否

## 测试命令

{md_tests(tests)}

## 实际结果

- 当前验证等级：{level}
- 用户验证状态：not_run
- 执行状态：{execution}
- GitHub 同步：not_pushed

## 风险与回滚

- 本轮未提交 Git，回滚应由用户在确认后使用 Git 工具处理。
- 当前尚未开发选股业务，不应被视为可用于真实投资或交易。

## 当前结论

{'规定自动测试已通过，当前等待用户检查。' if all_passed else '存在自动测试失败，需先修复失败项。'}

## 下一步

用户检查本轮文件、状态和测试输出后，再决定是否进入 GitHub 外循环、是否提交以及下一阶段业务事实确认。
""".strip() + "\n"
        write_text(round_dir / "ROUND.md", round_md, root)
        state_dir = root / "Agent-Memory" / "00-当前状态"
        write_text(state_dir / "CURRENT_TASK.md", f"""# CURRENT_TASK

- 当前 TASK：{status.get('current_task')}
- 任务名称：建立 Agent 项目闭环系统 V4.1 执行增强版和选股系统工程壳
- 当前状态：{execution}
- 当前验证等级：{level}
- 用户验证状态：not_run
- 当前卡点：{'无，待用户检查和 GPT 审查。' if all_passed else '自动测试未全部通过。'}
- 已完成：工程壳、Agent-Memory、自动化脚本、测试和 ROUND-001 记录。
- 未完成：用户真实验证、GitHub 外循环、业务事实确认、真实选股能力开发。
- 下一步：用户检查本轮结果，并确认是否进入 GitHub 外循环。
- 关联 ROUND：{status.get('current_round')}
- 是否需要 GitHub 外循环：待用户确认
""", root)
        write_text(state_dir / "CURRENT_STATE.md", f"""# CURRENT_STATE

- 当前阶段：闭环基础设施初始化完成，等待用户检查。
- 当前可运行能力：生成 GPT_CONTEXT、生成 INDEX、验证 Agent-Memory、输出项目状态、开始 TASK/ROUND、结束 ROUND、创建 CHECKPOINT。
- 当前正常功能：规定自动化脚本和 unittest {'已通过' if all_passed else '未全部通过'}。
- 当前尚不存在的业务能力：真实数据采集、股票池生成、特征指标、筛选规则、回测验证、Agent 决策、报告生成、实盘接口。
- 当前限制：用户未真实验证，最高只能达到 L2_AGENT_TESTED。
- 最近一次测试：见 `{round_dir.relative_to(root).as_posix()}/ROUND.md`。
- 最近稳定 commit：{status.get('last_stable_commit')}
- 当前实验 commit：{git.get('head_commit')}
- 下一次优先验证：用户本地检查脚本输出和 Agent-Memory 一致性。
""", root)
        write_text(state_dir / "OPEN_ISSUES.md", "# OPEN_ISSUES\n\n当前无开放问题。\n" if all_passed else "# OPEN_ISSUES\n\n- 自动测试未全部通过，需查看 ROUND.md。\n", root)
        print(f"已完成 ROUND 收尾：{status.get('current_round')}，验证等级 {level}")
        return 0 if all_passed else 1
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

START_TASK = r'''
from __future__ import annotations
import argparse
from datetime import datetime
from memory_common import atomic_json, load_status, manifest, now_iso, repo_root, save_status, write_text, workspace_status, fail


def next_task(root):
    base = datetime.now().strftime("TASK-%Y%m%d")
    parent = root / "Agent-Memory" / "01-轮次记录"
    nums = [int(p.name.rsplit("-", 1)[-1]) for p in parent.glob(base + "-*") if p.name.rsplit("-", 1)[-1].isdigit()]
    return f"{base}-{(max(nums) if nums else 0) + 1:03d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="创建新 TASK。当前任务未关闭时默认拒绝。")
    parser.add_argument("--name", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        root = repo_root(); status = load_status(root)
        if status.get("execution_status") != "closed" and not args.force:
            fail("当前任务尚未关闭。若确认需要新任务，请使用 --force。")
        task = next_task(root); round_id = "ROUND-001"; git = workspace_status(root)
        task_dir = root / "Agent-Memory" / "01-轮次记录" / task; round_dir = task_dir / round_id
        round_dir.mkdir(parents=True, exist_ok=False)
        write_text(task_dir / "TASK.md", f"# {task}\n\n- 任务名称：{args.name}\n- 当前验证等级：L0_PLANNED\n- 关联 ROUND：{round_id}\n", root)
        write_text(round_dir / "ROUND.md", f"# {round_id}\n\n- 所属 TASK：{task}\n- 状态：已创建，待执行。\n", root)
        status.update({"current_task": task, "current_round": round_id, "execution_status": "task_started", "verification_level": "L0_PLANNED", "user_verification": "not_run", "branch": git["branch"], "base_commit": git["head_commit"], "observed_head_commit": git["head_commit"], "head_commit": git["head_commit"], "workspace_clean": git["workspace_clean"], "github_sync": "not_pushed", "open_issues": [], "last_updated": now_iso()})
        save_status(root, status)
        atomic_json(round_dir / "workspace_manifest.json", manifest(root, git["head_commit"], git["workspace_clean"]), root)
        print(f"已创建 TASK：{task}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

START_ROUND = r'''
from __future__ import annotations
import argparse
from memory_common import atomic_json, current_task_dir, load_status, manifest, now_iso, repo_root, save_status, workspace_status, write_text, fail


def next_round(task_dir):
    nums = [int(p.name.split("-")[-1]) for p in task_dir.glob("ROUND-*") if p.name.split("-")[-1].isdigit()]
    return f"ROUND-{(max(nums) if nums else 0) + 1:03d}"


def main() -> int:
    argparse.ArgumentParser(description="在当前 TASK 下创建下一轮 ROUND。").parse_args()
    try:
        root = repo_root(); status = load_status(root); task_dir = current_task_dir(root, status)
        round_id = next_round(task_dir); round_dir = task_dir / round_id; round_dir.mkdir(parents=True, exist_ok=False)
        git = workspace_status(root)
        status.update({"current_round": round_id, "execution_status": "round_started", "verification_level": "L0_PLANNED", "user_verification": "not_run", "branch": git["branch"], "base_commit": git["head_commit"], "observed_head_commit": git["head_commit"], "head_commit": git["head_commit"], "workspace_clean": git["workspace_clean"], "github_sync": "not_pushed", "open_issues": [], "round_started_at": now_iso(), "start_workspace_clean": git["workspace_clean"], "last_updated": now_iso()})
        save_status(root, status)
        write_text(round_dir / "ROUND.md", f"# {round_id}\n\n- 所属 TASK：{status.get('current_task')}\n- 起始时间：{status.get('round_started_at')}\n- 起始分支：{git.get('branch')}\n- 起始 HEAD：{git.get('head_commit')}\n", root)
        atomic_json(round_dir / "workspace_manifest.json", manifest(root, git["head_commit"], git["workspace_clean"]), root)
        print(f"已创建 ROUND：{round_id}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

CREATE_CHECKPOINT = r'''
from __future__ import annotations
import argparse
from datetime import datetime
from memory_common import load_status, now_iso, repo_root, save_status, write_text, fail


def next_id(root):
    base = datetime.now().strftime("CHECKPOINT-%Y%m%d")
    folder = root / "Agent-Memory" / "02-阶段快照"
    nums = [int(p.stem.rsplit("-", 1)[-1]) for p in folder.glob(base + "-*.md") if p.stem.rsplit("-", 1)[-1].isdigit()]
    return f"{base}-{(max(nums) if nums else 0) + 1:03d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="创建 CHECKPOINT 骨架。")
    parser.add_argument("--title", default="阶段快照")
    args = parser.parse_args()
    try:
        root = repo_root(); status = load_status(root); cid = next_id(root)
        content = f"""# {cid}

- 标题：{args.title}
- 覆盖 TASK：{status.get('current_task')}
- 覆盖 ROUND：{status.get('current_round')}
- 阶段目标：待确认
- 已完成内容：待确认
- 已解决问题：待确认
- 未解决问题：待确认
- 放弃方向：待确认
- 当前项目状态：{status.get('execution_status')}
- 重要技术决策：待确认
- 最近稳定 commit：{status.get('last_stable_commit')}
- 当前验证等级：{status.get('verification_level')}
- 下一阶段起点：待确认
"""
        write_text(root / "Agent-Memory" / "02-阶段快照" / f"{cid}.md", content, root)
        status["latest_checkpoint"] = cid; status["last_updated"] = now_iso(); save_status(root, status)
        print(f"已创建 CHECKPOINT：{cid}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

TESTS = r'''
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

    def test_new_task_and_round_reset_user_verification(self):
        for script_name in ["start_task.py", "start_round.py"]:
            with self.subTest(script=script_name):
                text = (SCRIPTS / script_name).read_text(encoding="utf-8")
                self.assertIn('"verification_level": "L0_PLANNED"', text)
                self.assertIn('"user_verification": "not_run"', text)

    def test_init_memory_templates_match_current_files(self):
        import init_memory  # noqa: E402

        expected_templates = {
            "MEMORY_COMMON": SCRIPTS / "memory_common.py",
            "BUILD_GPT_CONTEXT": SCRIPTS / "build_gpt_context.py",
            "BUILD_INDEX": SCRIPTS / "build_index.py",
            "GIT_SNAPSHOT": SCRIPTS / "git_snapshot.py",
            "VALIDATE_MEMORY": SCRIPTS / "validate_memory.py",
            "PROJECT_STATUS": SCRIPTS / "project_status.py",
            "FINISH_ROUND": SCRIPTS / "finish_round.py",
            "START_TASK": SCRIPTS / "start_task.py",
            "START_ROUND": SCRIPTS / "start_round.py",
            "CREATE_CHECKPOINT": SCRIPTS / "create_checkpoint.py",
            "TESTS": ROOT / "tests" / "test_memory_tools.py",
        }
        for attr, path in expected_templates.items():
            with self.subTest(template=attr):
                actual = getattr(init_memory, attr).lstrip("\n")
                expected = path.read_text(encoding="utf-8")
                self.assertEqual(actual, expected)

        for script_name in ["project_status", "validate_memory", "build_gpt_context"]:
            with self.subTest(bat_template=script_name):
                actual = init_memory.bat(script_name).replace("\r\n", "\n")
                expected = (SCRIPTS / f"{script_name}.bat").read_text(encoding="utf-8").replace("\r\n", "\n")
                self.assertEqual(actual, expected)

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
'''


def bat(script: str) -> str:
    return f'''@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0.."
set "SCRIPT=%~dp0{script}.py"

where python >nul 2>nul
if not errorlevel 1 goto run_python

where py >nul 2>nul
if not errorlevel 1 goto run_py

echo 错误：未找到 python 或 py，请先安装 Python 或将 Python 加入 PATH。
set "CODE=1"
goto done

:run_python
python "%SCRIPT%"
set "CODE=%ERRORLEVEL%"
goto done

:run_py
py "%SCRIPT%"
set "CODE=%ERRORLEVEL%"
goto done

:done
set "NO_PAUSE=%STOCKSELECTOR_NO_PAUSE: =%"
if not "%NO_PAUSE%"=="1" pause
exit /b %CODE%
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化或补齐 StockSelector Agent-Memory V4.1 基础设施。")
    parser.add_argument("--force", action="store_true", help="允许覆盖本初始化工具管理的文件。")
    args = parser.parse_args()
    try:
        root = repo_root()
        if root.name != PROJECT:
            raise RuntimeError(f"当前仓库名不是 {PROJECT}：{root}")
        branch, head = git_branch_head(root)
        started = now_iso()

        for directory in [
            "src/stock_selector/data", "src/stock_selector/screening", "src/stock_selector/features",
            "src/stock_selector/backtest", "src/stock_selector/agents", "src/stock_selector/reports",
            "src/stock_selector/common", "tests", "config", "data/raw", "data/interim", "data/processed",
            "outputs", "logs", "docs", "scripts/templates", "Agent-Memory/00-当前状态",
            f"Agent-Memory/01-轮次记录/{TASK_ID}/{ROUND_ID}", "Agent-Memory/02-阶段快照", "Agent-Memory/03-GPT导出",
        ]:
            (root / directory).mkdir(parents=True, exist_ok=True)
        for file in [
            "src/stock_selector/__init__.py", "src/stock_selector/data/__init__.py",
            "src/stock_selector/screening/__init__.py", "src/stock_selector/features/__init__.py",
            "src/stock_selector/backtest/__init__.py", "src/stock_selector/agents/__init__.py",
            "src/stock_selector/reports/__init__.py", "src/stock_selector/common/__init__.py",
            "tests/__init__.py", "data/raw/.gitkeep", "data/interim/.gitkeep", "data/processed/.gitkeep",
        ]:
            touch(root, file)

        managed = {
            "scripts/memory_common.py": MEMORY_COMMON,
            "scripts/build_gpt_context.py": BUILD_GPT_CONTEXT,
            "scripts/build_index.py": BUILD_INDEX,
            "scripts/git_snapshot.py": GIT_SNAPSHOT,
            "scripts/validate_memory.py": VALIDATE_MEMORY,
            "scripts/project_status.py": PROJECT_STATUS,
            "scripts/finish_round.py": FINISH_ROUND,
            "scripts/start_task.py": START_TASK,
            "scripts/start_round.py": START_ROUND,
            "scripts/create_checkpoint.py": CREATE_CHECKPOINT,
            "tests/test_memory_tools.py": TESTS,
            "scripts/validate_memory.bat": bat("validate_memory"),
            "scripts/build_gpt_context.bat": bat("build_gpt_context"),
            "scripts/project_status.bat": bat("project_status"),
            ".env.example": "# 仅保留变量名和空值示例，不写入真实密钥。\nSTOCK_SELECTOR_DATA_SOURCE=\nSTOCK_SELECTOR_API_KEY=\nSTOCK_SELECTOR_OUTPUT_DIR=\n",
            "pyproject.toml": "[project]\nname = \"stock-selector\"\nversion = \"0.1.0\"\ndescription = \"A neutral engineering shell for an A-share intelligent stock selection system.\"\nreadme = \"README.md\"\nrequires-python = \">=3.10\"\ndependencies = []\n",
            "README.md": "# StockSelector\n\nStockSelector 是一个面向 A 股智能选股系统的工程仓库。当前阶段只建立 Agent 项目闭环基础设施和中性工程目录壳，尚没有真实选股、回测、交易或报告生成能力。\n\n## 常用命令\n\n```powershell\npython scripts/project_status.py\npython scripts/build_gpt_context.py\npython scripts/build_index.py\npython scripts/validate_memory.py\npython -m unittest discover -s tests -v\n```\n\n当前业务事实如数据源、复权方案、股票池、指标、模型、交易周期和输出规则均为待确认。\n",
            "AGENTS.md": "# AGENTS.md\n\n## 开始任务前\n\n1. 阅读 `Agent-Memory/INDEX.md`。\n2. 阅读 `Agent-Memory/03-GPT导出/GPT_CONTEXT.md`、`Agent-Memory/00-当前状态/CURRENT_TASK.md`、`Agent-Memory/00-当前状态/CURRENT_STATE.md`。\n3. 阅读 `Agent-Memory/MEMORY_STATUS.json`。\n4. 获取当前工作目录、真实 Git 分支和起始 commit。\n5. 检查是否存在旧的未提交修改。\n6. 不得把旧轮次修改混入本轮而不说明。\n\n## 执行任务时\n\n1. 可以检查和修改与当前任务有关的仓库文件。\n2. 不得把推测写成已确认事实。\n3. 测试失败必须如实记录。\n4. 用户真实运行结果优先于自动测试。\n5. 不读取、不记录、不提交真实密钥。\n6. 不自动 Commit。\n7. 不自动 Push。\n8. 不擅自创建或切换分支。\n9. `MEMORY_STATUS.json` 是机器状态唯一权威来源。\n10. 不为填满模板而编造内容。\n\n## 结束任务前\n\n1. 新建或更新本轮 `ROUND.md`。\n2. 更新每轮必更新文件。\n3. 仅在事实变化时更新 `FILE_MAP.md`、`ENVIRONMENT.md`、`USAGE.md`、`PROJECT.md`。\n4. 更新 `MEMORY_STATUS.json`。\n5. 重新生成 `GPT_CONTEXT.md`。\n6. 重新生成 `INDEX.md`。\n7. 运行 `validate_memory.py`。\n8. 明确当前验证等级。\n9. 未经用户真实验证，不得标记 L4 或 L5。\n10. 停止，不自动 Commit，不自动 Push。\n",
            "docs/ARCHITECTURE.md": "# 架构说明\n\n当前仓库是中性的工程壳。各业务模块职责只是暂定边界，不代表数据源、指标、算法、模型或存储方案已经确定。\n",
            "docs/DEVELOPMENT_WORKFLOW.md": "# 开发工作流\n\n本地内循环：阅读 Agent-Memory，修改相关文件，运行生成、验证、状态和 unittest 命令，使用 `finish_round.py` 记录结果。\n\nGitHub 外循环需用户确认。Codex 不自动 `git add`、Commit、Push、Pull、Merge、Rebase，也不自动创建或切换分支。\n\n验证等级：`L0_PLANNED`、`L1_CHANGED`、`L2_AGENT_TESTED`、`L4_USER_VERIFIED`、`L5_CLOSED`。用户未验证时不得标记 L4 或 L5。\n",
            "docs/DESIGN_QUESTIONS.md": "# 下一阶段设计问题\n\n- 系统选股目标是什么。\n- 选股周期是什么。\n- 股票池范围是什么。\n- 数据源如何选择。\n- 复权方式如何选择。\n- 如何定义特征和指标。\n- 如何避免未来函数。\n- 如何避免数据泄漏。\n- 回测目标是什么。\n- Agent 承担什么职责。\n- 最终输出形式是什么。\n- 用户如何验收结果。\n",
            "config/README.md": "# config\n\n仅保存非敏感配置样例和待确认配置说明，不写入真实密钥。\n",
            "data/README.md": "# data\n\n数据目录用于未来放置原始数据、中间数据和处理后数据说明。当前数据源、复权方案和股票池均待确认。\n",
            "outputs/README.md": "# outputs\n\n输出目录用于未来保存自动生成结果。当前项目尚无真实选股输出能力。\n",
            "logs/README.md": "# logs\n\n日志目录用于未来保存本地运行日志，日志不得包含真实密钥或账号凭证。\n",
            "Agent-Memory/02-阶段快照/README.md": "# 阶段快照\n\n当前尚未创建正式 CHECKPOINT。\n",
            "scripts/templates/TASK.template.md": "# TASK ID\n\n- 任务名称：待确认\n- 目标：待确认\n- 背景：待确认\n- 已知事实：待确认\n- 待确认事项：待确认\n- 完成标准：待确认\n- 当前验证等级：L0_PLANNED\n- 关联 ROUND：待确认\n- GitHub 外循环要求：待确认\n- 风险：待确认\n",
            "scripts/templates/ROUND.template.md": "# ROUND ID\n\n- TASK ID：待确认\n- ROUND ID：待确认\n- 触发来源：待确认\n- 用户原始目标：待确认\n- 本轮目标：待确认\n- GPT 分析：待确认\n- Codex 实际修改：待确认\n- 修改文件：待确认\n- Git 状态锚点：待确认\n- 工作区清单：待确认\n- 测试命令：待确认\n- 预期结果：待确认\n- 实际结果：待确认\n- 退出码：待确认\n- 当前验证等级：待确认\n- 用户验证状态：not_run\n- 风险与回滚：待确认\n- 当前结论：待确认\n- 下一步：待确认\n- 是否进入 GitHub 外循环：待确认\n- 是否 Commit：否\n- 是否 Push：否\n",
            "scripts/templates/ISSUE.template.md": "# ISSUE ID\n\n- 标题：待确认\n- 类型：待确认\n- 首次出现 ROUND：待确认\n- 状态：open\n- 现象：待确认\n- 影响范围：待确认\n- 当前判断：待确认\n- 下一步：待确认\n- 关联源码：待确认\n- 是否阻塞：待确认\n",
            "scripts/templates/CHECKPOINT.template.md": "# CHECKPOINT ID\n\n- 覆盖 TASK：待确认\n- 覆盖 ROUND：待确认\n- 阶段目标：待确认\n- 已完成内容：待确认\n- 已解决问题：待确认\n- 未解决问题：待确认\n- 放弃方向：待确认\n- 当前项目状态：待确认\n- 重要技术决策：待确认\n- 最近稳定 commit：待确认\n- 当前验证等级：待确认\n- 下一阶段起点：待确认\n",
        }
        for module in ["data", "screening", "features", "backtest", "agents", "reports", "common"]:
            managed[f"src/stock_selector/{module}/README.md"] = f"# {module}\n\n当前仅保留暂定职责边界，不确定具体业务路线。相关业务事实均为待确认。\n"
        for path, content in managed.items():
            safe_write(root, path, content, args.force)

        gitignore = root / ".gitignore"
        gi = gitignore.read_text(encoding="utf-8", errors="replace") if gitignore.exists() else ""
        extra = "\n\n# StockSelector local secrets and generated artifacts\n.env\n.env.*\n!.env.example\n*.pem\n*.key\n*.p12\n*.pfx\n*.crt\n*.cer\n*.token\n*.secret\nlogs/*\n!logs/README.md\noutputs/*\n!outputs/README.md\ndata/raw/*\n!data/raw/.gitkeep\ndata/interim/*\n!data/interim/.gitkeep\ndata/processed/*\n!data/processed/.gitkeep\n*.tmp\n*.temp\n*.bak\n*.swp\n.vscode/\n.idea/\n"
        if "# StockSelector local secrets and generated artifacts" not in gi:
            safe_write(root, ".gitignore", gi.rstrip() + extra + "\n", True)

        status = {
            "schema_version": "4.1", "project": PROJECT, "project_name_zh": PROJECT_ZH,
            "current_task": TASK_ID, "current_round": ROUND_ID, "latest_checkpoint": None,
            "execution_status": "infrastructure_initializing", "verification_level": "L1_CHANGED",
            "user_verification": "not_run", "branch": branch, "base_commit": head,
            "head_commit": head, "last_stable_commit": head, "workspace_clean": False,
            "github_sync": "not_pushed", "last_updated": now_iso(), "open_issues": [],
            "notes": ["初始化开始前 HEAD 作为 last_stable_commit；本轮未执行 git add、commit、push、pull、merge、rebase、reset、clean，也未创建或切换分支。"],
            "round_started_at": started, "start_workspace_clean": True,
        }
        atomic_json(root / "Agent-Memory" / "MEMORY_STATUS.json", status)
        safe_write(root, f"Agent-Memory/01-轮次记录/{TASK_ID}/TASK.md", f"# {TASK_ID}\n\n- 任务名称：{TASK_NAME}\n- 目标：建立 Agent-Memory、闭环脚本、工程目录壳、Git 状态锚点和第一轮记录。\n- 背景：仓库处于初始阶段，当前不开发具体选股算法。\n- 已知事实：项目英文名 StockSelector，中文名 A股智能选股系统。\n- 待确认事项：数据源、复权方案、股票池、指标、筛选规则、回测框架、模型类型、Agent 决策方式、数据库、实盘接口、交易周期、输出排序规则。\n- 完成标准：规定脚本可运行，自动测试通过，状态文件一致，ROUND-001 如实记录。\n- 当前验证等级：L1_CHANGED\n- 关联 ROUND：{ROUND_ID}\n- GitHub 外循环要求：待用户确认，不自动 Commit，不自动 Push。\n- 风险：用户尚未真实验证，最高只能达到 L2_AGENT_TESTED。\n", True)
        safe_write(root, f"Agent-Memory/01-轮次记录/{TASK_ID}/{ROUND_ID}/ROUND.md", f"# {ROUND_ID}\n\n- 所属 TASK：{TASK_ID}\n- ROUND ID：{ROUND_ID}\n- 触发来源：用户初始化指令文件 `Codex初始化指令-StockSelector-V4.1.txt`\n- 用户目标：建立 Agent 项目闭环系统 V4.1 执行增强版和选股系统工程壳。\n- 本轮目标：创建文件、脚本、状态、测试并完成第一轮闭环记录。\n- 起始时间：{started}\n- 当前真实分支：{branch}\n- 开始 HEAD：{head}\n- 初始工作区状态：开始前已检查为干净。\n- 当前状态：文件已创建，等待自动化验证和最终收尾。\n", True)
        state_docs = {
            "PROJECT.md": "# PROJECT\n\n- 项目名称：StockSelector / A股智能选股系统\n- 项目定位：面向后续 A 股智能选股系统开发的工程仓库。\n- 核心目的：建立可持续迭代、可记录、可验证的项目闭环基础设施。\n- 当前主线：先建立 Agent-Memory 和工程壳，再由用户确认业务事实。\n- 当前阶段：闭环基础设施初始化。\n- 已确认事实：项目英文名、中文名、当前任务和当前不开发具体选股算法。\n- 待确认事项：数据源、复权方案、股票池、指标、筛选规则、回测框架、模型类型、Agent 决策方式、数据库、实盘接口、交易周期、输出排序规则。\n- 长期有效原则：不把推测写成事实，不写入真实密钥，不自动 Commit 或 Push。\n",
            "CURRENT_TASK.md": f"# CURRENT_TASK\n\n- 当前 TASK：{TASK_ID}\n- 任务名称：{TASK_NAME}\n- 当前状态：infrastructure_initializing\n- 当前验证等级：L1_CHANGED\n- 用户验证状态：not_run\n- 当前卡点：自动化测试尚未全部执行。\n- 已完成：初始状态文档正在建立。\n- 未完成：测试、最终 ROUND 记录、用户验证、GitHub 外循环。\n- 下一步：运行生成、验证、状态和 unittest 命令。\n- 关联 ROUND：{ROUND_ID}\n- 是否需要 GitHub 外循环：待用户确认\n",
            "CURRENT_STATE.md": f"# CURRENT_STATE\n\n- 当前阶段：闭环基础设施初始化中。\n- 当前可运行能力：脚本文件已创建，待实际执行验证。\n- 当前正常功能：待验证。\n- 当前尚不存在的业务能力：真实选股、数据采集、股票池、指标、回测、Agent 决策、报告输出、实盘接口。\n- 当前限制：用户尚未真实验证，最高只能达到 L2_AGENT_TESTED。\n- 最近一次测试：待执行。\n- 最近稳定 commit：{head}\n- 当前实验 commit：{head}\n- 下一次优先验证：运行规定自动测试。\n",
            "OPEN_ISSUES.md": "# OPEN_ISSUES\n\n当前无开放问题。\n",
            "FILE_MAP.md": "# FILE_MAP\n\n- `src/stock_selector/`：中性业务模块壳。\n- `scripts/`：闭环自动化脚本。\n- `tests/`：unittest 测试。\n- `Agent-Memory/`：项目记忆、状态和轮次记录。\n- `docs/`：架构、工作流、设计问题。\n- 当前结构疑点：业务路线待确认。\n- GPT 建议优先检查区域：`MEMORY_STATUS.json`、`scripts/`、`tests/test_memory_tools.py`。\n",
            "ENVIRONMENT.md": f"# ENVIRONMENT\n\n- 操作系统：{platform.platform()}\n- Python 实际版本：{platform.python_version()}\n- Git 实际版本：待脚本运行确认\n- 仓库路径：{root}\n- 当前分支：{branch}\n- 包管理方式：pyproject.toml，当前无第三方依赖\n- 环境变量名称：`STOCK_SELECTOR_DATA_SOURCE`、`STOCK_SELECTOR_API_KEY`、`STOCK_SELECTOR_OUTPUT_DIR`\n- 敏感信息说明：不得读取、记录、复制、显示或提交真实密钥、Token、Cookie、密码、私钥或证书内容。\n- 最后确认时间：{now_iso()}\n",
            "USAGE.md": "# USAGE\n\n- 查看状态：`python scripts/project_status.py`\n- 生成 GPT_CONTEXT：`python scripts/build_gpt_context.py`\n- 验证记忆：`python scripts/validate_memory.py`\n- 开始新 TASK：`python scripts/start_task.py --name \"任务名称\"`\n- 开始新 ROUND：`python scripts/start_round.py`\n- 结束 ROUND：`python scripts/finish_round.py --tests-json path\\to\\test_results.json`\n- 创建 CHECKPOINT：`python scripts/create_checkpoint.py --title \"阶段标题\"`\n- Windows BAT：`scripts\\validate_memory.bat`、`scripts\\build_gpt_context.bat`、`scripts\\project_status.bat`\n- 常见失败：Git 不在 PATH、JSON 损坏、用户未验证却出现 L4 或 L5。\n",
        }
        for name, content in state_docs.items():
            safe_write(root, f"Agent-Memory/00-当前状态/{name}", content, True)
        safe_write(root, "Agent-Memory/INDEX.md", "# Agent-Memory INDEX\n\n初始化占位，稍后由 `scripts/build_index.py` 覆盖生成。\n", True)
        safe_write(root, "Agent-Memory/03-GPT导出/GPT_CONTEXT.md", "# GPT_CONTEXT.md\n\n初始化占位，稍后由 `scripts/build_gpt_context.py` 覆盖生成。\n", True)
        current = parse_status(root)
        data = {
            "generated_at": now_iso(), "repository_root": str(root), "branch": current["branch"],
            "base_commit": head, "head_commit": current["head_commit"], "start_workspace_clean": True,
            "end_workspace_clean": current["workspace_clean"], "tracked_modified": current["tracked_modified"],
            "tracked_deleted": current["tracked_deleted"], "renamed": current["renamed"], "untracked": current["untracked"],
            "created_by_this_round": current["untracked"],
            "changed_by_this_round": current["tracked_modified"] + current["tracked_deleted"],
            "sha256": {p: sha256_file(root / p) for p in current["untracked"] + current["tracked_modified"] if sha256_file(root / p)},
            "git_available": current["git_available"], "git_warning": current["git_warning"],
            "git_add_executed": False, "committed": False, "pushed": False,
        }
        atomic_json(root / "Agent-Memory" / "01-轮次记录" / TASK_ID / ROUND_ID / "workspace_manifest.json", data)
        print("Agent-Memory V4.1 基础设施已初始化或补齐。")
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
