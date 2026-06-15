# GPT_CONTEXT.md

本文件由 `scripts/build_gpt_context.py` 自动生成。`MEMORY_STATUS.json` 是机器状态唯一权威来源。

## A. 自动事实

- 项目：StockSelector / A股智能选股系统
- 当前 TASK：TASK-20260612-001
- 当前 ROUND：ROUND-005
- 执行状态：waiting_user_review
- 验证等级：L2_AGENT_TESTED
- 用户验证：not_run
- GitHub 同步：not_pushed
- 当前真实分支：main
- 当前真实 HEAD：e3c9faa19704d7ce04ea735a2765fb7e65ff01f2
- 状态文件观察到的 HEAD：e3c9faa19704d7ce04ea735a2765fb7e65ff01f2
- 工作区干净：False

## B. Agent 解释

### 当前任务
# CURRENT_TASK
- 当前 TASK：TASK-20260612-001
- 任务名称：真实历史股票案卷库产品化与自动增量监控
- 当前 ROUND：ROUND-005
- 本轮目标：将历史案卷库升级为自动增量监控模式，双击启动后同时执行增量导入、只读文件监控、本地网页服务和浏览器工作台。
- 当前状态：waiting_user_review
- 当前验证等级：L2_AGENT_TESTED
- 用户验证状态：not_run
- 当前卡点：无阻塞问题；等待用户双击 `启动历史案卷库.bat` 和浏览器复验。
- 已完成：只读文件监控、变更防抖、增量变更导入、监控事件日志、今日变化页面、监控状态和开关、模拟新增案卷验收、自动化测试。
- 未完成：用户真实双击验收、GitHub 外循环、正式选股策略设计与实现。
- 下一步：用户访问 `http://127.0.0.1:8765/` 或双击 BAT 验收；确认后可进入基于真实案卷库的选股逻辑研讨。
- 是否需要 GitHub 外循环：待用户确认；本轮 Agent 未 Commit、未 Push。

### 当前状态
# CURRENT_STATE
- 当前阶段：真实历史股票案卷库 V0.1 已升级为自动增量监控模式，等待用户复核。
- 当前可运行能力：只读导入旧 L.Lawlight 历史数据、SQLite 索引、变更路径级增量导入、文件监控、防抖、删除和重命名识别、今日变化页面、股票搜索、案卷详情、案卷对比、诊断中心、数据考古报告、双击启动 BAT。
- 当前正常命令：`python scripts\import_legacy_cases.py`、`python scripts\serve_case_library.py --open-browser`、`python -m unittest discover -s tests -v`、`python scripts\validate_memory.py`。
- 当前真实数据：正式导入扫描 `D:\AAAAAAAAA项目\L.Lawlight\1\RadarData` 和 `HumanView`，433 个目录、2430 个文件、9 只股票、19 个案卷、无法解析 0。
- 当前新增监控状态：本地服务进程已启动于 `http://127.0.0.1:8765/`，`/api/monitor/status` 返回 enabled=true、running=true。
- 本轮模拟验收：临时旧项目新增 688001 案卷，监控发现 13 个新增文件，538 ms 内进入数据库，自动导入耗时 137 ms，今日变化页显示新增股票 1、新增案卷 1。
- 当前尚不存在的业务能力：正式选股策略、涨跌预测、回测交易、实盘接口、投资建议。
- 当前限制：尚未经过用户真实双击验收，因此验证等级保持 `L2_AGENT_TESTED`，不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- Git HEAD 记录语义：当前环境 PowerShell 中 `git` 不在 PATH；`MEMORY_STATUS.json` 里的 HEAD 字段保留最近观察值。
- 最近一次测试：见 `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-005/ROUND.md`。
- 最近稳定 commit：e3c9faa19704d7ce04ea735a2765fb7e65ff01f2
- 下一次优先事项：用户双击启动并验收工作台；通过后可进入选股逻辑研讨。

