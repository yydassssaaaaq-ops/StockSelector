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

## 核心修改

- 新增 `src/stock_selector/features/historical_factors.py`：定义 `historical_ohlcv_v1`，包含 20 日趋势、60 日趋势、20 日均线位置、20 日成交额中位数、20 日波动率、20 日最大回撤；每个因子记录字段、窗口、方向、缺失策略、标准化和数据风险。
- 新增 `src/stock_selector/backtest/execution.py`：集中处理下一开盘/下一收盘价格、无量、缺价、涨跌停近似阻断和延迟退出。
- 重构 `src/stock_selector/backtest/engine.py`：历史信号改用独立历史因子层，加入现金权重、执行阻断、股票池等权基线、20 日趋势单因子基线、策略身份和完整审计。
- 更新 `scripts/run_minimal_backtest.py`：默认股票池改为 `broad_current_listed`；新增 `--execution-timing` 和 `--universe-filter-mode`；CSV 和快照流动性过滤均显式标记研究局限。
- 更新 `src/stock_selector/reports/backtest_report.py`：HTML/JSON/CSV 输出新增策略身份、因子定义、基线指标、阻断列表、现金权重、因子覆盖、能证明/不能证明字段。
- 更新 `tests/test_minimal_backtest.py`：新增未来 K 线不污染过去信号、默认不走 CSV、窗口不足剔除、下一开盘执行、无量/停牌不能成交、涨跌停近似约束、部分无法成交保留现金、审计字段完整等测试。
- 更新 README、架构说明、回测使用说明和模块 README；明确 ROUND-007 18.78% 结果降级为固定当前候选 CSV 下的工程样例。

## 新旧逻辑本质区别

- 旧逻辑回答：“今天候选池里的股票过去表现如何？”
- 新逻辑回答：“站在每个历史信号日，只用当时已有日线因子，固定历史策略能形成什么候选、如何执行、相对基准和简单基线表现如何？”
- 旧逻辑用缺失因子动态重配维持实时评分器运行；新逻辑将实时扫描和历史研究拆成两套策略身份，不再把缺字段后的模型称为同一策略。
- 旧逻辑默认下一交易日收盘成交；新逻辑默认下一交易日开盘，并记录无量、涨跌停近似阻断、延迟退出和现金权重。

## 自动验证

- `python -m py_compile src\stock_selector\features\historical_factors.py src\stock_selector\backtest\execution.py src\stock_selector\backtest\engine.py src\stock_selector\reports\backtest_report.py scripts\run_minimal_backtest.py`：通过。
- `python -m unittest tests.test_minimal_backtest -v`：14 项通过。
- `python -m unittest discover -s tests -v`：61 项通过。
- 时间点可信性专项覆盖：修改信号日之后 K 线不改变该信号日候选；窗口不足剔除；默认历史回测不使用 CSV；实时和历史策略身份分离；下一交易日开盘执行；无量、涨跌停近似约束、现金权重和审计字段均可验证。

## 真实小规模验收

命令：

```powershell
python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 5 --rebalance-frequency weekly --execution-timing next_open --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source sina --universe-filter-mode broad_current_listed --universe-limit 30 --adjustment qfq --timeout 15 --retries 1
```

结果：

- run_id：`20260615_234854_minimal_backtest`
- 输出：`outputs/minimal_backtest/20260615_234854_minimal_backtest/report.html`、`summary.json`、`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`；`outputs/minimal_backtest/latest.html` 已指向该报告。
- 股票池：新浪当前宽 A 股代码池前 30 只；`universe.csv` 仅含 code/name/exchange/board，不含今天成交额、涨跌幅、评分或候选排名。
- 股票历史源：腾讯前复权日 K；30 只股票历史全成功，缓存命中 30，股票失败 0。
- 基准源：东财沪深 300 请求失败，真实回退 Yahoo Finance `000300.SS`；失败记录进入 `data_failures` 和 `failed_benchmark_requests=1`。
- 策略累计收益：-10.72%；沪深 300：+1.25%；股票池等权基线：-3.75%；20 日趋势单因子基线：-8.70%。
- 结论：可信回测链路可运行；当前有限样本未能同时优于基准和简单基线，不证明策略有效。

## 当前能说明什么

- 程序可在固定历史策略身份下完成 point-in-time 因子、排名、执行、基线比较和审计输出。
- 当前自动测试能证明明显未来数据污染不会改变过去信号。
- 默认历史回测不再使用当天候选 CSV 向前回测，也不使用今天成交额/涨跌幅/评分筛过去股票池。

## 当前不能说明什么

- 不能证明 `historical_ohlcv_v1` 长期有效、可实盘盈利或优于简单规则。
- 不能消除当前仍上市股票池带来的幸存者偏差。
- 不能证明日线级涨跌停近似等于真实盘口可成交性。
- 不能覆盖行业、财务、资金流、历史上市/退市完整股票池和正式组合构建。

## 下一阶段最值得建设的方向

- 建设真正 point-in-time 的历史股票池，包括上市、退市、停牌和板块制度变化。
- 引入更完整的历史可得数据源，优先补齐行业、财务、换手率/流通市值、真实成交额口径和可成交性字段。
- 建立组合构建和风险约束层，让策略验证从 Top N 等权升级为可解释的组合研究。

## Git 状态

- 本轮代码、文档和 Agent-Memory 修改已提交。
- 普通 commit：`2d664de4ccf8b5882e101c173a23c0e60f3eaf73`（提交信息：`重构可信历史验证底座`）。
- Push：`git push origin main` 成功，`2f1136e..2d664de main -> main`。
- 未使用 force push；未创建或切换分支。
- 2026-06-16 00:01 后进行记忆状态同步，因此会产生一个后续记忆同步提交记录 push 已成功。
