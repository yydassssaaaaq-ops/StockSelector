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
- 是否 Commit：`finish_round.py` 不执行 Git 操作；任务完成、测试通过且工作区无明显异常后可另行记录真实 Commit。
- 是否 Push：`finish_round.py` 不执行 Git 操作；Push 结果以本轮最终记录为准。
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

检查本轮文件、状态和测试输出；若通过且工作区无明显异常，可在当前分支 Commit 并 Push。
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
- 下一步：检查本轮结果；若通过且工作区无明显异常，可在当前分支 Commit 并 Push。
- 关联 ROUND：{status.get('current_round')}
- 是否需要 GitHub 外循环：测试通过且工作区无明显异常后可执行
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
