# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：StockSelector / A股智能选股系统
- 当前 TASK：TASK-20260612-001
- 当前 ROUND：ROUND-007
- 执行状态：waiting_github_sync
- 验证等级：L2_AGENT_TESTED
- 用户验证：not_run
- GitHub 同步：push_failed_network
- 当前真实分支：main
- 当前真实 HEAD：36dac1328e642cb2c7f84c174a102fcf210059ac
- 状态文件观察到的 HEAD：36dac1328e642cb2c7f84c174a102fcf210059ac
- 工作区干净：False

## B. Agent 解释

### 当前任务
# CURRENT_TASK
- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 工程闭环与第一条真实 A 股选股业务链
- 当前 ROUND：ROUND-007
- 本轮目标：把真实行情规则筛选升级为第一条可被历史数据验证的最小回测闭环。
- 当前状态：waiting_github_sync
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：本地 commit 已完成，但 GitHub push 连续三次失败，错误为 HTTPS 连接重置或无法连接到 github.com:443；等待网络恢复后重试普通 push。
- 已完成：中立行情模型拆分、缺失因子动态权重、腾讯前复权历史日线、东财历史日线可选源、Yahoo 沪深 300 基准回退、最小横截面回测引擎、集中指标、HTML/JSON/CSV 报告、真实回测样例和自动化测试。
- 未完成：用户真实查看验收、无幸存者偏差历史股票池、停牌/涨跌停可成交性、行业/财务因子、正式组合构建、实盘接口。
- 本轮真实样例：`python scripts\run_real_a_share_screen.py --top 30` 于 2026-06-15 16:48:53 生成 `20260615_164853_sina_snapshot`，读取真实行情 5527 条，过滤后 1665 条，输出候选 30 条。
- 最新回测样例：`python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 10 --rebalance-frequency weekly --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source csv --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv --universe-limit 20 --adjustment qfq --timeout 20 --retries 3` 于 2026-06-15 18:15:58 生成 `20260615_181558_minimal_backtest`。
- 最新可查看结果：`outputs/minimal_backtest/latest.html`；摘要 JSON：`outputs/minimal_backtest/20260615_181558_minimal_backtest/summary.json`；CSV：`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- GitHub 外循环：本地 commit `36dac1328e642cb2c7f84c174a102fcf210059ac` 已创建；push 未成功，未使用 force push，不创建或切换分支。

### 当前状态
# CURRENT_STATE
- 当前阶段：第一条真实 A 股选股业务链已从快照筛选推进到最小历史回测闭环。
- 当前可运行能力：真实 A 股行情快照采集、规则筛选打分、候选 CSV、原始行情 CSV、摘要 JSON、HTML 报告；真实历史日线获取、前复权缓存、信号生成、收益回放、沪深 300 基准比较、回测 HTML/JSON/CSV 报告；历史案卷库导入、SQLite 索引、文件监控和本地工作台仍保留可用。
- 当前正常命令：`python scripts\run_real_a_share_screen.py --top 30`、`python scripts\run_minimal_backtest.py`、`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前真实行情数据：新浪市场中心 `hs_a` 快照，2026-06-15 真实样例读取 5527 条 A 股行情，过滤后 1665 条，输出 Top 30；Top 5 为 000725 京东方Ａ、002185 华天科技、000630 铜陵有色、000021 深科技、000737 北方铜业。
- 当前真实样例输出：`outputs/a_share_screen/latest.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/report.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`、`outputs/a_share_screen/20260615_164853_sina_snapshot/summary.json`、`data/raw/a_share_quotes/20260615_164853_sina_snapshot_quotes.csv`。
- 当前真实回测样例：`20260615_181558_minimal_backtest`，区间 2026-01-01 至 2026-06-15，股票池为上一轮真实新浪候选 CSV 前 20 只，股票历史源为腾讯前复权日 K，基准为沪深 300；东财基准源断连后回退 Yahoo Finance `000300.SS`。
- 当前回测结果：有效期数 21；策略累计收益 18.78%，年化收益 53.13%，最大回撤 23.15%，年化波动率 48.54%，夏普 1.127，胜率 61.90%，平均单期收益 1.05%，最好单期 13.75%，最差单期 -12.62%，平均换手 99.05%，交易次数 215；沪深 300 累计收益 2.13%，最大回撤 7.76%；相对基准超额收益 16.65%。结论为有限样本内策略累计收益高于基准，但回撤风险需要继续检查。
- 当前规则边界：排除 ST/退市整理和新股前缀样本；快照筛选要求价格、成交额、换手率、涨跌幅、振幅在阈值内；历史回测使用信号日收盘后可得日线字段并默认下一交易日收盘成交。缺失主力资金、估值或换手率时不按 0 分处理，而是对可用因子动态重新归一并记录完整性。
- 当前尚不存在的业务能力：无幸存者偏差全历史股票池、行业中性化、财务因子、涨跌停/停牌可成交性精细建模、正式组合构建、涨跌预测、实盘交易、投资建议。
- 当前限制：用户尚未真实查看本轮报告，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- Git 状态：本地 commit `36dac1328e642cb2c7f84c174a102fcf210059ac` 已创建；GitHub push 连续三次失败，错误为 HTTPS 连接重置或无法连接到 github.com:443，需网络恢复后重试普通 push。
- 最近一次完整测试：`python -m unittest discover -s tests -v`，56 项通过。
- 最近稳定 commit：36dac1328e642cb2c7f84c174a102fcf210059ac
- 下一次优先事项：建设无幸存者偏差的历史股票池和停牌/涨跌停可成交性处理，扩大股票池并对比东财字段完整源恢复后的结果。

