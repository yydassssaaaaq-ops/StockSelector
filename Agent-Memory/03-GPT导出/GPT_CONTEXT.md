# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：StockSelector / A股智能选股系统
- 当前 TASK：TASK-20260612-001
- 当前 ROUND：ROUND-002
- 执行状态：waiting_github_sync
- 验证等级：L4_USER_VERIFIED
- 用户验证：passed
- GitHub 同步：not_pushed
- 当前真实分支：main
- 当前真实 HEAD：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 状态文件观察到的 HEAD：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 工作区干净：False

## B. Agent 解释

### 当前任务
# CURRENT_TASK
- 当前 TASK：TASK-20260612-001
- 任务名称：修复 Windows BAT 辅助入口问题
- 当前状态：waiting_github_sync
- 当前验证等级：L4_USER_VERIFIED
- 用户验证状态：passed
- 当前卡点：无开放问题；等待用户在 GitHub Desktop 中确认并同步。
- 已完成：ROUND-002 已建立；已记录用户真实反馈；三个 BAT 辅助入口已修复；自动验证通过；用户已真实双击验证通过。
- 未完成：尚未 Commit，尚未 Push，当前不得进入 L5_CLOSED。
- 下一步：用户在 GitHub Desktop 中检查本轮改动，确认后再执行 Commit 和 Publish/Push。
- 关联 ROUND：ROUND-002
- 是否需要 GitHub 外循环：是，等待用户手动执行；本轮 Agent 不 Commit、不 Push。

### 当前状态
# CURRENT_STATE
- 当前阶段：Windows BAT 辅助入口已由用户重新验证通过，等待 GitHub 同步。
- 当前可运行能力：生成 GPT_CONTEXT、生成 INDEX、验证 Agent-Memory、输出项目状态、开始 TASK/ROUND、结束 ROUND、创建 CHECKPOINT。
- 当前正常功能：用户已验证 `python scripts\project_status.py`、`python scripts\validate_memory.py` 和 `python -m unittest discover -s tests -v` 通过；本轮自动 BAT 非交互测试已通过；用户重新双击三个 BAT 也已通过。
- 当前异常历史：用户双击 `scripts\project_status.bat` 曾失败，表现为错误寻找 `scripts\scripts\project_status.py`、中文路径解析异常、CMD 中文乱码、未可靠切换到仓库根目录。
- 当前处理结果：三个 BAT 已改为使用 `%~dp0` 定位自身目录、带引号路径、`cd /d "%~dp0.."` 切换仓库根目录、UTF-8 当前进程设置、python/py 顺序探测、双击 pause 与 `STOCKSELECTOR_NO_PAUSE=1` 非交互跳过；用户真实双击复验通过。
- 当前尚不存在的业务能力：真实数据采集、股票池生成、特征指标、筛选规则、回测验证、Agent 决策、报告生成、实盘接口。
- 当前限制：用户验证状态为 passed，可达到 L4_USER_VERIFIED；因尚未 Commit/Push，不得进入 L5_CLOSED。
- Git HEAD 记录语义：`MEMORY_STATUS.json` 中 `observed_head_commit` 表示最近一次生成状态文件时观察到的 HEAD；兼容字段 `head_commit` 同样只表示观察值。当前真实 HEAD 必须以 Git 动态读取结果为准，不再要求状态文件观察值永远等于提交后的 HEAD。
- 最近一次测试：见 `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-002/ROUND.md`。
- 最近稳定 commit：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 状态文件观察到的 HEAD：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 当前真实 HEAD：由 `git rev-parse --verify HEAD` 或 `scripts/project_status.py` 动态读取。
- 下一次优先事项：用户在 GitHub Desktop 中检查、Commit，并在需要时 Publish/Push。

### 开放问题
# OPEN_ISSUES
当前无开放问题。

