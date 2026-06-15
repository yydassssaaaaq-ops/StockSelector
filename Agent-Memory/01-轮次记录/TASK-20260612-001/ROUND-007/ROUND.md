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
- 新增 `scripts/run_minimal_backtest.py`：可复现 CLI。
- 新增 `tests/test_minimal_backtest.py`：覆盖公共模型、字段映射、复权缓存、日期错位、防未来函数、交易成本、收益/回撤、缺失因子、失败不中断、报告生成、缓存命中、异常数据和基准对齐。
- 更新 `src/stock_selector/screening/momentum_liquidity.py`：评分动态权重和历史缺失换手率开关。
- 更新 README、模块 README、`docs/a_share_screen_usage.md`、新增 `docs/minimal_backtest_usage.md`。
- 更新 `.gitignore` 忽略 `data/cache/` 历史行情缓存。

## 真实数据运行记录

- 东财探针：`600000` 和沪深 300 在 `2025-01-01` 至 `2026-06-15` 曾返回 349 根日线，确认 `fqt=1` 前复权参数可用。
- 第一次真实回测：`python scripts\run_minimal_backtest.py --start-date 2025-12-01 --end-date 2026-06-15 --top-n 10 --rebalance-frequency weekly --transaction-cost 0.001 --slippage 0.0005 --universe-source sina --universe-limit 60 --universe-min-amount 800000000 --adjustment qfq --timeout 20`，股票池选出 60 只后，东财沪深 300 基准请求 `RemoteDisconnected`，退出码 1。
- 第二次真实回测：同区间收缩到 30 只后，命令被 180 秒工具超时中断，退出码 124。
- 单票诊断：东财 `000725` 历史日 K 连续断连，确认不能依赖单一东财历史源完成本轮。
- 备选源诊断：腾讯前复权日 K 返回真实 OHLC 和成交量；Yahoo Finance 返回沪深 300 `000300.SS` 指数日线。
- 最终真实回测命令：`python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 10 --rebalance-frequency weekly --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source csv --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv --universe-limit 20 --adjustment qfq --timeout 20 --retries 3`
- 最终 run_id：`20260615_181558_minimal_backtest`
- 股票池：上一轮真实新浪候选 CSV 前 20 只。
- 股票历史源：腾讯前复权日 K。
- 基准：沪深 300；东财指数日 K 失败后回退 Yahoo Finance `000300.SS`。
- 有效期数：21。
- 策略累计收益：18.78%；年化收益：53.13%；最大回撤：23.15%；年化波动率：48.54%；夏普：1.127；胜率：61.90%；平均单期收益：1.05%；最好单期：13.75%；最差单期：-12.62%；平均换手：99.05%；交易次数：215。
- 基准累计收益：2.13%；年化收益：5.35%；最大回撤：7.76%；年化波动率：17.28%；夏普：0.388；胜率：52.38%。
- 相对基准超额收益：16.65%。
- 报告结论：有限样本内策略累计收益高于基准，但回撤风险需要继续检查。

## 输出文件

- HTML：`outputs/minimal_backtest/20260615_181558_minimal_backtest/report.html`
- latest：`outputs/minimal_backtest/latest.html`
- JSON：`outputs/minimal_backtest/20260615_181558_minimal_backtest/summary.json`
- CSV：`outputs/minimal_backtest/20260615_181558_minimal_backtest/periods.csv`
- CSV：`outputs/minimal_backtest/20260615_181558_minimal_backtest/holdings.csv`
- CSV：`outputs/minimal_backtest/20260615_181558_minimal_backtest/failures.csv`
- CSV：`outputs/minimal_backtest/20260615_181558_minimal_backtest/universe.csv`

## 验证记录

- `python -m py_compile src\stock_selector\data\models.py src\stock_selector\data\eastmoney.py src\stock_selector\data\sina.py src\stock_selector\data\eastmoney_history.py src\stock_selector\screening\momentum_liquidity.py src\stock_selector\backtest\metrics.py src\stock_selector\backtest\engine.py src\stock_selector\reports\backtest_report.py scripts\run_minimal_backtest.py`：退出码 0，通过。
- `python -m unittest tests.test_minimal_backtest -v`：退出码 0，9 项通过。
- `python -m unittest discover -s tests -v`：退出码 0，56 项通过。

## 风险与限制

- 股票池来自当前真实候选 CSV，历史退市股票未纳入，存在幸存者偏差。
- 腾讯历史源不提供换手率、主力资金和估值字段；回测评分记录缺失因子并动态归一可用权重。
- 腾讯源成交额由成交量和收盘价派生，非接口原始成交额。
- 停牌、涨跌停可成交性和真实盘口滑点未完整建模。
- 东财历史源本轮不稳定，已记录失败并保留回退机制。
- 当前结果不构成投资建议、收益承诺或交易指令。

## 当前结论

- 第一条真实历史回测闭环达到 `L2_AGENT_TESTED`：自动测试通过，且真实历史行情回测完整跑通并生成 HTML/JSON/CSV 报告。
- 用户尚未真实查看报告，因此不标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 本轮已按协作规则执行 Git add 和 Commit；本地 commit 为 `36dac1328e642cb2c7f84c174a102fcf210059ac`。
- GitHub push 连续三次失败：两次 `Recv failure: Connection was reset`，一次无法连接到 `github.com:443`；未使用 force push，现场保留。

## 下一步

- 建设无幸存者偏差的历史股票池。
- 恢复或替换字段更完整的历史源，补换手率、成交额、估值和资金流。
- 加入停牌、涨跌停、行业和财务因子处理。
- 扩大样本并做参数稳健性检查。
- 网络恢复后重试普通 `git push`。
