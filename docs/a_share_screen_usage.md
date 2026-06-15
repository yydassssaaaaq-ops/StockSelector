# A 股真实行情选股闭环

## 运行命令

```powershell
python scripts\run_real_a_share_screen.py --top 30
```

默认使用新浪市场中心 `hs_a` 行情快照，分页读取沪深北 A 股实时或延迟行情。也可以指定：

```powershell
python scripts\run_real_a_share_screen.py --source sina --top 30
python scripts\run_real_a_share_screen.py --source eastmoney --top 30
python scripts\run_real_a_share_screen.py --source auto --top 30
```

## 输出文件

- `outputs/a_share_screen/latest.html`：最新可视化报告。
- `outputs/a_share_screen/<run_id>/report.html`：本次 HTML 报告。
- `outputs/a_share_screen/<run_id>/candidates.csv`：候选股票明细。
- `outputs/a_share_screen/<run_id>/summary.json`：运行摘要、筛选配置和候选结果。
- `data/raw/a_share_quotes/<run_id>_quotes.csv`：原始行情快照。

## 当前规则

当前筛选链只做工程可解释排序：

- 排除 ST、退市整理和新股前缀样本。
- 要求价格、成交额、换手率、涨跌幅和振幅处于配置阈值内。
- 按涨跌幅、成交额、换手率、主力资金、估值和振幅守门项打分。
- 新浪源不提供主力净流入字段，报告会保留该字段为空，不使用模拟值补齐。
- 缺失因子不再按 0 分直接惩罚；系统会对可用因子动态重新归一权重，并在结果中记录缺失因子、有效权重和数据完整性。

本结果不构成投资建议、收益承诺或交易指令。

历史验证命令见 `docs/minimal_backtest_usage.md`。