### 最近 ROUND
# ROUND-002
## 基本信息
- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-002
- 触发来源：用户真实验证反馈
- 本轮目标：修复 Windows BAT 辅助入口问题，不修改选股业务代码。
- 起始时间：2026-06-12T20:52:52+08:00
- 结束时间：2026-06-12T21:01:19+08:00
- 用户重新验证时间：2026-06-12T21:09:44+08:00
- 起始分支：main
- 起始 HEAD：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 是否 Commit：否
- 是否 Push：否
- 是否创建或切换分支：否
## 用户真实反馈
- `python scripts\project_status.py` 可以正常显示项目状态。
- `python scripts\validate_memory.py` 结果为 PASS，FAIL 0，WARNING 0。
- `python -m unittest discover -s tests -v` 共 11 项测试，全部通过。
- 双击 `scripts\project_status.bat` 执行失败。
- 实际问题包括：BAT 错误寻找 `scripts\scripts\project_status.py`；仓库路径包含中文时命令解析异常；CMD 中文乱码；BAT 没有可靠地从任意启动位置切换到仓库根目录。
## 本轮修改
- 修复 `scripts/project_status.bat`。
- 修复 `scripts/validate_memory.bat`。
- 修复 `scripts/build_gpt_context.bat`。

### 工作区摘要

tracked 修改：
- .gitignore
- README.md

未跟踪文件：
- .env.example
- AGENTS.md
- Agent-Memory/00-当前状态/CURRENT_STATE.md
- Agent-Memory/00-当前状态/CURRENT_TASK.md
- Agent-Memory/00-当前状态/ENVIRONMENT.md
- Agent-Memory/00-当前状态/FILE_MAP.md
- Agent-Memory/00-当前状态/OPEN_ISSUES.md
- Agent-Memory/00-当前状态/PROJECT.md
- Agent-Memory/00-当前状态/USAGE.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-001/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-001/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-001/workspace_manifest.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-002/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-002/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-002/workspace_manifest.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/TASK.md
- Agent-Memory/02-阶段快照/README.md
- Agent-Memory/03-GPT导出/GPT_CONTEXT.md
- Agent-Memory/INDEX.md
- Agent-Memory/MEMORY_STATUS.json
- config/README.md
- data/README.md
- data/interim/.gitkeep
- data/processed/.gitkeep
- data/raw/.gitkeep
- docs/ARCHITECTURE.md
- docs/DESIGN_QUESTIONS.md
- docs/DEVELOPMENT_WORKFLOW.md
- logs/README.md
- outputs/README.md
- pyproject.toml
- scripts/build_gpt_context.bat
- scripts/build_gpt_context.py
- scripts/build_index.py
- scripts/create_checkpoint.py
- scripts/finish_round.py
- scripts/git_snapshot.py
- scripts/init_memory.py
- scripts/memory_common.py
- scripts/project_status.bat
- scripts/project_status.py
- scripts/start_round.py
- scripts/start_task.py
- scripts/templates/CHECKPOINT.template.md
- scripts/templates/ISSUE.template.md
- scripts/templates/ROUND.template.md
- scripts/templates/TASK.template.md
- scripts/validate_memory.bat
- scripts/validate_memory.py
- src/stock_selector/__init__.py
- src/stock_selector/agents/README.md
- src/stock_selector/agents/__init__.py
- src/stock_selector/backtest/README.md
- src/stock_selector/backtest/__init__.py
- src/stock_selector/common/README.md
- src/stock_selector/common/__init__.py
- src/stock_selector/data/README.md
- src/stock_selector/data/__init__.py
- src/stock_selector/features/README.md
- src/stock_selector/features/__init__.py
- src/stock_selector/reports/README.md
- src/stock_selector/reports/__init__.py
- src/stock_selector/screening/README.md
- src/stock_selector/screening/__init__.py
- tests/__init__.py
- tests/test_memory_tools.py
- 新建文件夹/5b4c8c3c74c7b9eef154ea8169a70a17.png

## C. 用户验证

- 用户验证状态：passed
- 用户验证已通过，可保持 `L4_USER_VERIFIED`；GitHub 同步前不得标记 `L5_CLOSED`。
- 下一步建议：用户在 GitHub Desktop 中检查改动，确认后 Commit 并 Publish/Push；同步前不得标记 L5。

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-002/`
- `scripts/`
- `tests/test_memory_tools.py`
