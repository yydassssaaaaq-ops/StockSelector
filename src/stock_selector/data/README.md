# data

当前包含中立行情模型、真实行情快照采集器和真实历史日线采集器：

- `models.py`：公共中立数据模型，包含 `AShareQuote`、`DailyBar`、`HistoricalSeries` 和失败记录。
- `eastmoney.py`：东财 push2 A 股行情快照，字段较丰富但接口可能波动。
- `sina.py`：新浪市场中心 `hs_a` 行情快照，默认稳定源，覆盖沪深北 A 股列表。
- `eastmoney_history.py`：东财 `push2his` 股票/指数日 K，支持前复权、后复权和不复权，带本地缓存；本轮真实运行中出现连接断开。
- `tencent_history.py`：腾讯前复权/后复权/不复权日 K，作为当前默认股票历史源；提供 OHLC 和成交量，成交额由成交量乘价格派生，换手率缺失。
- `yahoo_history.py`：Yahoo Finance 指数日 K，当前仅作为沪深 300 基准回退源。

采集器不读取密钥，不写入旧项目目录。所有外部请求必须设置超时，失败不得静默跳过。
