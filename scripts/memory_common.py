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
