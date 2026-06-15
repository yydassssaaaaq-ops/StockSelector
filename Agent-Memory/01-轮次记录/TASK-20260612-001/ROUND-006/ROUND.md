# ROUND-006

## 基本信息

- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-006
- 触发来源：用户要求基础设施阶段结束，开始建设第一条真正可运行的 A 股选股业务闭环，并允许测试通过后自动 Commit/Push。
- 本轮目标：使用真实数据跑通最小业务链：行情快照采集 -> 因子过滤/打分 -> 候选结果 -> 可查看报告。
- 起始时间：2026-06-15T16:31:22+08:00
- 结束时间：2026-06-15T16:56:34+08:00
- 起始分支：main
- 起始 HEAD：a062e3f1c9abc83ccd82356b0df03dc564d13515
- 是否切换或新建分支：否

## 本轮修改

- 新增 `src/stock_selector/data/eastmoney.py`：东财 push2 A 股行情采集器。
- 新增 `src/stock_selector/data/sina.py`：新浪市场中心 `hs_a` 行情采集器，作为默认真实源。
- 新增 `src/stock_selector/screening/momentum_liquidity.py`：动量、流动性、估值、波动守门项筛选和打分。
- 新增 `src/stock_selector/reports/screen_report.py`：生成原始行情 CSV、候选 CSV、摘要 JSON 和 HTML 报告。
- 新增 `scripts/run_real_a_share_screen.py`：真实行情选股闭环 CLI。
- 新增 `tests/test_a_share_screen.py`：字段映射、筛选和报告输出测试。
- 新增 `docs/a_share_screen_usage.md`，并更新 README、模块 README、开发工作流和 AGENTS.md。
- 更新 Agent-Memory 当前状态、TASK 说明和协作规则：允许测试通过且工作区无明显异常后在当前分支正常 Commit/Push；禁止 force push。

## 真实数据样例

- 执行命令：`python scripts\run_real_a_share_screen.py --top 30`
- 真实数据源：新浪市场中心 `hs_a` 行情快照。
- run_id：`20260615_164853_sina_snapshot`
- 读取真实行情：5527 条。
- 通过过滤：1665 条。
- 输出候选：30 条。
- Top 5：000725 京东方Ａ、002185 华天科技、000630 铜陵有色、000021 深科技、000737 北方铜业。
- 最新 HTML 报告：`outputs/a_share_screen/latest.html`
- 本次 HTML 报告：`outputs/a_share_screen/20260615_164853_sina_snapshot/report.html`
- 候选 CSV：`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`
- 摘要 JSON：`outputs/a_share_screen/20260615_164853_sina_snapshot/summary.json`
- 原始行情 CSV：`data/raw/a_share_quotes/20260615_164853_sina_snapshot_quotes.csv`

## 验证记录

- `python -m py_compile src\stock_selector\data\eastmoney.py src\stock_selector\data\sina.py src\stock_selector\screening\momentum_liquidity.py src\stock_selector\reports\screen_report.py scripts\run_real_a_share_screen.py`：退出码 0，通过。
- `python -m unittest tests.test_a_share_screen -v`：退出码 0，4 项通过。
- `python scripts\run_real_a_share_screen.py --top 30`：首次在东财单源实现下失败，页面翻到第 23 页时接口断开连接；随后新增新浪回退源并将默认源改为新浪。
- `python scripts\run_real_a_share_screen.py --top 30`：退出码 0，真实行情闭环通过，生成 HTML/CSV/JSON 报告。
- `python -m unittest discover -s tests -v`：退出码 0，47 项通过。
- `python scripts\validate_memory.py`：退出码 0，通过，FAIL 0 项、WARNING 0 项。

## 风险与限制

- 当前结果是工程规则筛选和候选观察，不构成投资建议、收益承诺或交易指令。
- 新浪源不提供主力净流入字段，系统保留空值，不使用模拟值补齐。
- 东财 push2 列表接口本轮真实运行时出现断连/502，已保留为可选源，默认真实样例使用新浪源。
- 尚未接入历史复权行情和回测，无法证明筛选规则具备稳定超额收益。

## 当前结论

- 第一条真实 A 股选股业务闭环已达到 `L2_AGENT_TESTED`：代码测试通过，且真实行情样例完整跑通并生成用户可查看结果。
- 用户尚未真实查看报告，因此不标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 本轮按新协作规则，在测试和状态校验通过后可执行 Git add、Commit 和 Push。
