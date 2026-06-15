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
- 正式导入扫描目录数：433
- 正式导入扫描文件数：2430
- 识别股票数：9
- 识别案卷数：19
- run_id 运行记录数：13
- 重复文件数：1077
- 无法解析文件数：0
- 质量等级分布：A 1，B 18
- 正式导入后旧项目未被写入

## 模拟新增案卷验收

- 模拟范围：临时旧项目目录，不修改真实 L.Lawlight
- 模拟股票代码：688001
- 新增文件数：13
- 系统发现时间：2026-06-15T01:05:41+08:00
- 墙钟耗时：538 ms 内案卷进入数据库
- 自动导入耗时：137 ms
- 数据库新增：1 个案卷、13 个文件记录
- 今日变化页面显示：新增股票 1、新增案卷 1、更新案卷 0、监控事件 13、无法解析文件 0
- 结果：通过

## 验证记录

- `python -m py_compile src\stock_selector\case_library\importer.py src\stock_selector\case_library\monitor.py src\stock_selector\case_library\webapp.py`：退出码 0，通过
- `python -m unittest tests.test_case_library_monitor -v`：退出码 0，11 项监控专项测试 OK
- `python -m unittest discover -s tests -v`：退出码 0，43 项完整测试 OK
- `python scripts\import_legacy_cases.py`：退出码 0，真实导入通过，扫描 2430 文件，识别 9 股票、19 案卷、无法解析 0
- 模拟新增案卷脚本：第一次因中文绝对路径进入 stdin 编码失败，第二次因中文股票名被 PowerShell 管道编码污染失败，改用当前工作目录和 ASCII 模拟名后退出码 0，通过
- `Invoke-WebRequest http://127.0.0.1:8765/api/monitor/status`：退出码 0，返回 enabled=true、running=true
- `Invoke-WebRequest http://127.0.0.1:8765/api/today_changes`：退出码 0，返回今日变化结构
- 浏览器烟测：`http://127.0.0.1:8765/` 打开通过，标题为真实历史股票案卷库 V0.1，今日变化页显示监控状态、自动导入批次和文件监控事件

## 当前结论

- 自动增量监控模式已达到 L2_AGENT_TESTED。
- 当前本地服务进程已用新版代码启动，访问地址为 `http://127.0.0.1:8765/`。
- 本轮没有实现正式选股策略，也没有生成投资预测或买卖建议。
- 仍等待用户本机双击 BAT 和浏览器交互复验，因此不标记 L4/L5。
