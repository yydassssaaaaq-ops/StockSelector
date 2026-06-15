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
