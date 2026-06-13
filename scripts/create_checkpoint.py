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
