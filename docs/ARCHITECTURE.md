# 架构说明

当前仓库是中性的工程壳。各业务模块职责只是暂定边界，不代表数据源、指标、算法、模型或存储方案已经最终确定。

## ROUND-008 后的研究边界

- `screening/momentum_liquidity.py`：实时快照扫描策略，只解释当日可见快照字段，不再作为历史验证策略复用。
- `features/historical_factors.py`：历史 OHLCV 因子层，固定策略身份 `historical_ohlcv_v1`，所有窗口严格截断在信号日。
- `backtest/execution.py`：日线级执行近似，集中处理下一开盘、无量、缺价、涨跌停阻断和延迟退出。
- `backtest/engine.py`：组合形成、基线比较、换手/成本、审计字段和结果结论。
- `reports/backtest_report.py`：同时输出机器可读 JSON/CSV 和人类 HTML 报告，必须披露股票池偏差、策略身份、因子覆盖、执行假设和当前结论边界。

默认历史回测不再使用当天候选 CSV 向前回测。CSV 股票池和当前快照流动性过滤保留为显式调试/诊断模式，并在报告中标记其研究局限。