### 开放问题
# OPEN_ISSUES
当前开放问题：
- GitHub push 失败：HTTPS 连接被重置或无法连接到 github.com:443；本地 commit 已保留，需网络恢复后重试普通 push。
非阻塞观察：
- 东财 push2 列表接口本轮真实运行时出现连接断开/502，因此默认真实样例改用新浪市场中心 `hs_a`；东财采集器保留为可选源。
- 新浪源不提供主力净流入字段，报告中相关字段保持空值，不使用模拟值补齐。
- 东财 `push2his` 历史日 K 在本轮真实回测时对股票和沪深 300 基准均出现连接断开；股票历史默认改用腾讯前复权日 K，沪深 300 基准回退 Yahoo Finance `000300.SS`。
- 腾讯历史源不提供换手率、主力资金和估值字段；回测评分已用动态可用因子权重降置信处理，报告中记录缺失因子和完整性。
- 当前回测股票池来自上一轮真实新浪候选 CSV 的当前样本，历史退市股票未纳入，存在幸存者偏差。
- 当前回测结果未经用户真实查看验收，不得视为投资建议或交易信号。

### 最近 ROUND
# ROUND-007
## 基本信息
- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-007
- 触发来源：用户要求把当前真实 A 股规则筛选升级为可被历史数据验证的最小回测闭环。
- 本轮目标：完成历史数据获取 -> 信号生成 -> 收益回放 -> 基准比较 -> 报告输出 -> 自动测试。
- 起始分支：main
- 起始 HEAD：ed4d3f28c6b57879d816822504cc828e67a9d4e8
- 是否切换或新建分支：否
## 架构审计结论
- 发现 `AShareQuote` 绑定在 `data/eastmoney.py` 中，新浪源反向依赖东财模块；本轮已拆到 `data/models.py`。
- 新浪和东财快照字段已统一映射到中立 `AShareQuote`。
- 原评分逻辑会把缺失主力资金按 0 分处理，导致新浪源分数不可比；本轮改为动态可用因子权重并记录缺失因子、有效权重和完整性。
- 新浪源主力资金为空时不再假装总分完全可比。
- 当前筛选规则已可通过历史 `DailyBar.to_quote()` 在历史日期重复执行；历史源缺失换手率时需显式允许并降置信。
- 回测报告记录数据源、请求/复权方式、参数、样本数量、失败原因和偏差说明。
## 本轮修改
- 新增 `src/stock_selector/data/models.py`：中立行情模型。
- 新增 `src/stock_selector/data/eastmoney_history.py`：东财历史日 K，支持前复权/后复权/不复权、缓存和失败记录。
- 新增 `src/stock_selector/data/tencent_history.py`：腾讯历史日 K，当前默认股票历史源，支持前复权。
- 新增 `src/stock_selector/data/yahoo_history.py`：Yahoo Finance 指数日线，作为沪深 300 基准回退。
- 新增 `src/stock_selector/backtest/engine.py`：最小横截面选股回测引擎。
- 新增 `src/stock_selector/backtest/metrics.py`：集中管理收益、风险、胜率、换手和超额收益指标。
- 新增 `src/stock_selector/reports/backtest_report.py`：生成 HTML/JSON/CSV 回测报告。

### 工作区摘要

tracked 修改：
- Agent-Memory/00-当前状态/CURRENT_STATE.md
- Agent-Memory/00-当前状态/CURRENT_TASK.md
- Agent-Memory/00-当前状态/OPEN_ISSUES.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-007/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-007/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-007/workspace_manifest.json
- Agent-Memory/MEMORY_STATUS.json

未跟踪文件：
- 无

## C. 用户验证

- 用户验证状态：not_run
- 当前不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 下一步建议：任务完成、测试通过且工作区无明显异常后，可由 Codex 在当前分支 Commit 并 Push；同步前不得标记 L5。

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-007/`
- `scripts/`
- `tests/test_memory_tools.py`
