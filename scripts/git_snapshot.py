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
