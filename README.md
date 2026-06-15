# StockSelector

StockSelector 是一个面向 A 股智能选股系统的工程仓库。当前已具备两条真实数据业务链：抓取 A 股行情快照并生成规则筛选报告；使用真实历史日线对当前筛选规则做最小横截面回测，并输出策略与沪深 300 基准对比报告。

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
- 历史回测默认股票历史源：腾讯前复权日 K；东财 `push2his` 日 K 已接入但本轮出现连接断开，保留为可选源。
- 基准：沪深 300，优先东财指数日 K，失败时回退 Yahoo Finance `000300.SS`。
- 快照输出：`outputs/a_share_screen/latest.html`、本轮 `candidates.csv`、`summary.json`，以及 `data/raw/a_share_quotes/*_quotes.csv` 原始行情快照。
- 回测输出：`outputs/minimal_backtest/latest.html`、`summary.json`、`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 说明：当前结果用于工程验证和候选观察，不构成投资建议、收益承诺或交易指令。

当前回测仍存在股票池幸存者偏差、停牌/涨跌停可成交性不完整、腾讯源缺少换手率/主力资金/估值字段等限制。模型类型、行业/财务因子、正式组合构建和实盘接口仍待后续建设。
