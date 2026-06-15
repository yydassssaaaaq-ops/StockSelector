# StockSelector

StockSelector 是一个面向 A 股智能选股系统的工程仓库。当前已具备第一条真实行情选股闭环：抓取 A 股行情快照，按动量、流动性、估值和波动约束进行规则筛选，并生成本地 HTML/CSV/JSON 报告。

## 常用命令

```powershell
python scripts/project_status.py
python scripts/run_real_a_share_screen.py --top 30
python scripts/build_gpt_context.py
python scripts/build_index.py
python scripts/validate_memory.py
python -m unittest discover -s tests -v
```

## 当前业务链

- 默认真实数据源：新浪市场中心 `hs_a` 行情快照。
- 可选数据源：东财 push2 A 股行情快照；当前作为可选源和自动回退链的一部分。
- 默认输出：`outputs/a_share_screen/latest.html`、本轮 `candidates.csv`、`summary.json`，以及 `data/raw/a_share_quotes/*_quotes.csv` 原始行情快照。
- 说明：当前结果用于工程验证和候选观察，不构成投资建议、收益承诺或交易指令。

复权方案、回测框架、模型类型、交易周期和实盘接口仍待后续建设。
