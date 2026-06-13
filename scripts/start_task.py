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
        status.update({"current_task": task, "current_round": round_id, "execution_status": "task_started", "verification_level": "L0_PLANNED", "branch": git["branch"], "base_commit": git["head_commit"], "observed_head_commit": git["head_commit"], "head_commit": git["head_commit"], "workspace_clean": git["workspace_clean"], "last_updated": now_iso()})
        save_status(root, status)
        atomic_json(round_dir / "workspace_manifest.json", manifest(root, git["head_commit"], git["workspace_clean"]), root)
        print(f"已创建 TASK：{task}")
        return 0
    except Exception as exc:
        fail(str(exc)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
