# A 股规则最小历史回测

本命令把当前真实行情筛选规则升级为可被历史日线验证的最小闭环：

```powershell
python scripts\run_minimal_backtest.py
```

常用可复现参数：

```powershell
python scripts\run_minimal_backtest.py `
  --start-date 2026-01-01 `
  --end-date 2026-06-15 `
  --top-n 10 `
  --rebalance-frequency weekly `
  --transaction-cost 0.001 `
  --slippage 0.0005 `
  --data-source tencent `
  --universe-source csv `
  --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv `
  --universe-limit 20 `
  --adjustment qfq
```

## 数据源

- 股票历史行情默认使用腾讯前复权日 K，真实返回 OHLC 和成交量。成交额由 `volume_hands * 100 * close` 派生，换手率、主力资金和估值字段缺失。
- 东财 `push2his` 日 K 已接入，字段更完整，但本轮真实运行中出现连续连接断开，因此保留为可选源。
- 基准默认沪深 300；优先尝试东财指数日 K，失败时回退 Yahoo Finance `000300.SS`。
- 所有历史请求都写入 `data/cache/historical_quotes/`，重复运行会优先命中本地缓存。

## 回测规则

- 调仓频率：默认周频。
- 信号日：每周最后一个交易日收盘后。
- 成交日：下一交易日收盘。
- 持有期：从本期成交日收盘持有到下一信号后的下一交易日收盘。
- 组合：Top N 等权。
- 成本：按换手额扣减交易成本和滑点。
- 缺失执行价：不补 0，不用未来数据填充，记录并跳过该持仓。

## 缺失因子处理

评分采用动态可用因子权重：

- 可用因子按原始权重重新归一到 100 分。
- 缺失因子记录在每只持仓的 `missing_factors` 中。
- `data_completeness` 显示本次评分实际可用的原始权重比例。
- 缺少主力资金、估值或换手率时，结果不标记为跨数据源可直接比较。

## 输出文件

- `outputs/minimal_backtest/latest.html`
- `outputs/minimal_backtest/<run_id>/report.html`
- `outputs/minimal_backtest/<run_id>/summary.json`
- `outputs/minimal_backtest/<run_id>/periods.csv`
- `outputs/minimal_backtest/<run_id>/holdings.csv`
- `outputs/minimal_backtest/<run_id>/failures.csv`
- `outputs/minimal_backtest/<run_id>/universe.csv`

## 本轮真实样例

命令：

```powershell
python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 10 --rebalance-frequency weekly --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source csv --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv --universe-limit 20 --adjustment qfq --timeout 20 --retries 3
```

结果：

- run_id：`20260615_181558_minimal_backtest`
- 股票池：上一轮真实新浪候选 CSV 的前 20 只。
- 股票历史源：腾讯前复权日 K。
- 基准源：东财指数日 K 请求失败后回退 Yahoo Finance `000300.SS`。
- 有效期数：21。
- 策略累计收益：18.78%。
- 沪深 300 累计收益：2.13%。
- 相对基准超额收益：16.65%。
- 策略最大回撤：23.15%，明显高于基准 7.76%。
- 结论：有限样本内策略累计收益高于基准，但回撤风险需要继续检查。

## 已知偏差

- 股票池来自当前真实快照候选，历史退市股票未纳入，存在幸存者偏差。
- 腾讯源不提供换手率、估值和主力资金字段，评分完整性低于实时快照源。
- 涨跌停可成交性、停牌细节和真实盘口滑点未完全建模。
- 当前结果未经用户真实查看验收，不构成投资建议。
