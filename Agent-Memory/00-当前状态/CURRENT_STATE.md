# CURRENT_STATE

- 当前阶段：基础设施阶段结束，已进入第一条真实 A 股选股业务闭环建设。
- 当前可运行能力：真实 A 股行情快照采集、规则筛选打分、候选 CSV、原始行情 CSV、摘要 JSON、HTML 报告；历史案卷库导入、SQLite 索引、文件监控和本地工作台仍保留可用。
- 当前正常命令：`python scripts\run_real_a_share_screen.py --top 30`、`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前真实行情数据：新浪市场中心 `hs_a` 快照，2026-06-15 真实样例读取 5527 条 A 股行情，过滤后 1665 条，输出 Top 30；Top 5 为 000725 京东方Ａ、002185 华天科技、000630 铜陵有色、000021 深科技、000737 北方铜业。
- 当前真实样例输出：`outputs/a_share_screen/latest.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/report.html`、`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`、`outputs/a_share_screen/20260615_164853_sina_snapshot/summary.json`、`data/raw/a_share_quotes/20260615_164853_sina_snapshot_quotes.csv`。
- 当前规则边界：排除 ST/退市整理和新股前缀样本；要求价格、成交额、换手率、涨跌幅、振幅在阈值内；按动量、流动性、主力资金、估值和波动守门项打分。新浪源不提供主力净流入字段，系统保留空值，不用模拟值补齐。
- 当前尚不存在的业务能力：历史回测、复权行情、行业中性化、财务因子、组合构建、涨跌预测、实盘交易、投资建议。
- 当前限制：用户尚未真实查看本轮报告，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 最近一次完整测试：`python -m unittest discover -s tests -v`，47 项通过。
- 最近稳定 commit：a062e3f1c9abc83ccd82356b0df03dc564d13515
- 下一次优先事项：为这条真实行情筛选链补历史行情/复权数据与最小回测，用收益回放检验筛选规则是否有稳定价值。
