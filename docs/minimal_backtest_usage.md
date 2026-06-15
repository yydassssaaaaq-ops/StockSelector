# A 股可信历史验证回测

本命令用于验证固定历史策略 `historical_ohlcv_v1`，而不是把实时快照候选股带回过去。

```powershell
python scripts\run_minimal_backtest.py
```

## 默认研究口径

- 股票池：当前仍上市的宽 A 股代码池过渡方案，默认只使用当前快照中的代码、名称、交易所和板块。
- 默认不使用今天的成交额、涨跌幅、实时评分或候选排名过滤过去股票池。
- 股票池仍有幸存者偏差：历史退市股票和历史成分变化尚未完整纳入。
- 历史策略：`historical_ohlcv_v1`，与实时 `momentum_liquidity` 扫描策略分离。
- 信号：每个信号日收盘后，只读取该日及以前日线。
- 执行：默认下一交易日开盘，日线近似处理无量、缺价、涨停难买和跌停难卖。
- 比较对象：沪深 300、股票池等权基线、20 日趋势单因子基线。

## 常用命令

```powershell
python scripts\run_minimal_backtest.py `
  --start-date 2026-01-01 `
  --end-date 2026-06-15 `
  --top-n 5 `
  --rebalance-frequency weekly `
  --execution-timing next_open `
  --transaction-cost 0.001 `
  --slippage 0.0005 `
  --data-source tencent `
  --universe-source sina `
  --universe-filter-mode broad_current_listed `
  --universe-limit 30 `
  --adjustment qfq
```

## 因子定义

`historical_ohlcv_v1` 使用固定因子集合和固定权重，不因数据源缺失而动态伪装成另一套策略：

- `trend_20d_return`：20 日价格趋势，权重 25%。
- `trend_60d_return`：60 日趋势持续性，权重 20%。
- `price_vs_ma20`：价格相对 20 日均线位置，权重 15%。
- `liquidity_20d_median_amount`：20 日成交额中位数，权重 20%。
- `volatility_20d`：20 日收益波动，低波动更好，权重 10%。
- `max_drawdown_20d`：20 日最大回撤，低回撤更好，权重 10%。

所有因子均按同一信号日横截面百分位标准化。窗口不足、信号日缺失、成交额有效样本不足等情况会剔除该股票本期历史评分，不使用有利默认值补齐。

## 调试模式

固定 CSV 股票池仍可用于复现实验或排查问题：

```powershell
python scripts\run_minimal_backtest.py `
  --universe-source csv `
  --universe-csv outputs\a_share_screen\20260615_164853_sina_snapshot\candidates.csv `
  --universe-limit 20
```

报告会将该模式标记为 `csv_debug`。它不是默认策略验证路径，不能作为历史选股能力证据。

如需复现旧的当前快照流动性过滤，可显式使用：

```powershell
python scripts\run_minimal_backtest.py --universe-filter-mode snapshot_liquidity
```

该模式会使用今天的成交额过滤过去股票池，只适合诊断，不适合作为可信策略验证。

## 输出文件

- `outputs/minimal_backtest/latest.html`
- `outputs/minimal_backtest/<run_id>/report.html`
- `outputs/minimal_backtest/<run_id>/summary.json`
- `outputs/minimal_backtest/<run_id>/periods.csv`
- `outputs/minimal_backtest/<run_id>/holdings.csv`
- `outputs/minimal_backtest/<run_id>/failures.csv`
- `outputs/minimal_backtest/<run_id>/universe.csv`

`summary.json` 和 HTML 报告包含股票池来源、策略身份、因子覆盖率、执行假设、阻断统计、基线比较、当前结果能证明什么以及不能证明什么。

## ROUND-008 真实样例

命令：

```powershell
python -u scripts\run_minimal_backtest.py --start-date 2026-01-01 --end-date 2026-06-15 --top-n 5 --rebalance-frequency weekly --execution-timing next_open --transaction-cost 0.001 --slippage 0.0005 --data-source tencent --universe-source sina --universe-filter-mode broad_current_listed --universe-limit 30 --adjustment qfq --timeout 15 --retries 1
```

结果：

- run_id：`20260615_234854_minimal_backtest`
- 股票池：新浪当前宽 A 股代码池前 30 只，未使用今天成交额、涨跌幅、评分或候选排名过滤。
- 股票历史源：腾讯前复权日 K。
- 基准源：东财指数日 K 请求失败后回退 Yahoo Finance `000300.SS`。
- 有效回测窗口：21 个周频窗口，其中早期窗口因 60 日因子窗口不足保持现金。
- 策略累计收益：-10.72%。
- 沪深 300 累计收益：1.25%。
- 股票池等权基线累计收益：-3.75%。
- 20 日趋势单因子基线累计收益：-8.70%。
- 结论：可信回测链路可运行，但当前有限样本不能证明策略有效。

## ROUND-007 历史工程样例降级说明

`20260615_181558_minimal_backtest` 保留为历史工程样例。它使用 2026-06-15 当天候选 CSV 前 20 只股票向前回测，因此只能说明旧回测程序能够运行，不能作为策略有效性证据。
