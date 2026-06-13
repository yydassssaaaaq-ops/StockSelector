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
