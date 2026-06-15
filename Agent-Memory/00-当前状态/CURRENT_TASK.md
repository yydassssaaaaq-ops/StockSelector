# CURRENT_TASK

- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 工程闭环与第一条真实 A 股选股业务链
- 当前 ROUND：ROUND-007
- 本轮目标：把真实行情规则筛选升级为第一条可被历史数据验证的最小回测闭环。
- 当前状态：waiting_user_review
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：无阻塞问题；等待用户查看 `outputs/minimal_backtest/latest.html` 和结构化结果。
- 已完成：中立行情模型拆分、缺失因子动态权重、腾讯前复权历史日线、东财历史日线可选源、Yahoo 沪深 300 基准回退、最小横截面回测引擎、集中指标、HTML/JSON/CSV 报告、真实回测样例和自动化测试。
- 未完成：用户真实查看验收、无幸存者偏差历史股票池、停牌/涨跌停可成交性、行业/财务因子、正式组合构建、实盘接口。
- 本轮真实样例：`python scripts\run_real_a_share_screen.py --top 30` 于 2026-06-15 16:48:53 生成 `20260615_164853_sina_snapshot`，读取真实行情 5527 条，过滤后 1665 条，输出候选 30 条。
- 最新回测样例：`python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 10 --rebalance-frequency weekly --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source csv --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv --universe-limit 20 --adjustment qfq --timeout 20 --retries 3` 于 2026-06-15 18:15:58 生成 `20260615_181558_minimal_backtest`。
- 最新可查看结果：`outputs/minimal_backtest/latest.html`；摘要 JSON：`outputs/minimal_backtest/20260615_181558_minimal_backtest/summary.json`；CSV：`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- GitHub 外循环：规则已改为测试通过且工作区无明显异常后可由 Codex 在当前分支 Commit 并 Push；不得 force push，不创建或切换分支。
