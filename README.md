# StockSelector

StockSelector 是一个面向 A 股选股研究系统的工程仓库。当前已具备两条真实数据业务链：抓取 A 股行情快照并生成实时规则筛选报告；使用真实历史日线运行 point-in-time 历史验证回测，并输出策略、基准、简单基线和可信性审计报告。

## 常用命令

```powershell
python scripts/project_status.py
python scripts/run_real_a_share_screen.py --top 30
python scripts/run_minimal_backtest.py
python scripts/build_gpt_context.py
python scripts/build_index.py
python scripts/validate_memory.py
python -m unittest discover -s tests -v
```

## 当前业务链

- 快照默认真实数据源：新浪市场中心 `hs_a` 行情快照。
- 历史验证默认策略：`historical_ohlcv_v1`，只使用信号日及以前的 OHLCV 派生因子；它与实时快照扫描策略分离。
- 历史回测默认股票池：当前仍上市宽 A 股代码池过渡方案，不再默认使用当天候选 CSV 或今天成交额过滤过去股票池。
- 历史回测默认股票历史源：腾讯前复权日 K；东财 `push2his` 日 K 已接入但本轮出现连接断开，保留为可选源。
- 基准：沪深 300，优先东财指数日 K，失败时回退 Yahoo Finance `000300.SS`。
- 快照输出：`outputs/a_share_screen/latest.html`、本轮 `candidates.csv`、`summary.json`，以及 `data/raw/a_share_quotes/*_quotes.csv` 原始行情快照。
- 回测输出：`outputs/minimal_backtest/latest.html`、`summary.json`、`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 说明：当前结果用于工程验证和候选观察，不构成投资建议、收益承诺或交易指令。

当前回测仍存在当前仍上市股票池的幸存者偏差、日线涨跌停可成交性近似、腾讯源成交额派生口径等限制。ROUND-007 的 18.78% 回测结果已降级为固定当前候选 CSV 下的工程运行样例，不构成策略有效性证据。模型类型、行业/财务因子、正式组合构建和实盘接口仍待后续建设。
