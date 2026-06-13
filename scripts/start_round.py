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
        status.update({"current_round": round_id, "execution_status": "round_started", "verification_level": "L0_PLANNED", "branch": git["branch"], "base_commit": git["head_commit"], "observed_head_commit": git["head_commit"], "head_commit": git["head_commit"], "workspace_clean": git["workspace_clean"], "round_started_at": now_iso(), "start_workspace_clean": git["workspace_clean"], "last_updated": now_iso()})
        save_status(root, status)
        write_text(round_dir / "ROUND.md", f"# {round_id}\n\n- 所属 TASK：{status.get('current_task')}\n- 起始时间：{status.get('round_started_at')}\n- 起始分支：{git.get('branch')}\n- 起始 HEAD：{git.get('head_commit')}\n", root)
        atomic_json(round_dir / "workspace_manifest.json", manifest(root, git["head_commit"], git["workspace_clean"]), root)
        print(f"已创建 ROUND：{round_id}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
