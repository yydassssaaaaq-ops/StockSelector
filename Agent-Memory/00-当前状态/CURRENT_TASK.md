# CURRENT_TASK

- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 工程闭环与第一条真实 A 股选股业务链
- 当前 ROUND：ROUND-006
- 本轮目标：不再扩建空基础设施，直接建设一条真实行情快照到规则筛选再到可查看报告的最小 A 股选股业务闭环。
- 当前状态：waiting_user_review
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：无阻塞问题；等待用户查看 `outputs/a_share_screen/latest.html` 和候选 CSV。
- 已完成：新浪 `hs_a` 真实行情采集、东财可选采集器、动量/流动性/估值/波动规则筛选、HTML/CSV/JSON 报告、真实样例运行、自动化测试、协作规则更新。
- 未完成：用户真实查看验收、历史回测、复权行情、行业/财务因子、正式投资组合构建、实盘接口。
- 本轮真实样例：`python scripts\run_real_a_share_screen.py --top 30` 于 2026-06-15 16:48:53 生成 `20260615_164853_sina_snapshot`，读取真实行情 5527 条，过滤后 1665 条，输出候选 30 条。
- 最新可查看结果：`outputs/a_share_screen/latest.html`；候选 CSV：`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`。
- GitHub 外循环：规则已改为测试通过且工作区无明显异常后可由 Codex 在当前分支 Commit 并 Push；不得 force push，不创建或切换分支。
