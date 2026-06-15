# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：StockSelector / A股智能选股系统
- 当前 TASK：TASK-20260612-001
- 当前 ROUND：ROUND-006
- 执行状态：waiting_user_review
- 验证等级：L2_AGENT_TESTED
- 用户验证：not_run
- GitHub 同步：pushed
- 当前真实分支：main
- 当前真实 HEAD：a062e3f1c9abc83ccd82356b0df03dc564d13515
- 状态文件观察到的 HEAD：a062e3f1c9abc83ccd82356b0df03dc564d13515
- 工作区干净：False

## B. Agent 解释

### 当前任务
# CURRENT_TASK
- 当前 TASK：TASK-20260612-001
- 任务名称：StockSelector 工程闭环与第一条真实 A 股选股业务链
- 当前 ROUND：ROUND-006
- 本轮目标：不再扩建空基础设施，直接建设一条真实行情快照到规则筛选再到可查看报告的最小 A 股选股业务闭环。
- 当前状态：waiting_user_review
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：无阻塞问题；等待用户查看 `outputs/a_share_screen/latest.html` 和候选 CSV。
- 已完成：新浪 `hs_a` 真实行情采集、东财可选采集器、动量/流动性/估值/波动规则筛选、HTML/CSV/JSON 报告、真实样例运行、自动化测试、协作规则更新。
- 未完成：用户真实查看验收、历史回测、复权行情、行业/财务因子、正式投资组合构建、实盘接口。
- 本轮真实样例：`python scripts\run_real_a_share_screen.py --top 30` 于 2026-06-15 16:48:53 生成 `20260615_164853_sina_snapshot`，读取真实行情 5527 条，过滤后 1665 条，输出候选 30 条。
- 最新可查看结果：`outputs/a_share_screen/latest.html`；候选 CSV：`outputs/a_share_screen/20260615_164853_sina_snapshot/candidates.csv`。
- GitHub 外循环：规则已改为测试通过且工作区无明显异常后可由 Codex 在当前分支 Commit 并 Push；不得 force push，不创建或切换分支。

### 当前状态
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

### 开放问题
# OPEN_ISSUES
当前无开放问题。
非阻塞观察：
- 东财 push2 列表接口本轮真实运行时出现连接断开/502，因此默认真实样例改用新浪市场中心 `hs_a`；东财采集器保留为可选源。
- 新浪源不提供主力净流入字段，报告中相关字段保持空值，不使用模拟值补齐。
- 当前筛选结果未经历史回测和用户真实验收，不得视为投资建议或交易信号。

### 最近 ROUND
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

### 工作区摘要

tracked 修改：
- AGENTS.md
- Agent-Memory/00-当前状态/CURRENT_STATE.md
- Agent-Memory/00-当前状态/CURRENT_TASK.md
- Agent-Memory/00-当前状态/ENVIRONMENT.md
- Agent-Memory/00-当前状态/FILE_MAP.md
- Agent-Memory/00-当前状态/OPEN_ISSUES.md
- Agent-Memory/00-当前状态/PROJECT.md
- Agent-Memory/00-当前状态/USAGE.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/TASK.md
- Agent-Memory/03-GPT导出/GPT_CONTEXT.md
- Agent-Memory/INDEX.md
- Agent-Memory/MEMORY_STATUS.json
- README.md
- docs/DEVELOPMENT_WORKFLOW.md
- scripts/build_gpt_context.py
- scripts/finish_round.py
- scripts/init_memory.py
- scripts/project_status.py
- scripts/templates/ROUND.template.md
- src/stock_selector/data/README.md
- src/stock_selector/reports/README.md
- src/stock_selector/screening/README.md

未跟踪文件：
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-006/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-006/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-006/workspace_manifest.json
- docs/a_share_screen_usage.md
- scripts/run_real_a_share_screen.py
- src/stock_selector/data/eastmoney.py
- src/stock_selector/data/sina.py
- src/stock_selector/reports/screen_report.py
- src/stock_selector/screening/momentum_liquidity.py
- tests/test_a_share_screen.py

## C. 用户验证

- 用户验证状态：not_run
- 当前不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 下一步建议：检查自动验证和真实样例结果；若通过且工作区无明显异常，可在当前分支 Commit 并 Push。

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-006/`
- `scripts/`
- `tests/test_memory_tools.py`
