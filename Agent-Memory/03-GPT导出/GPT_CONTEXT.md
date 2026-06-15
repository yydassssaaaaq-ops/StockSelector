# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：StockSelector / A股智能选股系统
- 当前 TASK：TASK-20260612-001
- 当前 ROUND：ROUND-008
- 执行状态：waiting_commit_push
- 验证等级：L2_AGENT_TESTED
- 用户验证：not_run
- GitHub 同步：not_pushed
- 当前真实分支：main
- 当前真实 HEAD：2f1136eee9600ad056967434c74a9aca85a1a521
- 状态文件观察到的 HEAD：2f1136eee9600ad056967434c74a9aca85a1a521
- 工作区干净：False

## B. Agent 解释

### 当前任务
# CURRENT_TASK
- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 可信研究与历史验证系统重构
- 当前 ROUND：ROUND-008
- 本轮目标：把历史回测从“固定当前候选池工程样例”重构为 point-in-time、策略身份清晰、数据边界透明、可继续扩展的可信研究底座。
- 当前状态：waiting_commit_push
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：本轮代码、文档、真实验收和自动化测试已完成；仍需按协作规则执行普通 commit 和 push，并等待用户真实查看验收。
- 已完成：实时扫描策略与历史验证策略分离；新增 `historical_ohlcv_v1` 历史 OHLCV 固定因子体系；默认股票池不再使用当天候选 CSV 或今天成交额/涨跌幅/评分过滤过去；新增下一开盘执行、无量/涨跌停近似阻断、现金权重、基线比较和完整审计报告；新增可信性测试。
- 未完成：用户真实查看验收、真正无幸存者偏差历史股票池、历史上市/退市/停牌完整建模、行业/财务/资金流因子、正式组合构建和实盘接口。
- 最新真实验收：`python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 5 --rebalance-frequency weekly --execution-timing next_open --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source sina --universe-filter-mode broad_current_listed --universe-limit 30 --adjustment qfq --timeout 15 --retries 1` 于 2026-06-15 23:48:54 生成 `20260615_234854_minimal_backtest`。
- 最新可查看结果：`outputs/minimal_backtest/latest.html`；摘要 JSON：`outputs/minimal_backtest/20260615_234854_minimal_backtest/summary.json`；CSV：`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 最新验收结论：策略累计收益 -10.72%，沪深 300 +1.25%，股票池等权基线 -3.75%，20 日趋势单因子基线 -8.70%；当前结果证明可信回测链路可运行，不证明策略有效。
- GitHub 外循环：本轮尚未提交/推送；禁止 force push，不创建或切换分支。

### 当前状态
# CURRENT_STATE
- 当前阶段：历史回测链路已从 ROUND-007 的最小工程样例升级为 ROUND-008 的可信研究底座。
- 当前可运行能力：真实 A 股行情快照采集、实时规则扫描、原始行情/候选 CSV/JSON/HTML 输出；历史 OHLCV 固定因子计算、point-in-time 信号、横截面百分位评分、下一开盘执行、日线级不可成交近似、沪深 300/股票池等权/单因子基线比较、HTML/JSON/CSV 审计报告；历史案卷库导入、SQLite 索引、文件监控和本地工作台仍保留可用。
- 当前正常命令：`python scripts\run_real_a_share_screen.py --top 30`、`python scripts\run_minimal_backtest.py`、`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前实时扫描策略：`screening/momentum_liquidity.py`，用于实时快照，不作为历史验证策略复用。
- 当前历史验证策略：`historical_ohlcv_v1`，只使用信号日及以前 OHLCV 派生因子；因子包括 20 日趋势、60 日趋势、20 日均线位置、20 日成交额中位数、20 日波动率、20 日最大回撤；固定权重，横截面百分位标准化，窗口不足或数据缺失时剔除本期样本。
- 当前默认股票池：`broad_current_listed`，通过当前快照仅取得仍上市 A 股代码、名称、交易所和板块；不使用今天成交额、涨跌幅、实时评分或候选排名过滤过去；仍存在幸存者偏差。
- 当前显式调试模式：`--universe-source csv` 会标记为 `csv_debug`；`--universe-filter-mode snapshot_liquidity` 会标记为当前快照流动性过滤诊断模式，均不应作为默认策略验证证据。
- 当前执行假设：信号日收盘后形成候选；默认下一交易日开盘执行；持有到下一调仓对应的下一交易日开盘；交易成本和滑点按换手扣减；无量、缺价、涨停难买、跌停难卖和延迟退出记录在报告中；部分无法成交的权重保留为现金。
- 当前真实验收输出：`outputs/minimal_backtest/latest.html`、`outputs/minimal_backtest/20260615_234854_minimal_backtest/report.html`、`summary.json`、`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 当前真实验收数据：新浪 `hs_a` 快照读取 5527 条，默认宽代码池前 30 只；腾讯前复权日 K 股票历史 30/30 成功，缓存命中 30；东财沪深 300 基准请求失败后回退 Yahoo Finance `000300.SS`，记录 `failed_benchmark_requests=1`。
- 当前真实验收结果：2026-01-01 至 2026-06-15，周频 Top5，21 个回测窗口；策略累计收益 -10.72%，年化收益 -24.49%，最大回撤 13.40%，夏普 -1.417，胜率 14.29%，交易次数 36，平均换手 34.29%；沪深 300 累计收益 +1.25%；股票池等权基线 -3.75%；20 日趋势单因子基线 -8.70%。
- 当前结论边界：本轮结果证明可信历史验证链路可运行，并能揭示策略未跑赢基准/简单基线；不证明策略有效、不构成投资建议、不构成交易信号。
- 当前自动测试：`python -m unittest discover -s tests -v`，61 项通过；`tests.test_minimal_backtest` 当前 14 项通过，覆盖未来数据隔离、默认非 CSV 股票池、窗口不足、下一开盘执行、无量/涨跌停约束、现金权重和审计字段。
- 当前限制：用户尚未真实查看本轮报告，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- Git 状态：本轮起始 HEAD 为 `2f1136eee9600ad056967434c74a9aca85a1a521`，起始工作区干净；当前存在本轮未提交修改，待普通 commit/push。
- 最近稳定 commit：2f1136eee9600ad056967434c74a9aca85a1a521
- 下一次优先事项：建设真正 point-in-time 历史股票池；补齐行业/财务/流通市值/换手率/真实成交额历史字段；建立组合构建和风险约束层。

### 开放问题
# OPEN_ISSUES
当前开放问题：
- GitHub 同步尚未完成：本轮修改尚未 commit/push；需在测试和记忆校验通过后执行普通 git add、commit、push，不得 force push。
- 用户尚未真实查看 ROUND-008 报告，因此不得标记 L4_USER_VERIFIED 或 L5_CLOSED。
非阻塞观察：
- 默认股票池已不再使用当天候选 CSV 或今天成交额过滤过去，但仍是当前仍上市代码池过渡方案，历史退市股票和历史成分变化尚未纳入，仍存在幸存者偏差。
- 东财 `push2his` 对沪深 300 基准在本轮真实验收中仍出现连接断开，已真实回退 Yahoo Finance `000300.SS` 并记录失败；东财历史源保留为可选源。
- 腾讯历史源成交额由成交手数乘价格派生，换手率、主力资金和估值字段仍缺失；ROUND-008 历史策略不再使用这些实时字段伪装成同一模型。
- 日线级涨跌停/停牌处理只是近似，不能替代逐笔盘口或真实撮合数据。
- ROUND-007 的 18.78% 回测结果已保留为固定当前候选 CSV 下的历史工程样例，不能作为策略有效性证据。

### 最近 ROUND
# ROUND-008
## 基本信息
- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-008
- 任务名称：StockSelector 可信研究与历史验证系统重构
- 触发来源：用户要求将当前最小历史回测升级为时间点可信、策略身份清晰、数据边界透明的研究底座。
- 本轮起始分支：main
- 本轮起始 HEAD：2f1136eee9600ad056967434c74a9aca85a1a521
- 起始工作区是否干净：是
- 是否创建或切换分支：否
## 独立审计结论
- 用户指出的核心问题成立：ROUND-007 的 `20260615_181558_minimal_backtest` 使用 2026-06-15 当天候选 CSV 前 20 只股票向前回测，只能说明旧程序能运行，不能作为策略有效性证据。
- 用户指出的策略身份漂移成立：旧历史回测复用实时 `momentum_liquidity` 评分器，并通过缺失因子动态重配继续打分；历史源缺少主力资金、估值、换手率等字段时，实际已不再是同一套实时策略。
- 用户指出的单日动量倾向成立：旧历史回测主要依赖历史日线 `to_quote()` 转成快照字段，趋势结构和窗口质量不足。
- 用户指出的执行简化成立：旧引擎仅支持 `next_close`，没有独立记录无量、缺价、涨跌停近似阻断、现金权重和延迟退出。
- 额外发现：报告审计字段不足以同时说明股票池来源、策略身份、因子覆盖、基线比较和“能证明/不能证明”边界。
- 额外发现：记忆文件记录的上一轮观察 HEAD 为 `36dac1328e642cb2c7f84c174a102fcf210059ac`，但本轮真实起始 HEAD 已是 `2f1136eee9600ad056967434c74a9aca85a1a521`；这是上一轮后续本地 commit，非本轮旧改动混入。本轮起始工作区干净。
## 设计取舍
- 保留实时扫描策略 `momentum_liquidity`，但不再把它伪装成历史验证策略。
- 新增固定历史策略 `historical_ohlcv_v1`，只使用信号日及以前 OHLCV 派生因子，并用固定权重和横截面百分位评分。
- 默认股票池改为当前仍上市宽 A 股代码池过渡方案，只用当前快照中的代码、名称、交易所、板块，不使用今天成交额、涨跌幅、实时评分或候选排名过滤过去。
- 固定 CSV 股票池保留为 `csv_debug` 显式调试模式，报告中标记其不能作为策略验证证据。
- 默认执行改为下一交易日开盘，日线近似处理无量、缺价、涨停难买、跌停难卖和延迟退出；无法精确替代盘口可成交性，报告中如实披露。
- 本轮没有引入 LLM 选股、机器学习调参、实盘交易或收益优化参数搜索。

### 工作区摘要

tracked 修改：
- Agent-Memory/00-当前状态/CURRENT_STATE.md
- Agent-Memory/00-当前状态/CURRENT_TASK.md
- Agent-Memory/00-当前状态/ENVIRONMENT.md
- Agent-Memory/00-当前状态/FILE_MAP.md
- Agent-Memory/00-当前状态/OPEN_ISSUES.md
- Agent-Memory/00-当前状态/PROJECT.md
- Agent-Memory/00-当前状态/USAGE.md
- Agent-Memory/03-GPT导出/GPT_CONTEXT.md
- Agent-Memory/INDEX.md
- Agent-Memory/MEMORY_STATUS.json
- README.md
- docs/ARCHITECTURE.md
- docs/minimal_backtest_usage.md
- scripts/run_minimal_backtest.py
- src/stock_selector/backtest/README.md
- src/stock_selector/backtest/engine.py
- src/stock_selector/features/README.md
- src/stock_selector/reports/backtest_report.py
- tests/test_minimal_backtest.py

未跟踪文件：
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-008/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-008/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-008/workspace_manifest.json
- src/stock_selector/backtest/execution.py
- src/stock_selector/features/historical_factors.py

## C. 用户验证

- 用户验证状态：not_run
- 当前不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 下一步建议：检查自动验证和真实样例结果；若通过且工作区无明显异常，可在当前分支 Commit 并 Push。

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-008/`
- `scripts/`
- `tests/test_memory_tools.py`
