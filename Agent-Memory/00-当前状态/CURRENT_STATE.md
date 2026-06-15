# CURRENT_STATE

- 当前阶段：第一条真实 A 股选股业务链已从快照筛选推进到最小历史回测闭环。
- 当前可运行能力：真实 A 股行情快照采集、规则筛选打分、候选 CSV、原始行情 CSV、摘要 JSON、HTML 报告；真实历史日线获取、前复权缓存、信号生成、收益回放、沪深 300 基准比较、回测 HTML/JSON/CSV 报告；历史案卷库导入、SQLite 索引、文件监控和本地工作台仍保留可用。
- 当前正常命令：`python scripts\run_real_a_share_screen.py --top 30`、`python scripts\run_minimal_backtest.py`、`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前真实行情数据：新浪市场中心 `hs_a` 快照，2026-06-15 真实样例读取 5527 条 A 股行情，过滤后 1665 条，输出 Top 30；Top 5 为 000725 京东方Ａ、002185 华天科技、000630 铜陵有色、000021 深科技、000737 北方铜业。
- 当前真实样例输出：`outputs/a_share_screen/latest.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/report.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`、`outputs/a_share_screen/20260615_164853_sina_snapshot/summary.json`、`data/raw/a_share_quotes/20260615_164853_sina_snapshot_quotes.csv`。
- 当前真实回测样例：`20260615_181558_minimal_backtest`，区间 2026-01-01 至 2026-06-15，股票池为上一轮真实新浪候选 CSV 前 20 只，股票历史源为腾讯前复权日 K，基准为沪深 300；东财基准源断连后回退 Yahoo Finance `000300.SS`。
- 当前回测结果：有效期数 21；策略累计收益 18.78%，年化收益 53.13%，最大回撤 23.15%，年化波动率 48.54%，夏普 1.127，胜率 61.90%，平均单期收益 1.05%，最好单期 13.75%，最差单期 -12.62%，平均换手 99.05%，交易次数 215；沪深 300 累计收益 2.13%，最大回撤 7.76%；相对基准超额收益 16.65%。结论为有限样本内策略累计收益高于基准，但回撤风险需要继续检查。
- 当前规则边界：排除 ST/退市整理和新股前缀样本；快照筛选要求价格、成交额、换手率、涨跌幅、振幅在阈值内；历史回测使用信号日收盘后可得日线字段并默认下一交易日收盘成交。缺失主力资金、估值或换手率时不按 0 分处理，而是对可用因子动态重新归一并记录完整性。
- 当前尚不存在的业务能力：无幸存者偏差全历史股票池、行业中性化、财务因子、涨跌停/停牌可成交性精细建模、正式组合构建、涨跌预测、实盘交易、投资建议。
- 当前限制：用户尚未真实查看本轮报告，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- Git 状态：本地 commit `36dac1328e642cb2c7f84c174a102fcf210059ac` 已创建；GitHub push 连续三次失败，错误为 HTTPS 连接重置或无法连接到 github.com:443，需网络恢复后重试普通 push。
- 最近一次完整测试：`python -m unittest discover -s tests -v`，56 项通过。
- 最近稳定 commit：36dac1328e642cb2c7f84c174a102fcf210059ac
- 下一次优先事项：建设无幸存者偏差的历史股票池和停牌/涨跌停可成交性处理，扩大股票池并对比东财字段完整源恢复后的结果。