### 开放问题
# OPEN_ISSUES
当前无开放问题。
非阻塞观察：
- 当前 PowerShell 环境中 `git` 不在 PATH；本轮未执行 git 操作。
- 项目测试入口仍为 `python -m unittest discover -s tests -v`，未声明 pytest 依赖。
- 自动监控采用标准库轮询，适合当前 2430 文件规模；如果旧项目文件量大幅增长，可再评估 watchdog 类事件驱动实现。

### 最近 ROUND
# ROUND-005
## 基本信息
- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-005
- 触发来源：用户要求将历史股票案卷库升级为自动增量监控模式
- 本轮目标：双击启动后同时完成增量导入、只读文件监控、本地网页服务和浏览器工作台；旧项目产生 RadarData 或 HumanView 新案卷时自动发现、导入、检查并更新网页
- 起始时间：2026-06-15T01:10:41+08:00
- 结束时间：2026-06-15T01:11:36+08:00
- 起始分支：main
- 起始 HEAD：e3c9faa19704d7ce04ea735a2765fb7e65ff01f2
- 是否 Commit：否
- 是否 Push：否
- 是否修改旧项目：否，旧 `D:\AAAAAAAAA项目\L.Lawlight\1` 仅被只读扫描
## 本轮修改
- 新增 `src/stock_selector/case_library/monitor.py`
- 扩展 `src/stock_selector/case_library/importer.py`：新增监控表、自动导入批次表、案卷变化表、删除墓碑字段、变更路径级增量导入
- 扩展 `src/stock_selector/case_library/webapp.py`：新增今日变化 API、监控状态 API、监控开关 API、今日变化页面，并在服务生命周期内启动/停止监控线程
- 更新 `启动历史案卷库.bat`：双击启动后执行导入、启动监控、启动网页服务和浏览器入口，失败保留窗口
- 新增 `tests/test_case_library_monitor.py`
- 更新 `docs/case_library_usage.md`
- 生成 `outputs/case_library/monitor_simulation_summary.json`
## 真实数据状态
- 真实旧项目根目录：`D:\AAAAAAAAA项目\L.Lawlight\1`
- 监控目录：`RadarData`、`HumanView`

### 工作区摘要

tracked 修改：
- Agent-Memory/00-当前状态/CURRENT_STATE.md
- Agent-Memory/00-当前状态/CURRENT_TASK.md
- Agent-Memory/00-当前状态/ENVIRONMENT.md
- Agent-Memory/00-当前状态/FILE_MAP.md
- Agent-Memory/00-当前状态/OPEN_ISSUES.md
- Agent-Memory/00-当前状态/USAGE.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/TASK.md
- Agent-Memory/03-GPT导出/GPT_CONTEXT.md
- Agent-Memory/INDEX.md
- Agent-Memory/MEMORY_STATUS.json
- scripts/init_memory.py
- scripts/start_round.py
- scripts/start_task.py
- scripts/validate_memory.py
- tests/test_memory_tools.py

未跟踪文件：
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-003/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-003/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-003/workspace_manifest.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-004/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-004/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-004/workspace_manifest.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-005/ROUND.md
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-005/test_results.json
- Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-005/workspace_manifest.json
- docs/case_library_usage.md
- docs/legacy_data_schema_map.md
- scripts/import_legacy_cases.py
- scripts/launch_case_library.py
- scripts/serve_case_library.py
- src/stock_selector/case_library/__init__.py
- src/stock_selector/case_library/importer.py
- src/stock_selector/case_library/monitor.py
- src/stock_selector/case_library/webapp.py
- tests/test_case_library.py
- tests/test_case_library_monitor.py
- 启动历史案卷库.bat

## C. 用户验证

- 用户验证状态：not_run
- 当前不得标记 `L4_USER_VERIFIED` 或 `L5_CLOSED`。
- 下一步建议：用户检查自动验证结果，确认后再决定是否进入 GitHub 外循环。

## 建议检查区域

- `Agent-Memory/MEMORY_STATUS.json`
- `Agent-Memory/00-当前状态/`
- `Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-005/`
- `scripts/`
- `tests/test_memory_tools.py`
