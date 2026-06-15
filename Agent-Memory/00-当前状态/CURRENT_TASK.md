# CURRENT_TASK

- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 可信研究与历史验证系统重构
- 当前 ROUND：ROUND-008
- 本轮目标：把历史回测从“固定当前候选池工程样例”重构为 point-in-time、策略身份清晰、数据边界透明、可继续扩展的可信研究底座。
- 当前状态：waiting_user_review
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：本轮代码、文档、真实验收、自动化测试、普通 commit 和 push 已完成；等待用户真实查看验收。
- 已完成：实时扫描策略与历史验证策略分离；新增 `historical_ohlcv_v1` 历史 OHLCV 固定因子体系；默认股票池不再使用当天候选 CSV 或今天成交额/涨跌幅/评分过滤过去；新增下一开盘执行、无量/涨跌停近似阻断、现金权重、基线比较和完整审计报告；新增可信性测试。
- 未完成：用户真实查看验收、真正无幸存者偏差历史股票池、历史上市/退市/停牌完整建模、行业/财务/资金流因子、正式组合构建和实盘接口。
- 最新真实验收：`python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 5 --rebalance-frequency weekly --execution-timing next_open --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source sina --universe-filter-mode broad_current_listed --universe-limit 30 --adjustment qfq --timeout 15 --retries 1` 于 2026-06-15 23:48:54 生成 `20260615_234854_minimal_backtest`。
- 最新可查看结果：`outputs/minimal_backtest/latest.html`；摘要 JSON：`outputs/minimal_backtest/20260615_234854_minimal_backtest/summary.json`；CSV：`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 最新验收结论：策略累计收益 -10.72%，沪深 300 +1.25%，股票池等权基线 -3.75%，20 日趋势单因子基线 -8.70%；当前结果证明可信回测链路可运行，不证明策略有效。
- GitHub 外循环：本轮普通 commit `2d664de4ccf8b5882e101c173a23c0e60f3eaf73` 已推送到 `origin/main`；未使用 force push，未创建或切换分支。
