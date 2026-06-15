# CURRENT_STATE

- 当前阶段：历史回测链路已从 ROUND-007 的最小工程样例升级为 ROUND-008 的可信研究底座。
- 当前可运行能力：真实 A 股行情快照采集、实时规则扫描、原始行情/候选 CSV/JSON/HTML 输出；历史 OHLCV 固定因子计算、point-in-time 信号、横截面百分位评分、下一开盘执行、日线级不可成交近似、沪深 300/股票池等权/单因子基线比较、HTML/JSON/CSV 审计报告；历史案卷库导入、SQLite 索引、文件监控和本地工作台仍保留可用。
- 当前正常命令：`python scripts\run_real_a_share_screen.py --top 30`、`python scripts\run_minimal_backtest.py`、`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前实时扫描策略：`screening/momentum_liquidity.py`，用于实时快照，不作为历史验证策略复用。
- 当前历史验证策略：`historical_ohlcv_v1`，只使用信号日及以前 OHLCV 派生因子；因子包括 20 日趋势、60 日趋势、20 日均线位置、20 日成交额中位数、20 日波动率、20 日最大回撤；固定权重，横截面百分位标准化，窗口不足或数据缺失时剔除本期样本。
- 当前默认股票池：`broad_current_listed`，通过当前快照仅取得仍上市 A 股代码、名称、交易所和板块；不使用今天成交额、涨跌幅、实时评分或候选排名过滤过去；仍存在幸存者偏差。
- 当前显式调试模式：`--universe-source csv` 会标记为 `csv_debug`；`--universe-filter-mode snapshot_liquidity` 会标记为当前快照流动性过滤诊断模式，均不应作为默认策略验证证据。
- 当前执行假设：信号日收盘后形成候选；默认下一交易日开盘执行；持有到下一调仓对应的下一交易日开盘；交易成本和滑点按换手扣减；无量、缺价、涨停难买、跌停难卖和延迟退出记录在报告中；部分无法成交的权重保留为现金。
- 当前真实验收输出：`outputs/minimal_backtest/latest.html`、`outputs/minimal_backtest/20260615_234854_minimal_backtest/report.html`、`summary.json`、`periods.csv`、`holdings.csv`、`failures.csv`、`universe.csv`。
- 当前真实验收数据：新浪 `hs_a` 快照读取 5527 条，默认宽代码池前 30 只；腾讯前复权日 K 股票历史 30/30 成功，缓存命中 30；东财沪深 300 基准请求失败后回退 Yahoo Finance `000300.SS`，记录 `failed_benchmark_requests=1`。
- 当前真实验收结果：2026-01-01 至 2026-06-15，周频 Top5，21 个回测窗口；策略累计收益 -10.72%，年化收益 -24.49%，最大回撤 13.40%，夏普 -1.417，胜率 14.29%，交易次数 36，平均换手 34.29%；沪深 300 累计收益 +1.25%；股票池等权基线 -3.75%；20 日趋势单因子基线 -8.70%。
- 当前结论边界：本轮结果证明可信历史验证链路可运行，并能揭示策略未跑赢基准/简单基线；不证明策略有效、不构成投资建议、不构成交易信号。
- 当前自动测试：`python -m unittest discover -s tests -v`，61 项通过；`tests.test_minimal_backtest` 当前 14 项通过，覆盖未来数据隔离、默认非 CSV 股票池、窗口不足、下一开盘执行、无量/涨跌停约束、现金权重和审计字段。
- 当前限制：用户尚未真实查看本轮报告，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- Git 状态：本轮起始 HEAD 为 `2f1136eee9600ad056967434c74a9aca85a1a521`，起始工作区干净；本轮普通 commit `2d664de4ccf8b5882e101c173a23c0e60f3eaf73` 已推送到 `origin/main`，未使用 force push，未创建或切换分支。
- 最近稳定 commit：2d664de4ccf8b5882e101c173a23c0e60f3eaf73
- 下一次优先事项：建设真正 point-in-time 历史股票池；补齐行业/财务/流通市值/换手率/真实成交额历史字段；建立组合构建和风险约束层。
